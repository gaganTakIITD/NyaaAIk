# Benchmark Evaluation Plan

## Overview

This document describes how to evaluate Nyaya Dhwani's RAG pipeline quality using benchmark questions. The evaluation measures **retrieval accuracy** (does the system find the right chunks?) and **answer quality** (does the LLM produce correct answers?) across languages.

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

**How to run:**

```python
# Pseudocode for retrieval evaluation
from nyaya_dhwani.retriever import get_retriever
retriever = get_retriever()

for q in benchmark["questions"]:
    if "expected_chunks" not in q:
        continue
    results = retriever.search(q["question"], k=7)
    retrieved_ids = set(results["chunk_id"].tolist())
    expected_ids = set(q["expected_chunks"])
    recall = len(retrieved_ids & expected_ids) / len(expected_ids)
    # ... compute MRR
```

**Compare backends:** run the same queries against FAISS (`NYAYA_RETRIEVAL_BACKEND=faiss`) and Vector Search (`=vector_search`) to compare retrieval quality.

### Dimension 2: Answer accuracy (MCQ)

**What we measure:** does the LLM select the correct answer given retrieved context?

| Metric | Definition | Target |
|--------|-----------|--------|
| **MCQ accuracy** | Fraction of questions answered correctly | > 0.7 |
| **Accuracy by difficulty** | Breakdown by easy/medium/hard | Easy > 0.85, Medium > 0.65, Hard > 0.5 |
| **Accuracy by category** | Breakdown by question category | Mapping > 0.8, Knowledge > 0.7 |

**How to run:**

For each MCQ question:
1. Format as: `"Question: {question}\nA) {a}\nB) {b}\nC) {c}\nD) {d}\nAnswer with the letter only."`
2. Prepend RAG context from retriever
3. Call LLM, extract the letter
4. Compare to `correct_answer`

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

## Evaluation procedure

### Phase 1: Retrieval evaluation (automated)

```bash
# Run against internal benchmark
python tests/run_benchmark.py --mode retrieval --backend faiss
python tests/run_benchmark.py --mode retrieval --backend vector_search
```

Output: recall@k, MRR, keyword boost hit rate for each backend.

### Phase 2: MCQ evaluation (automated)

```bash
# Internal benchmark MCQ questions
python tests/run_benchmark.py --mode mcq --backend vector_search

# BhashaBench-Legal Criminal Law subset (after access approval)
python tests/run_benchmark.py --mode mcq --dataset tests/bbl_criminal_law.json
```

Output: accuracy by difficulty, category, and language.

### Phase 3: Open-ended evaluation (semi-automated)

```bash
python tests/run_benchmark.py --mode open_ended
```

Output: keyword coverage and citation accuracy (automated), plus generated answers for manual review.

### Phase 4: Multilingual evaluation (automated)

```bash
python tests/run_benchmark.py --mode multilingual
```

Runs Hindi and Kannada questions, compares answers to English equivalents.

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

## Future work

- **Automated CI integration:** run retrieval evaluation on every PR that changes the retriever or index
- **BhashaBench-Legal full suite:** once access is approved, run the full 2,769 Criminal Law questions
- **User feedback loop:** collect thumbs-up/down from the app UI, add to benchmark
- **Adversarial questions:** test edge cases (repealed sections, ambiguous mappings, questions about laws not in the corpus)
- **Latency benchmarks:** measure end-to-end response time for FAISS vs Vector Search across different query types
