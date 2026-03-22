# Developer Guide — Deploying Nyaya Dhwani on Databricks Apps

This guide covers everything a developer needs to deploy and operate the Nyaya Dhwani app on Databricks. It documents the pitfalls we encountered and the solutions we found, so you don't have to repeat them.

## Prerequisites

- A Databricks workspace (Free Edition works for notebooks + FAISS; Apps requires a workspace that supports Databricks Apps)
- [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/) installed and authenticated
- A Sarvam API key (optional, for multilingual support) — get one at [dashboard.sarvam.ai](https://dashboard.sarvam.ai)

## Quick start (deployment checklist)

| Step | What | Command / Action |
|------|------|------------------|
| 1 | Auth CLI | `databricks auth login --host https://<workspace>.cloud.databricks.com --profile free-aws` |
| 2 | Create secret scope | `databricks secrets create-scope nyaya-dhwani` |
| 3 | Store Sarvam key | `databricks secrets put-secret nyaya-dhwani sarvam_api_key` |
| 4 | Run ingest notebook | `notebooks/india_legal_policy_ingest.ipynb` on a cluster |
| 5 | Build FAISS index | `notebooks/build_rag_index.ipynb` on a cluster |
| 6 | Create Databricks App | **Compute → Apps → Create** → connect Git repo |
| 7 | Grant permissions | Service principal needs: CAN_QUERY on AI Gateway, READ on Volume, READ on secret scope |
| 8 | Deploy | Click Deploy in the Apps UI |

## Authentication and secrets

### LLM authentication (Databricks AI Gateway)

**On Databricks Apps (no PAT needed):** the app runs as a **service principal** with OAuth M2M. It calls `WorkspaceClient().config.authenticate()` from `databricks-sdk` to get a short-lived token. The service principal must have **CAN_QUERY** on the AI Gateway endpoint.

**Locally:** set `DATABRICKS_TOKEN` (a PAT from **User Settings → Developer → Access tokens**).

**What we learned:**
- `WorkspaceClient().config.token` is `None` for OAuth M2M — it only works for PAT auth
- `config.authenticate()` takes **no arguments** and returns a `dict` with `{"Authorization": "Bearer <token>"}` — not a callable factory (despite older SDK docs suggesting otherwise)
- The token is short-lived and refreshed automatically on each call

### Sarvam API key

**On Databricks Apps:** the app loads the key from the workspace secret scope at startup:

```python
w = WorkspaceClient()
val = w.secrets.get_secret(scope="nyaya-dhwani", key="sarvam_api_key")
# SDK returns base64-encoded values — decode before use
decoded = base64.b64decode(val.value).decode("utf-8")
os.environ["SARVAM_API_KEY"] = decoded
```

**What we learned:**

| Issue | What happened | Solution |
|-------|---------------|----------|
| `app.yaml` `valueFrom` didn't work | `[ERROR] Error resolving resource sarvam_api_key` — Apps UI secret resources are separate from `databricks secrets` scopes | Load from secret scope via SDK instead |
| Sarvam returned 403 | SDK `get_secret()` returns **base64-encoded** values; we were sending the base64 string as the API key | Decode with `base64.b64decode()` before use |
| Apps UI vs CLI secrets | `databricks secrets put-secret` and Apps UI "Secret resource" are **completely separate** systems | Use the SDK to read from CLI secret scopes, which works reliably |

### Environment variables reference

| Variable | Required? | Local dev | Databricks Apps |
|----------|-----------|-----------|-----------------|
| `LLM_OPENAI_BASE_URL` | Yes | `.env` | `app.yaml` `value:` |
| `LLM_MODEL` | Yes | `.env` | `app.yaml` `value:` |
| `DATABRICKS_TOKEN` | Local only | `.env` (PAT) | Not needed (OAuth M2M) |
| `SARVAM_API_KEY` | Optional | `.env` | Loaded from secret scope via SDK |
| `NYAYA_INDEX_DIR` | No | Override path | Default `/Volumes/...` auto-downloaded |

## UC Volumes are not FUSE-mounted in Databricks Apps

This is the #1 gotcha for developers moving from notebooks to Apps.

**On clusters/notebooks:** `/Volumes/main/india_legal/legal_files/nyaya_index/manifest.json` works as a normal file path.

**On Databricks Apps:** that path doesn't exist. You get `FileNotFoundError`.

**Our solution:** detect the missing path and download via SDK:

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
for item in w.files.list_directory_contents(volume_path):
    with w.files.download(item.path).contents as src:
        # write to /tmp/nyaya_index/...
```

Files are cached in `/tmp/nyaya_index` so subsequent requests reuse them.

**Alternatives for other apps:**
1. SDK download at startup (our approach) — best for small/medium files
2. Bundle files in the repo — if small and not sensitive
3. SDK streaming on demand — for large/infrequent files
4. SQL warehouse queries — for structured data

## Gradio + Databricks Apps integration

### The `gradio-client` 1.3.0 crash

**Problem:** `gr.Chatbot` produces a JSON schema with `additionalProperties: true` (a boolean). `gradio-client` 1.3.0's `_json_schema_to_python_type` can't handle booleans — it recurses into `True` and crashes with `TypeError: argument of type 'bool' is not iterable` or `APIInfoParseError: Cannot parse schema True`.

This crash happens on the `GET /` route (health check), even with `show_api=False`.

**Solution:** monkey-patch `_json_schema_to_python_type` and `get_type` at import time:

```python
import gradio_client.utils as _gc_utils
_orig_inner = _gc_utils._json_schema_to_python_type

def _safe_inner(schema, defs=None):
    if not isinstance(schema, dict):
        return "Any"
    return _orig_inner(schema, defs)

_gc_utils._json_schema_to_python_type = _safe_inner
```

The patch must replace at **module level** so recursive calls within the original function also go through the guard.

### The localhost health-check failure

**Problem:** Gradio's `launch()` sends `HEAD http://localhost:<port>/` to verify the server started. The crash above makes `/` return 500. After retries, Gradio raises `ValueError: When localhost is not accessible, a shareable link must be created`.

**What we tried that didn't work:**

| Attempt | Result |
|---------|--------|
| `share=False, show_api=False` | Still crashes — health check hits `/` regardless |
| `root_path="/"` | Gradio adds redirect middleware → 307 on HEAD → also treated as "not accessible" |
| `server_name="0.0.0.0", server_port=8000` | Conflicts with platform-injected env vars |

**What works:** fix the schema crash (monkey-patch above) + bare `demo.launch()` with **zero arguments**. All four official [Databricks app-templates](https://github.com/databricks/app-templates) use this pattern. The platform injects `GRADIO_SERVER_NAME`, `GRADIO_SERVER_PORT`, etc. via environment variables.

### `gr.ChatInterface` vs `gr.Chatbot` in `gr.Blocks`

If you only need a basic chat UI, use `gr.ChatInterface` — it avoids the schema crash entirely. The `gr.Chatbot` inside `gr.Blocks` is what triggers the problematic `additionalProperties: true` in the JSON schema.

### Gradio `Radio` choices — `(label, value)` not `(value, label)`

**Problem:** `gr.Radio(choices=[(a, b)])` expects `(label, value)`. If you pass `(value, label)`, the stored value is the display name (e.g. `"Kannada"`) instead of the code (`"kn"`).

**Symptom:** downstream lookups like `bcp47_target("Kannada")` silently return the default `"en-IN"`, so translation never happens. No error is raised.

**Fix:** `choices=[(display_name, code) for code, display_name in LANGUAGES]`

## Translation pipeline

```
User input (any language)
  ├─ Text ──→ Sarvam Mayura → English ──→ FAISS search → LLM → English answer
  └─ Audio ──→ Sarvam Saaras STT ──→ English query ──↗
                                                            │
                                    Sarvam Mayura ← English answer
                                         │
                                    Bilingual output:
                                      1. Selected language (translated)
                                      2. English (original)
                                      3. Sources / citations
```

**Key design decisions:**
- LLM always generates in **English** for accuracy with English-language legal corpus
- The `SYSTEM_PROMPT` says "Respond in English"
- Translation back to user's language happens after LLM response
- Both versions are shown so users can verify translation quality
- TTS reads only the translated portion

### Sarvam Mayura silent failure on long text

**Problem:** Sarvam Mayura's translate API silently returns the input text unchanged when it exceeds ~500 characters. No error is raised — the HTTP response is 200 and the `translated_text` field contains the original English text verbatim.

**Symptom:** the bilingual response shows identical English text under both the language label (e.g. "Kannada:") and the "English:" section. Short text like the disclaimer translates correctly, but long LLM responses come back unchanged.

**Solution:** chunk long text before translating. The app splits responses on newline boundaries into chunks of ~500 characters, translates each chunk independently, and rejoins:

```python
_TRANSLATE_CHUNK_LIMIT = 500

def _chunked_translate(text, *, source, target):
    paragraphs = text.split("\n")
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 > _TRANSLATE_CHUNK_LIMIT and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        chunks.append(current)
    return "\n".join(translate_text(c, ...) for c in chunks)
```

**For other developers using Sarvam Mayura:**
- Always chunk text longer than ~500 characters
- Split on paragraph or sentence boundaries to preserve context within each chunk
- The API does not document this limit or return an error — you must handle it client-side
- Short text (disclaimers, single sentences) translates fine without chunking

## `app.yaml` configuration

```yaml
command: ["python", "app/main.py"]

env:
  # SARVAM_API_KEY is loaded from Databricks secret scope at startup via SDK
  - name: "LLM_OPENAI_BASE_URL"
    value: "https://7474650313055161.ai-gateway.cloud.databricks.com/mlflow/v1"
  - name: "LLM_MODEL"
    value: "databricks-llama-4-maverick"
```

**What not to put in `app.yaml`:**
- `DATABRICKS_TOKEN` — use SDK OAuth instead
- `SARVAM_API_KEY` via `valueFrom` — use SDK secret scope loading instead
- `server_name`, `server_port`, `root_path` in `demo.launch()` — let the platform handle it

## Service principal permissions

The app's service principal needs:

| Permission | Resource | Why |
|------------|----------|-----|
| **CAN_QUERY** | AI Gateway serving endpoint | LLM chat completions |
| **READ** | UC Volume `main.india_legal.legal_files` | Download FAISS index at startup |
| **READ** | Secret scope `nyaya-dhwani` | Load `sarvam_api_key` at startup |

## Dependency pins

| Package | Pin | Why |
|---------|-----|-----|
| `gradio` | `~=4.44.0` | Matches Databricks app-templates |
| `gradio-client` | `==1.3.0` | Same minor line as Gradio 4.44.x; has schema bug requiring monkey-patch |
| `huggingface-hub` | `~=0.35.3` | Newer versions remove `HfFolder` which Gradio 4.44 still imports |
| `pandas` | `~=2.2.3` | Matches Databricks app-templates |
| `databricks-sdk` | latest | For OAuth M2M auth, secret loading, Volume file download |
| `faiss-cpu` | `1.7.x` (in notebooks) | 1.8+ requires NumPy 2 which conflicts with databricks-connect |

## Testing

```bash
pip install -e ".[dev,rag]"
pytest tests/ -v
```

| Test | What it exercises |
|------|-------------------|
| `test_text_utils.py` | Column cleaning |
| `test_manifest.py` | RAGManifest JSON round-trip |
| `test_index_faiss.py` | FAISS save/load + search |
| `test_llm_client.py` | URL helpers + RAG message formatting |
| `test_sarvam_client.py` | Translation parsing + WAV round-trip |

## Repository layout

| Path | Purpose |
|------|---------|
| `app/main.py` | Gradio app (RAG + LLM + Sarvam) |
| `app.yaml` | Databricks Apps entry point + env config |
| `src/nyaya_dhwani/` | Python package: embedder, retrieval, llm_client, sarvam_client |
| `notebooks/india_legal_policy_ingest.ipynb` | Ingest BNS, IPC mapping → Delta tables |
| `notebooks/build_rag_index.ipynb` | Build FAISS index on UC Volume |
| `requirements.txt` | Databricks Apps pip install |
| `docs/APP_USER_GUIDE.md` | End-user guide for the app |
| `docs/PLAYGROUND_TO_APP.md` | Playground Get code → env vars |
| `docs/UI_design.md` | UI/UX spec |
| `tests/` | pytest suite |
