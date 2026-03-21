# nyaya-dhwani-hackathon

Databricks free edition experimental project for legal advice agent.

## Databricks Free Edition (use this repo with your workspace)

Authenticate the [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/) against this project’s workspace using a **dedicated profile** (here `free-aws`) so it does not clash with other `DEFAULT` profiles (e.g. Azure vs AWS).

```bash
databricks auth login --host https://dbc-6651e87a-25a5.cloud.databricks.com --profile free-aws
```

For any terminal session where you use the CLI or Python SDK with this workspace, select that profile:

```bash
export DATABRICKS_CONFIG_PROFILE=free-aws
```

Add the `export` line to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.) if you want it set automatically in new terminals.

Verify:

```bash
databricks current-user me
```

**Cursor / MCP:** [`.cursor/mcp.json`](.cursor/mcp.json) sets `DATABRICKS_CONFIG_PROFILE` to `free-aws` so the Databricks MCP server matches this workspace without shell exports.

## Workspace integration (secrets + Git)

Step-by-step for the Free Edition host: **[docs/WORKSPACE_SETUP.md](docs/WORKSPACE_SETUP.md)** (Databricks secret scope `nyaya-dhwani`, GitHub Repos, rotating keys).  
**Do not commit API keys or PATs** — see [docs/SECURITY.md](docs/SECURITY.md).

## Run and use

There is **no standalone HTTP app** in this repo yet (FastAPI/Gradio is [planned](docs/PLAN.md)). Today the “application” is a **Databricks notebook pipeline** plus an importable Python package for RAG building blocks.

### 1. One-time setup

