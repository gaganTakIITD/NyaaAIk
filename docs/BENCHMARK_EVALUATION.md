# Benchmark Evaluation Plan

## Overview

This document describes how to evaluate Nyaya Dhwani's RAG pipeline quality using benchmark questions. The evaluation measures **retrieval accuracy** (does the system find the right chunks?) and **answer quality** (does the LLM produce correct answers?) across languages.

All evaluation runs in a **Databricks notebook** (`notebooks/run_benchmark.py`) on the Free Edition — using the same Vector Search, LLM, and Sarvam APIs as the deployed app.

## Benchmark datasets

### 1. Internal benchmark (`tests/benchmark_questions.json`)

20 hand-crafted questions covering the app's core use cases:

| Category | Count | Description |
|----------|-------|-------------|
| `ipc_bns_mapping` | 6 | "Which BNS section replaces IPC X?" |
| `bns_knowledge` | 3 | "What does BNS Section X deal with?" |
| `cross_reference` | 3 | Scenario-based: "FIR was filed under IPC 307, what's the BNS equivalent?" |
| `open_ended` | 4 | Free-form questions matching real user queries |

**Languages:** 12 English, 2 Hindi, 2 Kannada, 4 open-ended (English).

**Format:** MCQ questions have `options` and `correct_answer`. Open-ended questions have `expected_in_answer` (keywords that should appear) and `expected_chunks` (chunk IDs that should be retrieved).

### 2. BhashaBench-Legal (external, gated)

