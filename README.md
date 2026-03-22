# nyaya-dhwani-hackathon

Databricks Free Edition project: **ingest Indian legal/policy text → FAISS RAG on a Unity Catalog Volume → Gradio app** with **Databricks Llama Maverick** (AI Gateway) and optional **Sarvam** (Mayura translate, Saaras STT, Bulbul TTS). Not legal advice — see [docs/UI_design.md](docs/UI_design.md) disclaimers.

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

The hackathon **MVP** in this repo is: **ingest → build a FAISS index on a Volume → retrieve chunks → call an OpenAI-compatible LLM** (Databricks Playground **Get code** / AI Gateway or another provider). The **Gradio** app lives at [`app/main.py`](app/main.py) — deploy it as a **Databricks App** from this Git repo ([docs/PLAN.md](docs/PLAN.md#deploy-the-app-git-connected)).

### MVP (latest): try in this order

| Step | What | Where |
|------|------|--------|
| 1 | Auth, Repos, secrets (`nyaya-dhwani`) | [One-time setup](#1-one-time-setup), [WORKSPACE_SETUP](docs/WORKSPACE_SETUP.md) |
| 2 | Ingest → `main.india_legal.legal_rag_corpus` | [`notebooks/india_legal_policy_ingest.ipynb`](notebooks/india_legal_policy_ingest.ipynb) |
| 3 | Embeddings + FAISS + `manifest.json` on Volume | [`notebooks/build_rag_index.ipynb`](notebooks/build_rag_index.ipynb) |
| 4 | Confirm index + `CorpusIndex.search` | Last cells of `build_rag_index` (smoke) or [local optional](#4-use-the-python-package-locally-optional) |
| 5 | Programmatic LLM (same URL/model as Playground **Get code**) | [LLM from env](#5-llm-call-playground--ai-gateway-parity), [PLAYGROUND_TO_APP](docs/PLAYGROUND_TO_APP.md) |
| 6 | Glue RAG + LLM | Notebook: [PLAN §2](docs/PLAN.md#2-query-path-runtime); **or** [`app/main.py`](app/main.py) + [§6 Gradio app](#6-gradio-app-databricks-apps) |

Until step **4** passes, fix FAISS/NumPy pins per [§3](#3-build-the-vector-index-databricks-notebook) before investing in the app layer.

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
- **`nyaya_dhwani.sarvam_client`**: set `SARVAM_API_KEY` before `chat_completions`, `translate_text`, `speech_to_text_file`, or `text_to_speech_wav_bytes` (e.g. from a local [`.env`](.env.example) — never commit secrets).
- **`nyaya_dhwani.llm_client`**: OpenAI-compatible **`chat_completions()`** (`requests`) for Databricks **AI Gateway** / Playground **Get code**; optional **`complete_with_openai_sdk()`** after `pip install -e ".[llm_openai]"`. Env vars: see [§5](#5-llm-call-playground--ai-gateway-parity) and [`.env.example`](.env.example).

### 5. LLM call (Playground / AI Gateway parity)

After **Playground** works for you, use **Get code** to copy `base_url`, model id, and token pattern. Map them to env (Databricks **Secrets** on jobs/apps, or local `.env` only — never commit):

| Variable | Typical use |
|----------|-------------|
| `DATABRICKS_TOKEN` | PAT or token from Get code |
| `LLM_OPENAI_BASE_URL` | Same as SDK `base_url`, e.g. `https://<workspace-id>.ai-gateway.cloud.databricks.com/mlflow/v1` (no trailing slash) |
| `LLM_MODEL` | e.g. `databricks-llama-4-maverick` or the model id from Get code |

Full detail and RAG message shape: **[docs/PLAYGROUND_TO_APP.md](docs/PLAYGROUND_TO_APP.md)**.

**Smoke test (local or notebook, after `pip install -e .`):**

```bash
export DATABRICKS_TOKEN="dapi…"
export LLM_OPENAI_BASE_URL="https://<workspace-id>.ai-gateway.cloud.databricks.com/mlflow/v1"
export LLM_MODEL="databricks-llama-4-maverick"
python3 -c "
from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text
r = chat_completions([{'role':'user','content':'Reply with one word: OK.'}], max_tokens=32)
print(extract_assistant_text(r))
"
```

**End-to-end MVP snippet (retrieve + generate)** — run where the index path is readable and `rag` + `rag_embed` are installed. Use the **same** embedding model id as in `manifest.json` (pass `SentenceEmbedder(model_name=...)` if you overrode the default at index build).

```python
from nyaya_dhwani.embedder import SentenceEmbedder
from nyaya_dhwani.retrieval import CorpusIndex
from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text, rag_user_message

INDEX_DIR = "/Volumes/main/india_legal/legal_files/nyaya_index"  # or a local copy
q = "What is theft under BNS?"
e = SentenceEmbedder()  # must match manifest embedding_model
ci = CorpusIndex.load(INDEX_DIR)
chunks = ci.search(e.encode([q]), k=5)
texts = chunks["text"].tolist()
msg = rag_user_message(texts, q)
r = chat_completions([{"role": "user", "content": msg}], max_tokens=2048)
print(extract_assistant_text(r))
```

(Add a system message with a **not legal advice** disclaimer in production.)

### 6. Gradio app (Databricks Apps)

In-repo entrypoint: [`app/main.py`](app/main.py) — welcome + language, topic chips, chat with **retrieve → Llama Maverick** (`llm_client`) + citations + disclaimer. Optional **Sarvam** (same `SARVAM_API_KEY` as notebooks): **mic → STT** (Saaras, default `translate` mode for English retrieval), **Mayura** to translate typed questions to English for embedding/RAG and answers back to the session language, **Bulbul TTS** when “Read answer aloud” is checked. UI spec: [docs/UI_design.md](docs/UI_design.md).

**Install** (from repo root): `pip install -r requirements-app.txt` or `pip install -e ".[rag,rag_embed,app]"`.

**Run locally** (index path + LLM env from Playground **Get code**; add Sarvam for voice/translate/TTS):

```bash
export NYAYA_INDEX_DIR="/Volumes/main/india_legal/legal_files/nyaya_index"   # or local copy
export LLM_OPENAI_BASE_URL="https://<workspace-id>.ai-gateway.cloud.databricks.com/mlflow/v1"
export LLM_MODEL="databricks-llama-4-maverick"
export DATABRICKS_TOKEN="dapi…"
export SARVAM_API_KEY="…"   # optional: STT, Mayura, Bulbul (see PLAYGROUND_TO_APP)
python app/main.py
```

**Deploy** on the workspace: **Compute → Apps → Create** → connect this Git repo → set env per [docs/PLAYGROUND_TO_APP.md](docs/PLAYGROUND_TO_APP.md) (LLM + optional `SARVAM_API_KEY` + Volume read for the index). Full flow: [docs/PLAN.md](docs/PLAN.md#deploy-the-app-git-connected).

**Entry point:** the repo includes **[`app.yaml`](app.yaml)** so Databricks runs `python app/main.py`. Without it, the default is `python app.py` in the repo root, which does not exist here — the app stays **Unavailable** with little logging. **`requirements.txt`** at the repo root is required for the Apps build step (`pip install -r requirements.txt`); it installs this package with RAG + Gradio extras.

**Troubleshooting “Unavailable” / “No source code”**

| Issue | What to do |
|-------|------------|
| Wrong Git URL | Use the exact repo URL (e.g. `https://github.com/shwethab/nyaya-dhwani-hackathon`) — avoid a truncated URL ending in `-`. |
| No deployment | After fixing Git or adding `app.yaml`, **Save** and **Deploy** (or redeploy) so a new build runs. |
| Secret env name | Map the Sarvam secret so the app receives **`SARVAM_API_KEY`** (resource key / env name your workspace uses for that value). |
| LLM env | Set `DATABRICKS_TOKEN`, `LLM_OPENAI_BASE_URL`, `LLM_MODEL` in app env or secrets. |
| `ImportError: HfFolder` from `huggingface_hub` | Needs **Gradio ≥ 5.50** (`requirements.txt` installs it before the package). Confirm the App’s Git branch has the latest commit, then redeploy. If it persists, the build may be using a cached env — trigger a clean rebuild. |

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
| `pytest tests/test_llm_client.py -v` | `llm_client` URL helpers + RAG message helpers (no network) |
| `pytest tests/test_sarvam_client.py -v` | Sarvam translation JSON parsing + WAV round-trip (no network) |
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
| [`src/nyaya_dhwani/`](src/nyaya_dhwani/) | Package: `text_utils`, `embedder`, `index_builder`, `retrieval`, `manifest`, `sarvam_client`, `llm_client` |
| [`app/main.py`](app/main.py) | Gradio Databricks App (RAG + Maverick + optional Sarvam) |
| [`requirements.txt`](requirements.txt) | Databricks Apps `pip install` (same content as `requirements-app.txt`) |
| [`app.yaml`](app.yaml) | Declares `python app/main.py` for Databricks Apps (overrides default `python app.py`) |
| [`requirements-app.txt`](requirements-app.txt) | Alias / local installs: `pip install -r requirements-app.txt` |
| [`docs/PLAYGROUND_TO_APP.md`](docs/PLAYGROUND_TO_APP.md) | Playground **Get code** → env vars → App (LLM + Sarvam) |
| [`docs/UI_design.md`](docs/UI_design.md) | UI/UX and Sarvam pipeline spec |
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
