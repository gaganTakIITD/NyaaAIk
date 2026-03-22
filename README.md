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

### 5. API keys, tokens, and secrets

The app needs credentials for the **LLM** (Databricks AI Gateway) and optionally **Sarvam** (STT, translation, TTS). How you provide them depends on whether you run locally or as a Databricks App.

#### Environment variables reference

| Variable | Required? | What it does | Where to get it |
|----------|-----------|--------------|-----------------|
| `LLM_OPENAI_BASE_URL` | Yes | AI Gateway base URL (OpenAI-compatible) | Playground → **Get code** → `base_url`. This repo uses `https://7474650313055161.ai-gateway.cloud.databricks.com/mlflow/v1` |
| `LLM_MODEL` | Yes | Model id for chat completions | Playground → **Get code** → model name. This repo uses `databricks-llama-4-maverick` |
| `DATABRICKS_TOKEN` | Local only | PAT or token from **Get code** | Workspace → **User Settings → Developer → Access tokens**. **Not needed on Databricks Apps** — see below |
| `SARVAM_API_KEY` | Optional | Sarvam REST API key (STT, Mayura translate, Bulbul TTS) | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `NYAYA_INDEX_DIR` | Yes | Path to the FAISS index directory | Output of [`notebooks/build_rag_index.ipynb`](notebooks/build_rag_index.ipynb), default `/Volumes/main/india_legal/legal_files/nyaya_index` |
| `LLM_CHAT_COMPLETIONS_URL` | No | Full POST URL override (skips base URL + `/chat/completions` construction) | Only if your endpoint doesn't follow the OpenAI `/v1/chat/completions` pattern |

#### Local development

Copy [`.env.example`](.env.example) to `.env`, fill in values, and source it (or use a tool like `direnv`). **Never commit `.env`**.

```bash
cp .env.example .env
# Edit .env with your values, then:
export $(grep -v '^#' .env | xargs)

# Smoke test:
python3 -c "
from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text
r = chat_completions([{'role':'user','content':'Reply with one word: OK.'}], max_tokens=32)
print(extract_assistant_text(r))
"
```

#### Databricks Apps deployment

On Databricks Apps, credentials work differently from local dev:

