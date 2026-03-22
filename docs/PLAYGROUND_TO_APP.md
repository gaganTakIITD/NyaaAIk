# From Playground “Get code” to the Gradio app

This document connects three layers: **Playground Get code** → **environment variables (and Secrets)** → **Databricks App** runtime (Gradio + RAG + Sarvam). Use it with [PLAN.md](PLAN.md) ([Deploy the app](PLAN.md#deploy-the-app-git-connected), [§10 Developer setup](PLAN.md#10-developer-setup-databricks-free-edition)).

**Default LLM for Nyaya Dhwani:** **Databricks Llama 4 Maverick** — use `LLM_MODEL=databricks-llama-4-maverick` unless your workspace renames the model id; always treat **Get code** as the source of truth for `base_url` and model string.

You confirmed **§8 Step 2a** works when a workspace model answers in **Playground** with context + question — the same pattern as RAG **generation** after `CorpusIndex.search`. Other models (e.g. Gemma 3 12B) are fine for smoke tests; **Maverick** is what we standardize on for the shipped app.

---

## 1. Get a programmatic snippet

1. In **Playground**, select **Databricks Llama 4 Maverick** (or the model you will use in production).
2. Click **Get code** (next to the model / Tools).
3. Copy the sample — it usually uses the **OpenAI-compatible** client against a **Databricks** base URL (**AI Gateway** often ends with `…/mlflow/v1`) and a **token** (`DATABRICKS_TOKEN` / personal access token / OAuth, depending on the snippet).

Do **not** commit tokens or host URLs with secrets.

---

## 2. Run it once in a notebook

- Paste the snippet into a **new cell** in a repo notebook; run it.
- If it returns a completion, **§8 Step 2b** is satisfied.

---

## 3. Map to environment variables (Secrets)

For [`src/nyaya_dhwani/llm_client.py`](../src/nyaya_dhwani/llm_client.py) (OpenAI-compatible `chat/completions`):

| Env | Purpose |
|-----|---------|
| `LLM_CHAT_COMPLETIONS_URL` | **Full** URL to `POST` (if your snippet uses a single URL). **Or** omit and set `LLM_OPENAI_BASE_URL` instead. |
| `LLM_OPENAI_BASE_URL` | Base URL only; we append `/chat/completions` when the base ends with `/v1` (including **AI Gateway** `…/mlflow/v1` from **Get code**). |
| `LLM_MODEL` | **Recommended:** `databricks-llama-4-maverick` — must match Playground / Get code. |
| `DATABRICKS_TOKEN` or `LLM_API_KEY` | Bearer token for the request (from Secrets in Jobs/Apps). **Never commit.** |

Your **Get code** output may name variables differently — align them to the above or pass arguments explicitly in code.

### AI Gateway (typical Get code shape)

Playground **Get code** often looks like:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DATABRICKS_TOKEN"],
    base_url="https://<workspace-id>.ai-gateway.cloud.databricks.com/mlflow/v1",
)
response = client.chat.completions.create(
    model="databricks-llama-4-maverick",
    messages=[{"role": "user", "content": "..."}],
    max_tokens=5000,
)
```

In the app, set `LLM_OPENAI_BASE_URL` to that same `base_url` (no trailing slash), `LLM_MODEL` to the same model id, and use either:

- **`llm_client.chat_completions`** (uses `requests`; no extra package), or  
- **`llm_client.complete_with_openai_sdk`** after `pip install 'nyaya-dhwani[llm_openai]'` — same SDK calls as Get code.

### Sarvam and index path (app and notebooks)

[`sarvam_client.py`](../src/nyaya_dhwani/sarvam_client.py) reads **`SARVAM_API_KEY`** (set from Databricks Secrets: `dbutils.secrets.get("nyaya-dhwani", "sarvam_api_key")` then `os.environ["SARVAM_API_KEY"] = …`, or map the secret in the **App** env UI).

| Env / secret | Purpose |
|--------------|---------|
| `SARVAM_API_KEY` | Sarvam HTTP APIs (STT/TTS/chat as wired in your app). |
| `NYAYA_INDEX_DIR` | **Optional** — absolute path to the FAISS index directory. If unset, use the same default as [`build_rag_index.ipynb`](../notebooks/build_rag_index.ipynb): `/Volumes/main/india_legal/legal_files/nyaya_index/`. |

---

## 4. Configure the same credentials on the Databricks App

Notebook env and **App** env should match for LLM + Sarvam + RAG.

| Concern | What to do |
|---------|------------|
| **LLM** | In the App **Environment variables** (or Secrets integration), set `LLM_OPENAI_BASE_URL`, `LLM_MODEL`, and `DATABRICKS_TOKEN` exactly as in §3. Prefer a **secret reference** or Databricks-managed secret over pasting tokens. |
| **Sarvam** | Set `SARVAM_API_KEY` (value from scope `nyaya-dhwani` key `sarvam_api_key` or equivalent). |
| **Index** | Ensure the App’s identity can **read** the Unity Catalog Volume path for `nyaya_index/`. Optionally set `NYAYA_INDEX_DIR` if the index is not at the default path. |
| **Dependencies** | App image / `requirements` must include `faiss-cpu` (1.7.x), `numpy<2`, `sentence-transformers`, `gradio`, `requests`, and the rest of your RAG stack per [README.md](../README.md). |

Gradio’s `blocks.launch()` must bind the host/port expected by [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) (follow the official **Python / Gradio** sample for your workspace version).

---

## 5. Git-connected App (wizard summary)

Full checklist: [PLAN.md — Deploy the app (Git-connected)](PLAN.md#deploy-the-app-git-connected). Short version:

1. **Compute → Apps → Create**
2. **Name** the app (e.g. `nyaya-dhwani`)
3. **Configure this Git repository** — branch (e.g. `main`), same repo as **Databricks Repos**
4. **Configure the app** — start command (e.g. `python app/main.py` once it exists), working directory, env vars from §3–§4, Volume read access

---

## 6. RAG glue

1. `chunks = ci.search(embedder.encode([query_en]), k=5)` (use English query string after Sarvam translate if needed).  
2. Build a single **context** string from `chunks["text"]`.  
3. Build `messages` with a **system** (or user) block: disclaimer — not legal advice; include **Context:** and **Question:**.  
4. **`llm_client.chat_completions(messages)`** — **Maverick** receives the same `messages` list (retrieved chunks + disclaimer + user question).  
5. Parse assistant text with `extract_assistant_text` / your helper.

---

## 7. Gradio UI and Sarvam in production

Where **Sarvam** (STT, `mayura`, `bulbul-v1`) and **Gradio** (`Chatbot`, `Audio`, theme) meet in one place is specified in [UI_design.md](UI_design.md) — screens, component map, mandatory disclaimers, and the Sarvam pipeline diagram.

---

## 8. See also

- [PLAN.md §9 — Apps on Free Edition](PLAN.md#9-vector-search-and-apps-on-free-edition-you-have-both)  
- [PLAN.md §10 — Developer setup](PLAN.md#10-developer-setup-databricks-free-edition)  
- [PLAN.md §11 — End-user instructions](PLAN.md#11-end-user-instructions)