- Complete [Databricks Free Edition](#databricks-free-edition-use-this-repo-with-your-workspace) and [Workspace integration](#workspace-integration-secrets--git).
- Add this repository in **Databricks → Repos** (clone from GitHub using a PAT in the UI — see [docs/WORKSPACE_SETUP.md](docs/WORKSPACE_SETUP.md)).
- In the workspace, create secrets under scope `nyaya-dhwani` (e.g. `sarvam_api_key`, `datagov_api_key`) or configure the same as **environment variables** on your cluster / serverless notebook.

### 2. Ingest data (Databricks notebook)

1. Open [`notebooks/india_legal_policy_ingest.ipynb`](notebooks/india_legal_policy_ingest.ipynb) from your **Repos** path (not only a stale workspace copy, unless you re-import from git).
2. Attach **compute** (cluster or serverless SQL/Spark as supported by your SKU).
3. Run cells **top to bottom** in order (install → config → Volume → sources → `legal_rag_corpus`).  
   - If `ai_parse_document` is unavailable on your runtime, rely on BNS CSV / `load_uploaded_file` paths documented in the notebook.
   - **Cell 9b (BNS PDF):** `ai_parse_document` returns **VARIANT**. The notebook stores **`to_json(...)` as `parsed_json` (STRING)** and parses with `from_json`, so Delta never keeps a VARIANT column for this step. If `doc.elements` is empty after the change, inspect one row: `display(spark.table("main.india_legal.bns_parsed_raw").selectExpr("substring(parsed_json,1,800)").limit(1))` and adjust the `StructType` in cell 9b to match the JSON keys returned by your runtime.
4. Confirm tables exist, e.g. `SHOW TABLES IN main.india_legal` and `SELECT COUNT(*) FROM main.india_legal.legal_rag_corpus`.

#### Data sources

Used by [`notebooks/india_legal_policy_ingest.ipynb`](notebooks/india_legal_policy_ingest.ipynb) (exact URLs and column handling are in the notebook):

- **`bns_sections`** — CSV on Unity Catalog Volume (e.g. uploaded `bns_sections.csv`); if the Volume file is missing, GitHub mirrors ([OpenNyAI `bns_sections.csv`](https://raw.githubusercontent.com/OpenNyAI/Opennyai/main/datasets/bns_sections.csv), [nandr39 `bns-dataset`](https://raw.githubusercontent.com/nandr39/bns-dataset/main/bns_sections.csv)); optional BNS 2023 gazette PDFs (MHA / India Code–style links in §3c) plus `ai_parse_document` when no CSV is available.
- **`bns_ipc_mapping`** — [nandhakumarg/IPC_and_BNS_transformation](https://huggingface.co/datasets/nandhakumarg/IPC_and_BNS_transformation) on Hugging Face (Apache-2.0). A small built-in stub is used only if that download fails.
- **Sarvam (optional)** — [Sarvam Chat API](https://api.sarvam.ai) (`sarvam-m`) for PDF-section enrichment and the §1b connectivity check; [dashboard](https://dashboard.sarvam.ai) for keys and access.

### 3. Build the vector index (Databricks notebook)

1. Open [`notebooks/build_rag_index.ipynb`](notebooks/build_rag_index.ipynb).
2. In the **first code cell**, set **`REPO_ROOT`** to your Repos checkout (Workspace sidebar → right-click the repo → **Copy path**). That cell installs **`faiss-cpu` 1.7.x**, **NumPy 1.x**, **pandas** below 3 (compatible with **`databricks-connect`**), then `pip install -e ...[rag,rag_embed]`. **faiss-cpu 1.8+** requires NumPy 2 (`numpy._core`), which conflicts with **databricks-connect** (expects `numpy<2`); the notebook pins **faiss-cpu** to 1.7.x and **numpy** to 1.x so both FAISS and Spark client libraries work.
3. Run **all cells in order** (install cell before any `from nyaya_dhwani...` import). This writes **`/Volumes/main/india_legal/legal_files/nyaya_index/`** containing `corpus.faiss`, `chunks.parquet`, and `manifest.json`.

If you see **`ModuleNotFoundError: No module named 'nyaya_dhwani'`**: set **`REPO_ROOT`** in the first code cell to the real path from **Copy path** (not the `<YOUR_EMAIL>` placeholder), run that cell until it prints `✅ import nyaya_dhwani`, then run the rest in order. Do not put **`%restart_python`** in the install cell — it restarts the kernel and breaks the run order; the notebook adds `src/` to `sys.path` so the package resolves even when `pip install -e` is flaky.

### 4. Use the Python package locally (optional)

From the repo root, install extras you need and import modules in a REPL or script:

```bash
cd /path/to/nyaya-dhwani-hackathon
python3 -m pip install -e ".[dev,rag,rag_embed]"   # rag_embed = sentence-transformers for embeddings
```

- **`nyaya_dhwani.retrieval.CorpusIndex`**: load the same `nyaya_index` directory if you copy it locally, or mount the Volume path in a future app.
- **`nyaya_dhwani.sarvam_client`**: set `SARVAM_API_KEY` (e.g. from a local [`.env`](.env.example) — never commit secrets) before calling `chat_completions`.

### 5. Roadmap: single “app” entrypoint

A **Databricks App** or **FastAPI** service that chains Sarvam STT → embed → FAISS search → LLM → Sarvam TTS is described in [docs/PLAN.md](docs/PLAN.md); it is not implemented in this branch. **Workspace probes** (MLflow, LLM, Apps) to run before adding code: [PLAN §8](docs/PLAN.md#8-build-sequence--verify-your-workspace-small-pieces).

---

## Testing

### Automated tests (`pytest`)

Install dev + RAG dependencies (FAISS tests need `rag`):

```bash
cd /path/to/nyaya-dhwani-hackathon
python3 -m pip install -e ".[dev,rag]"
python3 -m pytest tests/ -v
```

| Command | What it exercises |
|---------|-------------------|
| `pytest tests/ -q` | Full suite (quiet) |
| `pytest tests/test_text_utils.py -v` | Column cleaning (`text_utils.clean_cols`) |
| `pytest tests/test_manifest.py -v` | `RAGManifest` JSON round-trip |
| `pytest tests/test_index_faiss.py -v` | FAISS save/load + `CorpusIndex.search` (requires `faiss-cpu`) |
| `pytest -k manifest` | Any test whose name contains `manifest` |

Embedding-model tests are not separate files yet; FAISS roundtrip uses **random normalized vectors** (no download). To run tests that need **sentence-transformers**, install `rag_embed` and use the manual checks below.

### Manual / component checks

Run from the repo root with `PYTHONPATH=src` or after `pip install -e .`.

**`text_utils`**

```bash
python3 -c "import pandas as pd; from nyaya_dhwani.text_utils import clean_cols; print(clean_cols(pd.DataFrame([{'A B': 1}])).columns.tolist())"
```

**`manifest`**

```bash
python3 -c "from nyaya_dhwani.manifest import RAGManifest, utc_now_iso; print(RAGManifest(embedding_model='m', embedding_dim=384, faiss_index_file='x', chunks_parquet_file='y', num_vectors=1, catalog='c', schema='s', source_table='t', created_at_utc=utc_now_iso()).to_json()[:80])"
```

**`sarvam_client` (calls Sarvam — needs `SARVAM_API_KEY`)**

```bash
export SARVAM_API_KEY="your-key"   # or: source .env
python3 -c "
from nyaya_dhwani.sarvam_client import chat_completions, extract_message_text
r = chat_completions([{'role':'user','content':'Say OK in one word.'}], max_tokens=20)
print(extract_message_text(r))
"
```

**`embedder` + `retrieval` (needs `pip install -e \".[rag_embed]\"` and optional small index)**

After you have run [`notebooks/build_rag_index.ipynb`](notebooks/build_rag_index.ipynb), copy `nyaya_index` to a local folder or point `CorpusIndex.load()` at a path you can read:

```bash
python3 -c "
from nyaya_dhwani.embedder import SentenceEmbedder
from nyaya_dhwani.retrieval import CorpusIndex
# INDEX_DIR = '/path/to/nyaya_index'  # local copy of Volume output
# e = SentenceEmbedder(); q = e.encode(['theft under BNS'])
# ci = CorpusIndex.load(INDEX_DIR); print(ci.search(q, k=3))
print('Set INDEX_DIR to a folder with manifest.json + corpus.faiss + chunks.parquet')
"
```

Uncomment the middle lines when `INDEX_DIR` is valid.

---

## Repository layout

| Path | Purpose |
|------|---------|
| [`notebooks/india_legal_policy_ingest.ipynb`](notebooks/india_legal_policy_ingest.ipynb) | Legal/policy ingestion → Delta tables + `legal_rag_corpus` |
| [`notebooks/build_rag_index.ipynb`](notebooks/build_rag_index.ipynb) | Embeddings + FAISS + `manifest.json` on UC Volume (`.../nyaya_index/`) |
| [`src/nyaya_dhwani/`](src/nyaya_dhwani/) | Package: `text_utils`, `embedder`, `index_builder`, `retrieval`, `manifest`, `sarvam_client` |
| [`tests/`](tests/) | `pytest` — see [Testing](#testing) |
| [`docs/PLAN.md`](docs/PLAN.md) | Product plan |

**Databricks secrets (recommended):** create scope `nyaya-dhwani` with keys `datagov_api_key` and `sarvam_api_key`, or set env vars on the cluster/job. Copy [`.env.example`](.env.example) to `.env` for local dev only (never commit `.env`).

Full ingestion runs **in the workspace** (cluster or serverless) with Spark, Unity Catalog, and optional `ai_parse_document`.

## Databricks AI Dev Kit

This repo is configured with the [Databricks AI Dev Kit](https://github.com/databricks-solutions/ai-dev-kit) (project-scoped install): MCP tools under `~/.ai-dev-kit`, Cursor skills and MCP config under [`.cursor/`](.cursor/), and install metadata under [`.ai-dev-kit/`](.ai-dev-kit/).

### Prerequisites

- [uv](https://github.com/astral-sh/uv) (or `pip` / `pip3`) for the MCP server virtualenv
- [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/) for authentication and workspace commands
- Open this folder in Cursor from this path so project-level config is picked up

### Install or refresh

From the repository root (interactive prompts):

```bash
bash <(curl -sL https://raw.githubusercontent.com/databricks-solutions/ai-dev-kit/main/install.sh)
```

Non-interactive example (Cursor only, default `DEFAULT` profile, all skills):

```bash
bash <(curl -sL https://raw.githubusercontent.com/databricks-solutions/ai-dev-kit/main/install.sh) --tools cursor --silent
```

See the [install section](https://github.com/databricks-solutions/ai-dev-kit?tab=readme-ov-file#install-in-existing-project) for `--global`, `--skills-profile`, `--force`, and other options.

### After install

1. In Cursor: **Settings → Cursor Settings → Tools & MCP** and enable the **databricks** MCP server (it may be deferred until loaded).
2. Authenticate for this workspace: follow [Databricks Free Edition](#databricks-free-edition-use-this-repo-with-your-workspace) (`free-aws` + `export DATABRICKS_CONFIG_PROFILE=free-aws`), or use `databricks auth login --profile DEFAULT` if your MCP config still points at `DEFAULT`.