[bharatgenai/BhashaBench-Legal](https://huggingface.co/datasets/bharatgenai/BhashaBench-Legal) — 24,365 MCQ questions from Indian legal exams (AIBE, CLAT, judicial services, UGC NET Law).

| Subset | Relevance | Count |
|--------|-----------|-------|
| Criminal Law & Justice | Directly relevant (IPC, BNS, CrPC) | 2,769 |
| Constitutional & Administrative Law | Partially relevant | 3,609 |
| Full dataset | Broad legal coverage | 24,365 |

**Access:** the dataset is gated. Request access at the HuggingFace page. Once approved, download with:

```python
from datasets import load_dataset
ds = load_dataset("bharatgenai/BhashaBench-Legal", data_dir="English", split="test", token="YOUR_TOKEN")
# Filter to Criminal Law
criminal = ds.filter(lambda x: "Criminal" in (x.get("topic") or ""))
criminal.to_json("tests/bbl_criminal_law.json")
```

**Columns:** `question`, `option_a`–`option_d`, `correct_answer`, `question_type`, `question_level`, `topic`, `subdomain`.

## Evaluation dimensions

### Dimension 1: Retrieval accuracy (both backends)

**What we measure:** does the retriever surface the right chunks for a given query?

| Metric | Definition | Target |
|--------|-----------|--------|
| **Recall@k** | Fraction of expected chunks found in top-k results | > 0.8 at k=7 |
| **MRR** (Mean Reciprocal Rank) | Average of 1/rank for the first relevant chunk | > 0.5 |
| **Keyword boost hit rate** | When query mentions "IPC 413", does the mapping chunk appear? | 100% |

**Compare backends:** run the same queries against FAISS and Vector Search to compare retrieval quality.

### Dimension 2: Answer accuracy (MCQ)

**What we measure:** does the LLM select the correct answer given retrieved context?

| Metric | Definition | Target |
|--------|-----------|--------|
| **MCQ accuracy** | Fraction of questions answered correctly | > 0.7 |
| **Accuracy by difficulty** | Breakdown by easy/medium/hard | Easy > 0.85, Medium > 0.65, Hard > 0.5 |
| **Accuracy by category** | Breakdown by question category | Mapping > 0.8, Knowledge > 0.7 |

### Dimension 3: Answer quality (open-ended)

**What we measure:** does the free-form answer contain the expected information?

| Metric | Definition | Target |
|--------|-----------|--------|
| **Keyword coverage** | Fraction of `expected_in_answer` keywords found in response | > 0.8 |
| **Citation accuracy** | Does the response cite the correct BNS/IPC sections? | > 0.7 |
| **Hallucination rate** | Does the response cite sections not in the corpus? | < 0.1 |

### Dimension 4: Multilingual quality

**What we measure:** does the translation pipeline preserve answer accuracy?

| Metric | Definition | Target |
|--------|-----------|--------|
| **Cross-lingual accuracy** | MCQ accuracy for Hindi/Kannada questions vs English equivalents | Within 10% of English |
| **Translation fidelity** | Do translated answers contain the same section numbers? | > 0.9 |
| **Round-trip consistency** | Query in Hindi → translate → retrieve → answer → translate back: same answer as English? | > 0.8 |

## Implementation plan

### What we'll build

**`notebooks/run_benchmark.py`** — a Databricks notebook that:

1. **Sets up access** to all services using the same patterns as the app:
   - Vector Search via `WorkspaceClient().vector_search_indexes.query_index()`
   - LLM via AI Gateway (same `chat_completions` from `nyaya_dhwani.llm_client`)
   - Sarvam translation via `nyaya_dhwani.sarvam_client.translate_text` (loaded from secret scope)
   - FAISS via `nyaya_dhwani.retriever.FaissRetriever`

2. **Runs all 4 evaluation phases** in separate cells:
   - Phase 1: Retrieval evaluation (FAISS vs Vector Search)
   - Phase 2: MCQ evaluation (LLM accuracy)
   - Phase 3: Open-ended evaluation (keyword + citation checks)
   - Phase 4: Multilingual evaluation (translation round-trip)

3. **Outputs results** as Delta tables and display summaries

### Notebook structure

| Cell | What it does | Services used |
|------|-------------|---------------|
| **Setup** | Install deps, configure `sys.path`, load secrets from scope | `databricks-sdk` |
| **Load benchmark** | Read `tests/benchmark_questions.json` from repo | File I/O |
| **Phase 1a: FAISS retrieval** | For each question: embed → FAISS search → check expected chunks | `SentenceEmbedder`, `CorpusIndex` |
| **Phase 1b: VS retrieval** | Same questions via `query_index()` → check expected chunks | Vector Search endpoint |
| **Phase 1 results** | Compare Recall@7, MRR, keyword boost hit rate side by side | Display/Delta |
| **Phase 2: MCQ** | Format MCQ prompt with RAG context → LLM → extract letter → score | AI Gateway LLM |
| **Phase 3: Open-ended** | Free-form RAG answer → check keywords + citations | AI Gateway LLM |
| **Phase 4a: Translation** | Translate English questions to Hindi/Kannada via Sarvam Mayura | Sarvam API |
| **Phase 4b: Multilingual round-trip** | Non-English query → translate → retrieve → answer → translate back → compare | Sarvam + VS + LLM |
| **Phase 4 results** | Cross-lingual accuracy gap, translation fidelity | Display/Delta |
| **Summary** | All metrics in one table, pass/fail against targets | Display |

### Databricks Free Edition setup for the notebook

The benchmark notebook needs the same access as the app. Here's what's required:

| Resource | How to access | Setup |
|----------|---------------|-------|
| **Vector Search** | `WorkspaceClient().vector_search_indexes.query_index()` | Endpoint `nyaya_vs_endpoint` must be ONLINE. User running notebook needs CAN_QUERY. |
| **FAISS index** | `CorpusIndex.load("/Volumes/main/india_legal/legal_files/nyaya_index")` | UC Volume path accessible from notebook cluster (FUSE-mounted). |
| **LLM (Llama Maverick)** | `nyaya_dhwani.llm_client.chat_completions()` | Set `LLM_OPENAI_BASE_URL`, `LLM_MODEL`, `DATABRICKS_TOKEN` as env vars in the notebook. Use Playground → Get code. |
| **Sarvam API** | `nyaya_dhwani.sarvam_client.translate_text()` | Load `SARVAM_API_KEY` from secret scope: `os.environ["SARVAM_API_KEY"] = dbutils.secrets.get("nyaya-dhwani", "sarvam_api_key")` |
| **Benchmark questions** | `json.load(open("tests/benchmark_questions.json"))` | Repo must be cloned in Databricks Repos. Set `REPO_ROOT` to the Repos path. |

**Setup cell pattern (copy-paste ready):**

```python
import os, sys

# --- Set REPO_ROOT to your Databricks Repos checkout path ---
REPO_ROOT = "/Workspace/Users/<your-email>/nyaya-dhwani-hackathon"
sys.path.insert(0, f"{REPO_ROOT}/src")

# LLM config (from Playground → Get code)
os.environ["LLM_OPENAI_BASE_URL"] = "https://7474650313055161.ai-gateway.cloud.databricks.com/mlflow/v1"
os.environ["LLM_MODEL"] = "databricks-llama-4-maverick"
os.environ["DATABRICKS_TOKEN"] = dbutils.secrets.get("nyaya-dhwani", "databricks_token")  # or use a PAT

# Sarvam (for multilingual eval)
os.environ["SARVAM_API_KEY"] = dbutils.secrets.get("nyaya-dhwani", "sarvam_api_key")

# Vector Search config
VS_ENDPOINT = "nyaya_vs_endpoint"
VS_INDEX = "main.india_legal.legal_rag_corpus_index"

# FAISS index path (FUSE-mounted on cluster)
FAISS_INDEX_DIR = "/Volumes/main/india_legal/legal_files/nyaya_index"
```

### Shared code from the app

The notebook reuses these modules directly (via `sys.path` pointing to the repo's `src/`):

| Module | What the notebook uses | Why |
|--------|----------------------|-----|
| `nyaya_dhwani.retriever` | `FaissRetriever`, `get_retriever()` | Retrieval evaluation |
| `nyaya_dhwani.vs_retriever` | `VectorSearchRetriever` | VS retrieval evaluation |
| `nyaya_dhwani.keyword_boost` | `detect_section_references`, `boost_with_keywords` | Test keyword boosting |
| `nyaya_dhwani.llm_client` | `chat_completions`, `extract_assistant_text`, `rag_user_message` | MCQ and open-ended eval |
| `nyaya_dhwani.sarvam_client` | `translate_text` | Multilingual eval |
| `nyaya_dhwani.embedder` | `SentenceEmbedder` | FAISS embedding for comparison |
| `nyaya_dhwani.retrieval` | `CorpusIndex` | Direct FAISS access |

This ensures the benchmark tests the **exact same code paths** as the deployed app.

### Output format

Results are saved to a Delta table for tracking over time:

```
main.india_legal.benchmark_results
  ├── run_id (string) — timestamp + git commit
  ├── phase (string) — retrieval/mcq/open_ended/multilingual
  ├── backend (string) — faiss/vector_search
  ├── question_id (string)
  ├── metric (string) — recall, accuracy, keyword_coverage, etc.
  ├── value (double)
  └── details (string) — JSON with full result details
```

Summary metrics per run are displayed inline and optionally written to `main.india_legal.benchmark_summary`.

## Evaluation procedure

### Phase 1: Retrieval evaluation

For each question with `expected_chunks`:

```python
# FAISS
faiss_ret = FaissRetriever(FAISS_INDEX_DIR)
results = faiss_ret.search(question["question"], k=7)
retrieved_ids = set(results["chunk_id"].tolist())

# Vector Search
vs_ret = VectorSearchRetriever(VS_ENDPOINT, VS_INDEX)
vs_results = vs_ret.search(question["question"], k=7)
vs_retrieved_ids = set(vs_results["chunk_id"].tolist())

# Compute metrics
recall_faiss = len(retrieved_ids & expected) / len(expected)
recall_vs = len(vs_retrieved_ids & expected) / len(expected)
```

### Phase 2: MCQ evaluation

For each MCQ question:

```python
# Retrieve context
context_chunks = retriever.search(question["question"], k=7)
texts = context_chunks["text"].tolist()

# Format MCQ prompt
mcq_prompt = f"""Context:\n{chr(10).join(texts)}\n
Question: {question["question"]}
A) {question["options"]["a"]}
B) {question["options"]["b"]}
C) {question["options"]["c"]}
D) {question["options"]["d"]}

Answer with ONLY the letter (a, b, c, or d)."""

# Call LLM
from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text
response = chat_completions([
    {"role": "system", "content": "You are a legal exam assistant. Answer with only the letter."},
    {"role": "user", "content": mcq_prompt}
], max_tokens=10)
answer = extract_assistant_text(response).strip().lower()[:1]
correct = answer == question["correct_answer"]
```

### Phase 3: Open-ended evaluation

```python
# RAG answer (same as app)
from nyaya_dhwani.llm_client import rag_user_message
context = retriever.search(question["question"], k=7)
user_msg = rag_user_message(context["text"].tolist(), question["question"])
response = chat_completions([
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_msg}
], max_tokens=2048)
answer = extract_assistant_text(response)

# Check keyword coverage
expected_keywords = question["expected_in_answer"]
found = sum(1 for kw in expected_keywords if kw.lower() in answer.lower())
keyword_coverage = found / len(expected_keywords)
```

### Phase 4: Multilingual evaluation

```python
from nyaya_dhwani.sarvam_client import translate_text

# Test 1: Translate English question to Hindi, retrieve, compare results
en_question = "Which BNS Section replaces IPC Section 378?"
hi_question = translate_text(en_question, source_language_code="en-IN", target_language_code="hi-IN")

en_results = retriever.search(en_question, k=7)
# For Hindi: translate to English first (same as app pipeline), then retrieve
hi_to_en = translate_text(hi_question, source_language_code="hi-IN", target_language_code="en-IN")
hi_results = retriever.search(hi_to_en, k=7)

# Compare: do both retrieve the same chunks?
en_ids = set(en_results["chunk_id"].tolist())
hi_ids = set(hi_results["chunk_id"].tolist())
overlap = len(en_ids & hi_ids) / len(en_ids) if en_ids else 0

# Test 2: Full round-trip MCQ
# Hindi question → translate → retrieve → LLM → answer → compare to correct_answer
```

## Benchmark question sources

| Source | Status | How to get |
|--------|--------|-----------|
| Internal (`tests/benchmark_questions.json`) | Available | In repo, 20 questions |
| BhashaBench-Legal Criminal Law | Gated | Request access at HuggingFace, filter `topic="Criminal Law & Justice"`, save to `tests/bbl_criminal_law.json` |
| BhashaBench-Legal Hindi | Gated | Same dataset, `data_dir="Hindi"` |
| User-submitted questions | Manual | Collect from app usage logs (with consent) |

## Success criteria

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| Retrieval Recall@7 | 0.6 | 0.8 | 0.95 |
| MCQ accuracy (overall) | 0.5 | 0.7 | 0.85 |
| MCQ accuracy (mapping questions) | 0.7 | 0.9 | 1.0 |
| Keyword boost hit rate | 0.9 | 1.0 | 1.0 |
| Multilingual accuracy gap | < 20% | < 10% | < 5% |
| Hallucination rate | < 0.2 | < 0.1 | < 0.05 |

## Files to create

| File | What | Where it runs |
|------|------|---------------|
| `notebooks/run_benchmark.py` | Full evaluation notebook (all 4 phases) | Databricks cluster (Free Edition) |
| `tests/benchmark_questions.json` | Hand-crafted test questions | Read by notebook + local tests |
| `tests/bbl_criminal_law.json` | BhashaBench-Legal subset (after access) | Read by notebook |

## Future work

- **Automated CI integration:** run retrieval evaluation on every PR that changes the retriever or index
- **BhashaBench-Legal full suite:** once access is approved, run the full 2,769 Criminal Law questions
- **User feedback loop:** collect thumbs-up/down from the app UI, add to benchmark
- **Adversarial questions:** test edge cases (repealed sections, ambiguous mappings, questions about laws not in the corpus)
- **Latency benchmarks:** measure end-to-end response time for FAISS vs Vector Search across different query types
- **Track results over time:** query `main.india_legal.benchmark_results` Delta table to see how changes affect quality