**LLM authentication (no PAT needed):** Databricks Apps runs your code as a **service principal**. The app uses `databricks-sdk` (`WorkspaceClient()`) to get an OAuth token automatically — you do **not** need to set `DATABRICKS_TOKEN`. The service principal must have **CAN_QUERY** permission on the AI Gateway endpoint (grant this in the workspace UI under the endpoint's permissions).

**Secrets vs. plain env vars:** Databricks Apps supports two ways to pass env vars in [`app.yaml`](app.yaml):

```yaml
env:
  # Plain value — visible in app.yaml (fine for non-secret config)
  - name: "LLM_OPENAI_BASE_URL"
    value: "https://7474650313055161.ai-gateway.cloud.databricks.com/mlflow/v1"

  # Secret — references a Databricks secret resource (for API keys)
  - name: "SARVAM_API_KEY"
    valueFrom: "sarvam_api_key"       # resource name in the app config
```

**Setting up the secret resource (step-by-step):**

Databricks Apps secret resources require **three things** to line up. If any one is missing, the env var will be empty at runtime.

**Step 1 — Store the secret in the workspace:**

```bash
databricks secrets create-scope nyaya-dhwani          # one-time (skip if scope exists)
databricks secrets put-secret nyaya-dhwani sarvam_api_key
# paste the API key when prompted
```

**Step 2 — Add a secret resource in the app UI:**

Go to **Compute → Apps → your app → Settings → Resources** and add:

| Field | Value | Must match |
|-------|-------|------------|
| **Resource key** | `sarvam_api_key` | `valueFrom` in `app.yaml` |
| **Resource type** | Secret | — |
| **Secret scope** | `nyaya-dhwani` | scope from Step 1 |
| **Secret key** | `sarvam_api_key` | key from Step 1 |

**Step 3 — Map the resource to an env var in `app.yaml`:**

```yaml
env:
  - name: "SARVAM_API_KEY"        # env var name your code reads
    valueFrom: "sarvam_api_key"   # must match resource key from Step 2
```

**Step 4 — Redeploy** the app so the new env mapping takes effect.

**Verification:** if the app logs still show `SARVAM_API_KEY missing`, check:
- The resource key in the app UI **exactly** matches `valueFrom` in `app.yaml` (case-sensitive)
- The secret scope and key exist: `databricks secrets list-secrets nyaya-dhwani`
- You redeployed after adding/changing the resource

**Current [`app.yaml`](app.yaml) configuration:**

| Env var | Source | Notes |
|---------|--------|-------|
| `SARVAM_API_KEY` | `valueFrom: "sarvam_api_key"` (secret resource) | Optional — app works without Sarvam but voice/translation/TTS is disabled |
| `LLM_OPENAI_BASE_URL` | `value:` (plain) | AI Gateway URL — change if your workspace id differs |
| `LLM_MODEL` | `value:` (plain) | Model name on the AI Gateway |
| `DATABRICKS_TOKEN` | *not needed* | Databricks Apps uses OAuth M2M via the service principal — see below |

**LLM authentication on Databricks Apps:** The app calls `WorkspaceClient().config.authenticate()` from the `databricks-sdk` to get a short-lived OAuth token. This happens automatically — no PAT or `DATABRICKS_TOKEN` is needed. The service principal must have **CAN_QUERY** on the AI Gateway serving endpoint.

**Common mistakes:**

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Secret resource exists but no `env` mapping in `app.yaml` | `SARVAM_API_KEY missing` in logs | Add `name`/`valueFrom` entry in `app.yaml` and redeploy |
| Resource key doesn't match `valueFrom` | Same as above | Keys are case-sensitive — check both match exactly |
| Forgot to redeploy after adding resource | Same as above | Redeploy from the app UI |
| Set `DATABRICKS_TOKEN` as a static PAT | Works initially, then expires | Remove it — use SDK OAuth instead (no config needed) |

#### UC Volumes are not mounted in Databricks Apps

This is a critical difference between **notebooks/clusters** and **Databricks Apps** that catches many developers:

- **On a cluster or notebook**, Unity Catalog Volumes are FUSE-mounted at `/Volumes/<catalog>/<schema>/<volume>/...`. You can read files with `open()`, `pathlib.Path`, or any library that expects local paths.
- **On Databricks Apps**, UC Volumes are **not** FUSE-mounted. The path `/Volumes/main/india_legal/legal_files/nyaya_index/manifest.json` simply does not exist on the filesystem. You get `FileNotFoundError: [Errno 2] No such file or directory`.

**How this app handles it:** [`app/main.py`](app/main.py) detects when a `/Volumes/...` path doesn't exist locally and **downloads the index files at startup** using the Databricks SDK's Files API:

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()  # uses the app's service principal — no PAT needed
for item in w.files.list_directory_contents("/Volumes/main/india_legal/legal_files/nyaya_index"):
    with w.files.download(item.path).contents as src:
        # write to /tmp/nyaya_index/...
```

The downloaded files are cached in `/tmp/nyaya_index` so subsequent requests don't re-download. The service principal must have **READ** permission on the UC Volume.

**For other developers building Databricks Apps that read files from UC Volumes:** you must use the SDK (`WorkspaceClient().files`) or the REST API to access Volume contents. Direct filesystem paths will not work. Alternatives:
1. **SDK download at startup** (this app's approach) — best for small/medium files (index, config, models) that can be cached in `/tmp`
2. **Bundle files in the repo** — if the files are small enough and not sensitive
3. **SDK streaming** — read files on demand without caching (for large files or infrequent access)
4. **Use a SQL warehouse** — query data via `databricks-sql-connector` instead of reading files

Full detail and RAG message shape: **[docs/PLAYGROUND_TO_APP.md](docs/PLAYGROUND_TO_APP.md)**.

#### End-to-end MVP snippet (retrieve + generate)

Run where the index path is readable and `rag` + `rag_embed` are installed. Use the **same** embedding model id as in `manifest.json` (pass `SentenceEmbedder(model_name=...)` if you overrode the default at index build).

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

> **Databricks Apps + Gradio** — Official **Gradio on Databricks Apps** samples and dependency patterns are in **[`databricks/app-templates`](https://github.com/databricks/app-templates)** (for example [`gradio-hello-world-app`](https://github.com/databricks/app-templates/tree/main/gradio-hello-world-app), plus [`gradio-chatbot-app`](https://github.com/databricks/app-templates/tree/main/gradio-chatbot-app) / [`gradio-data-app`](https://github.com/databricks/app-templates/tree/main/gradio-data-app)). This repo aligns with those templates: root [`requirements.txt`](requirements.txt) pins **`gradio~=4.44.0`**, **`huggingface-hub~=0.35.3`**, **`pandas~=2.2.3`**, and **`gradio-client==1.3.0`** (same minor line as Gradio 4.44.x). **[`app.yaml`](app.yaml)** sets the command to `python app/main.py`.

#### Gradio + Databricks Apps integration challenges

Deploying a Gradio app with a **`gr.Chatbot`** component on Databricks Apps required solving two intertwined issues:

1. **`gradio-client` 1.3.0 `get_api_info()` crash with `gr.Chatbot`** — The `gr.Chatbot` component (default tuple format) produces a JSON schema with `additionalProperties: true` (a JSON Schema boolean). The `gradio-client` 1.3.0 function `_json_schema_to_python_type` does not handle boolean schemas — it recurses into `True`, eventually calling `”const” in True` (`TypeError: argument of type 'bool' is not iterable`) or raising `APIInfoParseError: Cannot parse schema True`. This crash happens inside Gradio's built-in `GET /` route handler (`gradio/routes.py:api_info`), which is called even when `show_api=False`.

2. **Gradio localhost health-check → `ValueError: When localhost is not accessible`** — During `demo.launch()`, Gradio sends a `HEAD http://localhost:<port>/` to verify the server started. Because the `get_api_info()` crash above causes that route to return `HTTP 500`, the health check fails repeatedly, and Gradio raises `ValueError: When localhost is not accessible, a shareable link must be created. Please set share=True`. The app never starts.

**How we solved it:**

- **Monkey-patch `_json_schema_to_python_type` and `get_type`** in `gradio_client.utils` at import time ([`app/main.py`](app/main.py), top of file). The patch replaces both functions at module level so that all recursive calls are also guarded — if `schema` is not a `dict` (e.g. `True`), it returns `”Any”` instead of crashing. This fixes the `GET /` route, making the health check return `200 OK`.

- **Bare `demo.launch()` with no arguments** — all four official Databricks app-templates ([`gradio-hello-world-app`](https://github.com/databricks/app-templates/tree/main/gradio-hello-world-app), [`gradio-chatbot-app`](https://github.com/databricks/app-templates/tree/main/gradio-chatbot-app), [`gradio-data-app`](https://github.com/databricks/app-templates/tree/main/gradio-data-app), [`gradio-data-app-obo-user`](https://github.com/databricks/app-templates/tree/main/gradio-data-app-obo-user)) call `demo.launch()` with **zero parameters**. The Databricks Apps platform injects the correct server configuration via environment variables (`GRADIO_SERVER_NAME`, `GRADIO_SERVER_PORT`, etc.). Explicitly setting `server_name=”0.0.0.0”`, `server_port`, or `root_path` conflicts with the platform — for example, `root_path=”/”` causes Gradio to add redirect middleware that turns the health check `HEAD /` into a `307 Temporary Redirect`, which Gradio also treats as “localhost not accessible”.

- **Tuple-format chat history** — `gr.Chatbot` defaults to `type=”tuples”` (pairs of `[user, assistant]`). The alternative `type=”messages”` (OpenAI-style dicts) produces an even more complex JSON schema that also triggers the `gradio-client` bug. Sticking with tuples keeps the schema simpler, and the monkey-patch handles the remaining `additionalProperties: true` edge case.

> **Note:** the `gradio-chatbot-app` template avoids this bug entirely by using `gr.ChatInterface` (which internally uses a simpler schema) rather than a raw `gr.Chatbot` inside `gr.Blocks`. If you only need a basic chat UI, `gr.ChatInterface` is the safer choice on Gradio 4.44.x + `gradio-client` 1.3.0.

**Install** (from repo root): `pip install -r requirements-app.txt` or `pip install -e “.[rag,rag_embed,app]”`.

**Run locally** (index path + LLM env from Playground **Get code**; add Sarvam for voice/translate/TTS):

```bash
export NYAYA_INDEX_DIR=”/Volumes/main/india_legal/legal_files/nyaya_index”   # or local copy
export LLM_OPENAI_BASE_URL=”https://<workspace-id>.ai-gateway.cloud.databricks.com/mlflow/v1”
export LLM_MODEL=”databricks-llama-4-maverick”
export DATABRICKS_TOKEN=”dapi…”
export SARVAM_API_KEY=”…”   # optional: STT, Mayura, Bulbul (see PLAYGROUND_TO_APP)
python app/main.py
```

**Deploy** on the workspace: **Compute → Apps → Create** → connect this Git repo → configure secrets and env as described in [§5 API keys, tokens, and secrets](#5-api-keys-tokens-and-secrets). The app's service principal needs:
- **CAN_QUERY** on the AI Gateway endpoint (for LLM calls)
- **READ** on the UC Volume `main.india_legal.legal_files` (for index download — see [§5 UC Volumes](#uc-volumes-are-not-mounted-in-databricks-apps))

Full flow: [docs/PLAN.md](docs/PLAN.md#deploy-the-app-git-connected).

**Entry point:** the repo includes **[`app.yaml`](app.yaml)** so Databricks runs `python app/main.py`. Without it, the default is `python app.py` in the repo root, which does not exist here — the app stays **Unavailable** with little logging. **`requirements.txt`** at the repo root is required for the Apps build step (`pip install -r requirements.txt`); it installs this package with RAG + Gradio extras.

**Troubleshooting “Unavailable” / “No source code”**

| Issue | What to do |
|-------|------------|
| Wrong Git URL | Use the exact repo URL (e.g. `https://github.com/shwethab/nyaya-dhwani-hackathon`) — avoid a truncated URL ending in `-`. |
| No deployment | After fixing Git or adding `app.yaml`, **Save** and **Deploy** (or redeploy) so a new build runs. |
| `SARVAM_API_KEY` not set despite secret existing | The secret resource must be mapped in [`app.yaml`](app.yaml) via `valueFrom` — see [§5](#5-api-keys-tokens-and-secrets). A secret in the workspace is not automatically an env var. |
| LLM auth fails on Databricks Apps | The service principal needs **CAN_QUERY** on the AI Gateway endpoint. `DATABRICKS_TOKEN` is not needed — the app uses `databricks-sdk` OAuth. See [§5](#5-api-keys-tokens-and-secrets). |
| LLM auth fails locally | Set `DATABRICKS_TOKEN` (PAT), `LLM_OPENAI_BASE_URL`, and `LLM_MODEL` in `.env` — see [§5](#5-api-keys-tokens-and-secrets). |
| `FileNotFoundError: /Volumes/.../manifest.json` | UC Volumes are **not** FUSE-mounted in Databricks Apps. The app auto-downloads from the Volume via the SDK. Ensure the service principal has **READ** on the Volume. See [§5 UC Volumes](#uc-volumes-are-not-mounted-in-databricks-apps). |
| `ImportError: HfFolder` from `huggingface_hub` | Pin **`huggingface-hub~=0.35.3`** with **`gradio~=4.44.0`** (see `requirements.txt` — matches the Databricks template). A newer hub (from unpinned installs) removes `HfFolder` while Gradio 4.44 still imports it. Redeploy after pull. |
| `APIInfoParseError: Cannot parse schema True` or `TypeError: argument of type 'bool' is not iterable` on startup | Bug in `gradio-client` 1.3.0 when `gr.Chatbot` is used inside `gr.Blocks`. The monkey-patch in [`app/main.py`](app/main.py) fixes this. If you see this error, ensure you are running the latest code from `main`. |
| `ValueError: When localhost is not accessible` | Caused by the `get_api_info()` crash above making the health check return 500. Fix the schema bug (monkey-patch) and use bare `demo.launch()` with no arguments — do **not** set `server_name`, `server_port`, or `root_path` explicitly. |

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
