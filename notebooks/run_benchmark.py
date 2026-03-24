# Databricks notebook source
# MAGIC %md
# MAGIC # Nyaya Dhwani — Benchmark Evaluation
# MAGIC
# MAGIC Evaluates the RAG pipeline across 4 dimensions:
# MAGIC 1. **Retrieval accuracy** — FAISS vs Vector Search
# MAGIC 2. **MCQ accuracy** — LLM answer correctness
# MAGIC 3. **Open-ended quality** — keyword coverage + citation checks
# MAGIC 4. **Multilingual quality** — translation round-trip fidelity
# MAGIC
# MAGIC Uses the same code paths as the deployed app (`src/nyaya_dhwani/`).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

import os, sys, json, time
from datetime import datetime, timezone

# --- Set REPO_ROOT to your Databricks Repos checkout path ---
REPO_ROOT = "/Workspace/Users/shwetha.bhandari@gmail.com/nyaya-dhwani-hackathon"
sys.path.insert(0, f"{REPO_ROOT}/src")

# LLM config
os.environ["LLM_OPENAI_BASE_URL"] = "https://7474650313055161.ai-gateway.cloud.databricks.com/mlflow/v1"
os.environ["LLM_MODEL"] = "databricks-llama-4-maverick"
os.environ["DATABRICKS_TOKEN"] = dbutils.secrets.get("nyaya-dhwani", "databricks_token") if "databricks_token" in [s.key for s in dbutils.secrets.list("nyaya-dhwani")] else ""

# Sarvam
os.environ["SARVAM_API_KEY"] = dbutils.secrets.get("nyaya-dhwani", "sarvam_api_key")

# HuggingFace (for BhashaBench-Legal)
try:
    os.environ["HF_TOKEN"] = dbutils.secrets.get("nyaya-dhwani", "hf_token")
    print("HF_TOKEN loaded from secret scope")
except Exception:
    print("HF_TOKEN not found — BBL evaluation will be skipped")

# Vector Search config
VS_ENDPOINT = "nyaya_vs_endpoint"
VS_INDEX = "main.india_legal.legal_rag_corpus_index"

# FAISS index (FUSE-mounted on cluster)
FAISS_INDEX_DIR = "/Volumes/main/india_legal/legal_files/nyaya_index"

# Run ID for tracking
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
print(f"Benchmark run: {RUN_ID}")

# Verify imports
from nyaya_dhwani.retrieval import CorpusIndex
from nyaya_dhwani.embedder import SentenceEmbedder
from nyaya_dhwani.retriever import FaissRetriever
from nyaya_dhwani.vs_retriever import VectorSearchRetriever
from nyaya_dhwani.keyword_boost import detect_section_references, boost_with_keywords
from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text, rag_user_message
from nyaya_dhwani.sarvam_client import translate_text, is_configured as sarvam_configured
print(f"All imports OK. Sarvam configured: {sarvam_configured()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load benchmark questions

# COMMAND ----------

with open(f"{REPO_ROOT}/tests/benchmark_questions.json") as f:
    benchmark = json.load(f)

questions = benchmark["questions"]
mcq_qs = [q for q in questions if "options" in q]
open_qs = [q for q in questions if "expected_in_answer" in q]
print(f"Loaded {len(questions)} questions: {len(mcq_qs)} MCQ, {len(open_qs)} open-ended")
print(f"Languages: {set(q['language'] for q in questions)}")
print(f"Categories: {set(q['category'] for q in questions)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Download BhashaBench-Legal (if accessible)

# COMMAND ----------

bbl_en = []
bbl_hi = []

if os.environ.get("HF_TOKEN"):
    try:
        %pip install datasets -q
        from datasets import load_dataset

        hf_token = os.environ["HF_TOKEN"]

        print("Downloading BhashaBench-Legal English...")
        ds_en = load_dataset("bharatgenai/BhashaBench-Legal", data_dir="English", split="test", token=hf_token)
        criminal_en = ds_en.filter(lambda x: "Criminal" in (x.get("subject_domain") or ""))
        bbl_en = [dict(r) for r in criminal_en]
        print(f"  Criminal Law (English): {len(bbl_en)} questions")

        print("Downloading BhashaBench-Legal Hindi...")
        ds_hi = load_dataset("bharatgenai/BhashaBench-Legal", data_dir="Hindi", split="test", token=hf_token)
        criminal_hi = ds_hi.filter(lambda x: "Criminal" in (x.get("subject_domain") or ""))
        bbl_hi = [dict(r) for r in criminal_hi]
        print(f"  Criminal Law (Hindi): {len(bbl_hi)} questions")

        # Save to Delta
        if bbl_en:
            spark.createDataFrame(criminal_en.to_pandas()).write.mode("overwrite").saveAsTable("main.india_legal.bbl_criminal_law_en")
            print("  Saved to main.india_legal.bbl_criminal_law_en")
        if bbl_hi:
            spark.createDataFrame(criminal_hi.to_pandas()).write.mode("overwrite").saveAsTable("main.india_legal.bbl_criminal_law_hi")
            print("  Saved to main.india_legal.bbl_criminal_law_hi")

    except Exception as e:
        print(f"BBL download failed (will skip): {e}")
else:
    print("HF_TOKEN not set — skipping BhashaBench-Legal download")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 1: Retrieval Evaluation
# MAGIC
# MAGIC Compare FAISS vs Vector Search on the internal benchmark questions.

# COMMAND ----------

import pandas as pd

# Initialize retrievers
print("Loading FAISS retriever...")
faiss_ret = FaissRetriever(FAISS_INDEX_DIR)
# Warm up
_ = faiss_ret.search("test", k=1)
print("FAISS ready.")

print("Loading VS retriever...")
vs_ret = VectorSearchRetriever(VS_ENDPOINT, VS_INDEX)
# Warm up
try:
    _ = vs_ret.search("test", k=1)
    vs_available = True
    print("Vector Search ready.")
except Exception as e:
    vs_available = False
    print(f"Vector Search not available: {e}")

# COMMAND ----------

def eval_retrieval(retriever, questions, k=7, label=""):
    """Evaluate retrieval recall and MRR for questions with expected_chunks."""
    results = []
    for q in questions:
        expected = set(q.get("expected_chunks", []))
        if not expected:
            continue
        try:
            df = retriever.search(q["question"], k=k)
            retrieved = set(df["chunk_id"].tolist()) if "chunk_id" in df.columns else set()

            recall = len(retrieved & expected) / len(expected)

            # MRR: 1/rank of first relevant chunk
            mrr = 0.0
            for _, row in df.iterrows():
                if row.get("chunk_id") in expected:
                    mrr = 1.0 / (row.get("rank", 0) + 1)
                    break

            # Keyword boost check
            refs = detect_section_references(q["question"])
            keyword_hit = any(cid in retrieved for cid in expected) if refs else None

            results.append({
                "question_id": q["id"],
                "category": q.get("category", ""),
                "difficulty": q.get("difficulty", ""),
                "language": q.get("language", "en"),
                "recall": recall,
                "mrr": mrr,
                "keyword_hit": keyword_hit,
                "expected": list(expected),
                "retrieved": list(retrieved),
            })
        except Exception as e:
            print(f"  Error on {q['id']}: {e}")
            results.append({"question_id": q["id"], "recall": 0, "mrr": 0, "keyword_hit": False})

    df = pd.DataFrame(results)
    if df.empty:
        print(f"{label}: No questions with expected_chunks")
        return df

    print(f"\n{'='*60}")
    print(f"  {label} Retrieval Results (k={k})")
    print(f"{'='*60}")
    print(f"  Questions evaluated: {len(df)}")
    print(f"  Mean Recall@{k}:     {df['recall'].mean():.3f}")
    print(f"  Mean MRR:            {df['mrr'].mean():.3f}")
    kw = df[df["keyword_hit"].notna()]
    if len(kw) > 0:
        print(f"  Keyword boost rate:  {kw['keyword_hit'].mean():.3f} ({kw['keyword_hit'].sum():.0f}/{len(kw)})")
    print()
    return df

# Run retrieval eval
print("Phase 1a: FAISS retrieval")
faiss_results = eval_retrieval(faiss_ret, questions, k=7, label="FAISS")

if vs_available:
    print("Phase 1b: Vector Search retrieval")
    vs_results = eval_retrieval(vs_ret, questions, k=7, label="Vector Search")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 1 Results — Side by Side

# COMMAND ----------

if vs_available:
    comparison = pd.DataFrame({
        "Metric": ["Mean Recall@7", "Mean MRR", "Keyword boost rate"],
        "FAISS": [
            faiss_results["recall"].mean() if len(faiss_results) else 0,
            faiss_results["mrr"].mean() if len(faiss_results) else 0,
            faiss_results[faiss_results["keyword_hit"].notna()]["keyword_hit"].mean() if len(faiss_results) else 0,
        ],
        "Vector Search": [
            vs_results["recall"].mean() if len(vs_results) else 0,
            vs_results["mrr"].mean() if len(vs_results) else 0,
            vs_results[vs_results["keyword_hit"].notna()]["keyword_hit"].mean() if len(vs_results) else 0,
        ],
    })
    display(comparison)
else:
    print("Vector Search not available — showing FAISS only")
    display(faiss_results[["question_id", "recall", "mrr", "keyword_hit"]])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 2: MCQ Evaluation
# MAGIC
# MAGIC Test LLM answer accuracy on MCQ questions (internal + BBL).

# COMMAND ----------

SYSTEM_PROMPT_MCQ = "You are a legal exam assistant. Answer with ONLY the letter (a, b, c, or d). No explanation."

def eval_mcq(retriever, questions, label="", max_questions=None):
    """Evaluate MCQ accuracy using RAG context + LLM."""
    if max_questions:
        questions = questions[:max_questions]

    results = []
    for i, q in enumerate(questions):
        try:
            # Retrieve context
            query_text = q.get("question", "")
            ctx_df = retriever.search(query_text, k=7)
            texts = ctx_df["text"].tolist() if "text" in ctx_df.columns else []

            # Format MCQ prompt
            options = q.get("options", {})
            if not options:
                # BBL format: option_a, option_b, etc.
                options = {
                    "a": q.get("option_a", ""),
                    "b": q.get("option_b", ""),
                    "c": q.get("option_c", ""),
                    "d": q.get("option_d", ""),
                }

            context_str = "\n\n".join(str(t).strip() for t in texts if t)
            mcq_prompt = (
                f"Context:\n{context_str}\n\n"
                f"Question: {query_text}\n"
                f"A) {options.get('a', '')}\n"
                f"B) {options.get('b', '')}\n"
                f"C) {options.get('c', '')}\n"
                f"D) {options.get('d', '')}\n\n"
                f"Answer with ONLY the letter (a, b, c, or d)."
            )

            response = chat_completions(
                [{"role": "system", "content": SYSTEM_PROMPT_MCQ},
                 {"role": "user", "content": mcq_prompt}],
                max_tokens=10, temperature=0.0,
            )
            answer = extract_assistant_text(response).strip().lower()[:1]
            correct_answer = q.get("correct_answer", "").strip().lower()[:1]
            is_correct = answer == correct_answer

            results.append({
                "question_id": q.get("id", f"q_{i}"),
                "category": q.get("category", q.get("subject_domain", "")),
                "difficulty": q.get("difficulty", q.get("question_level", "")),
                "language": q.get("language", "en"),
                "predicted": answer,
                "correct": correct_answer,
                "is_correct": is_correct,
            })

            if (i + 1) % 10 == 0:
                acc_so_far = sum(r["is_correct"] for r in results) / len(results)
                print(f"  [{i+1}/{len(questions)}] Running accuracy: {acc_so_far:.3f}")

        except Exception as e:
            print(f"  Error on question {i}: {e}")
            results.append({
                "question_id": q.get("id", f"q_{i}"),
                "is_correct": False,
                "predicted": "error",
                "correct": q.get("correct_answer", "").strip().lower()[:1],
            })

    df = pd.DataFrame(results)
    if df.empty:
        print(f"{label}: No MCQ results")
        return df

    print(f"\n{'='*60}")
    print(f"  {label} MCQ Results")
    print(f"{'='*60}")
    print(f"  Questions: {len(df)}")
    print(f"  Accuracy:  {df['is_correct'].mean():.3f} ({df['is_correct'].sum()}/{len(df)})")

    # By difficulty
    if "difficulty" in df.columns:
        by_diff = df.groupby("difficulty")["is_correct"].agg(["mean", "count"])
        print(f"\n  By difficulty:")
        for level, row in by_diff.iterrows():
            if level:
                print(f"    {level}: {row['mean']:.3f} ({int(row['count'])} questions)")

    # By category
    if "category" in df.columns:
        by_cat = df.groupby("category")["is_correct"].agg(["mean", "count"])
        print(f"\n  By category:")
        for cat, row in by_cat.iterrows():
            if cat:
                print(f"    {cat}: {row['mean']:.3f} ({int(row['count'])} questions)")
    print()
    return df

# COMMAND ----------

# Internal MCQ
retriever = vs_ret if vs_available else faiss_ret
backend_label = "VS" if vs_available else "FAISS"

print(f"Phase 2a: Internal MCQ ({backend_label})")
internal_mcq_results = eval_mcq(retriever, mcq_qs, label=f"Internal ({backend_label})")

# COMMAND ----------

# BBL MCQ (English — run a subset to save time/cost)
if bbl_en:
    BBL_SAMPLE_SIZE = 50  # Adjust based on time/cost budget
    print(f"Phase 2b: BBL Criminal Law MCQ (English, first {BBL_SAMPLE_SIZE})")
    bbl_mcq_results = eval_mcq(retriever, bbl_en, label=f"BBL Criminal Law EN ({backend_label})", max_questions=BBL_SAMPLE_SIZE)
else:
    print("Phase 2b: Skipped (no BBL data)")
    bbl_mcq_results = pd.DataFrame()

# COMMAND ----------

# BBL MCQ (Hindi — smaller subset)
if bbl_hi:
    BBL_HI_SAMPLE = 20
    print(f"Phase 2c: BBL Criminal Law MCQ (Hindi, first {BBL_HI_SAMPLE})")
    bbl_hi_results = eval_mcq(retriever, bbl_hi, label=f"BBL Criminal Law HI ({backend_label})", max_questions=BBL_HI_SAMPLE)
else:
    print("Phase 2c: Skipped (no Hindi BBL data)")
    bbl_hi_results = pd.DataFrame()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 3: Open-Ended Evaluation

# COMMAND ----------

SYSTEM_PROMPT_RAG = (
    "You are Nyaya Dhwani, an assistant for Indian legal information. "
    "Answer using the Context below when it is relevant. Cite Acts or sections when the context supports it. "
    "If the context is insufficient, say so briefly. "
    "Do not claim to be a lawyer. Keep answers clear and structured. "
    "Respond in English."
)

open_results = []
for q in open_qs:
    try:
        ctx_df = retriever.search(q["question"], k=7)
        texts = ctx_df["text"].tolist() if "text" in ctx_df.columns else []
        user_msg = rag_user_message([str(t) for t in texts], q["question"])

        response = chat_completions(
            [{"role": "system", "content": SYSTEM_PROMPT_RAG},
             {"role": "user", "content": user_msg}],
            max_tokens=2048, temperature=0.2,
        )
        answer = extract_assistant_text(response)

        # Keyword coverage
        expected_kw = q.get("expected_in_answer", [])
        found = sum(1 for kw in expected_kw if kw.lower() in answer.lower())
        kw_coverage = found / len(expected_kw) if expected_kw else 1.0

        # Retrieval check
        expected_chunks = set(q.get("expected_chunks", []))
        retrieved = set(ctx_df["chunk_id"].tolist()) if "chunk_id" in ctx_df.columns else set()
        chunk_recall = len(retrieved & expected_chunks) / len(expected_chunks) if expected_chunks else 1.0

        open_results.append({
            "question_id": q["id"],
            "question": q["question"],
            "keyword_coverage": kw_coverage,
            "chunk_recall": chunk_recall,
            "answer_preview": answer[:200],
            "expected_keywords": expected_kw,
            "found_keywords": [kw for kw in expected_kw if kw.lower() in answer.lower()],
            "missing_keywords": [kw for kw in expected_kw if kw.lower() not in answer.lower()],
        })
    except Exception as e:
        print(f"  Error on {q['id']}: {e}")

open_df = pd.DataFrame(open_results)
if not open_df.empty:
    print(f"\n{'='*60}")
    print(f"  Open-Ended Results")
    print(f"{'='*60}")
    print(f"  Questions: {len(open_df)}")
    print(f"  Mean keyword coverage: {open_df['keyword_coverage'].mean():.3f}")
    print(f"  Mean chunk recall:     {open_df['chunk_recall'].mean():.3f}")
    print()
    for _, r in open_df.iterrows():
        status = "PASS" if r["keyword_coverage"] >= 0.8 else "FAIL"
        print(f"  [{status}] {r['question_id']}: coverage={r['keyword_coverage']:.2f}")
        if r["missing_keywords"]:
            print(f"         missing: {r['missing_keywords']}")
    display(open_df[["question_id", "keyword_coverage", "chunk_recall", "answer_preview"]])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 4: Multilingual Evaluation
# MAGIC
# MAGIC Test translation round-trip fidelity and cross-lingual retrieval.

# COMMAND ----------

if not sarvam_configured():
    print("Phase 4: Skipped (SARVAM_API_KEY not configured)")
else:
    multilingual_results = []

    # English MCQ questions that have Hindi/Kannada equivalents
    en_qs = {q["id"].replace("HI_", "MAP_").replace("KN_", "MAP_"): q
             for q in mcq_qs if q["language"] == "en" and q["category"] == "ipc_bns_mapping"}

    non_en_qs = [q for q in mcq_qs if q["language"] != "en"]

    print(f"Phase 4: Testing {len(non_en_qs)} non-English questions")

    for q in non_en_qs:
        try:
            # Translate non-English question to English (same as app pipeline)
            translated = translate_text(
                q["question"],
                source_language_code="auto",
                target_language_code="en-IN",
            )
            print(f"\n  [{q['id']}] {q['language']}")
            print(f"    Original:   {q['question'][:80]}...")
            print(f"    Translated: {translated[:80]}...")

            # Retrieve with translated query
            ctx_df = retriever.search(translated, k=7)
            retrieved = set(ctx_df["chunk_id"].tolist()) if "chunk_id" in ctx_df.columns else set()
            expected = set(q.get("expected_chunks", []))
            recall = len(retrieved & expected) / len(expected) if expected else 1.0

            # MCQ with translated context
            texts = ctx_df["text"].tolist() if "text" in ctx_df.columns else []
            options = q.get("options", {})
            # Translate options back to English for the LLM
            context_str = "\n\n".join(str(t).strip() for t in texts if t)
            mcq_prompt = (
                f"Context:\n{context_str}\n\n"
                f"Question: {translated}\n"
                f"A) {options.get('a', '')}\n"
                f"B) {options.get('b', '')}\n"
                f"C) {options.get('c', '')}\n"
                f"D) {options.get('d', '')}\n\n"
                f"Answer with ONLY the letter (a, b, c, or d)."
            )
            response = chat_completions(
                [{"role": "system", "content": SYSTEM_PROMPT_MCQ},
                 {"role": "user", "content": mcq_prompt}],
                max_tokens=10, temperature=0.0,
            )
            answer = extract_assistant_text(response).strip().lower()[:1]
            correct = q.get("correct_answer", "").strip().lower()[:1]

            multilingual_results.append({
                "question_id": q["id"],
                "language": q["language"],
                "translated_query": translated,
                "retrieval_recall": recall,
                "predicted": answer,
                "correct": correct,
                "is_correct": answer == correct,
            })
            print(f"    Recall: {recall:.2f}, Answer: {answer} (correct: {correct}) {'PASS' if answer == correct else 'FAIL'}")

        except Exception as e:
            print(f"  Error on {q['id']}: {e}")
            multilingual_results.append({
                "question_id": q["id"], "language": q["language"],
                "is_correct": False, "retrieval_recall": 0,
            })

    ml_df = pd.DataFrame(multilingual_results)
    if not ml_df.empty:
        print(f"\n{'='*60}")
        print(f"  Multilingual Results")
        print(f"{'='*60}")
        print(f"  Questions: {len(ml_df)}")
        print(f"  Accuracy:  {ml_df['is_correct'].mean():.3f}")
        print(f"  Mean retrieval recall: {ml_df['retrieval_recall'].mean():.3f}")
        by_lang = ml_df.groupby("language")["is_correct"].agg(["mean", "count"])
        print(f"\n  By language:")
        for lang, row in by_lang.iterrows():
            print(f"    {lang}: {row['mean']:.3f} ({int(row['count'])} questions)")
        display(ml_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print(f"\n{'='*60}")
print(f"  BENCHMARK SUMMARY — Run {RUN_ID}")
print(f"{'='*60}\n")

summary_rows = []

# Retrieval
if len(faiss_results) > 0:
    summary_rows.append({"Phase": "Retrieval", "Metric": "FAISS Recall@7", "Value": f"{faiss_results['recall'].mean():.3f}", "Target": "> 0.8"})
    summary_rows.append({"Phase": "Retrieval", "Metric": "FAISS MRR", "Value": f"{faiss_results['mrr'].mean():.3f}", "Target": "> 0.5"})
if vs_available and len(vs_results) > 0:
    summary_rows.append({"Phase": "Retrieval", "Metric": "VS Recall@7", "Value": f"{vs_results['recall'].mean():.3f}", "Target": "> 0.8"})
    summary_rows.append({"Phase": "Retrieval", "Metric": "VS MRR", "Value": f"{vs_results['mrr'].mean():.3f}", "Target": "> 0.5"})

# MCQ
if len(internal_mcq_results) > 0:
    summary_rows.append({"Phase": "MCQ", "Metric": "Internal accuracy", "Value": f"{internal_mcq_results['is_correct'].mean():.3f}", "Target": "> 0.7"})
if len(bbl_mcq_results) > 0:
    summary_rows.append({"Phase": "MCQ", "Metric": "BBL Criminal Law (EN)", "Value": f"{bbl_mcq_results['is_correct'].mean():.3f}", "Target": "> 0.5"})
if len(bbl_hi_results) > 0:
    summary_rows.append({"Phase": "MCQ", "Metric": "BBL Criminal Law (HI)", "Value": f"{bbl_hi_results['is_correct'].mean():.3f}", "Target": "> 0.4"})

# Open-ended
if len(open_df) > 0:
    summary_rows.append({"Phase": "Open-ended", "Metric": "Keyword coverage", "Value": f"{open_df['keyword_coverage'].mean():.3f}", "Target": "> 0.8"})
    summary_rows.append({"Phase": "Open-ended", "Metric": "Chunk recall", "Value": f"{open_df['chunk_recall'].mean():.3f}", "Target": "> 0.8"})

# Multilingual
if sarvam_configured() and 'ml_df' in dir() and len(ml_df) > 0:
    summary_rows.append({"Phase": "Multilingual", "Metric": "Non-EN accuracy", "Value": f"{ml_df['is_correct'].mean():.3f}", "Target": "> 0.6"})
    summary_rows.append({"Phase": "Multilingual", "Metric": "Non-EN retrieval recall", "Value": f"{ml_df['retrieval_recall'].mean():.3f}", "Target": "> 0.7"})

summary_df = pd.DataFrame(summary_rows)
display(summary_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save Results to Delta

# COMMAND ----------

# Flatten all results into one table for tracking
all_results = []

for _, r in faiss_results.iterrows() if len(faiss_results) > 0 else []:
    all_results.append({"run_id": RUN_ID, "phase": "retrieval", "backend": "faiss",
                        "question_id": r.get("question_id", ""), "metric": "recall",
                        "value": r.get("recall", 0), "details": json.dumps(dict(r))})

if vs_available:
    for _, r in vs_results.iterrows() if len(vs_results) > 0 else []:
        all_results.append({"run_id": RUN_ID, "phase": "retrieval", "backend": "vector_search",
                            "question_id": r.get("question_id", ""), "metric": "recall",
                            "value": r.get("recall", 0), "details": json.dumps(dict(r))})

for _, r in internal_mcq_results.iterrows() if len(internal_mcq_results) > 0 else []:
    all_results.append({"run_id": RUN_ID, "phase": "mcq", "backend": backend_label.lower(),
                        "question_id": r.get("question_id", ""), "metric": "accuracy",
                        "value": 1.0 if r.get("is_correct") else 0.0, "details": json.dumps(dict(r))})

if all_results:
    results_sdf = spark.createDataFrame(pd.DataFrame(all_results))
    results_sdf.write.mode("append").saveAsTable("main.india_legal.benchmark_results")
    print(f"Saved {len(all_results)} result rows to main.india_legal.benchmark_results")

    # Summary table
    summary_df["run_id"] = RUN_ID
    spark.createDataFrame(summary_df).write.mode("append").saveAsTable("main.india_legal.benchmark_summary")
    print("Saved summary to main.india_legal.benchmark_summary")
else:
    print("No results to save")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Results are saved to:
# MAGIC - `main.india_legal.benchmark_results` — per-question detail
# MAGIC - `main.india_legal.benchmark_summary` — per-run metrics vs targets
# MAGIC
# MAGIC Query historical results:
# MAGIC ```sql
# MAGIC SELECT * FROM main.india_legal.benchmark_summary ORDER BY run_id DESC LIMIT 20
# MAGIC ```
