# From Playground “Get code” to the app

You confirmed **§8 Step 2a**: models such as **Gemma 3 12B** and **Meta Llama 3.1 8B Instruct** work in the workspace **Playground** with context + question — the same pattern as RAG **generation** after `CorpusIndex.search`.

## 1. Get a programmatic snippet

1. In **Playground**, keep the same model you want in production.
2. Click **Get code** (next to the model / Tools).
3. Copy the sample — it usually uses the **OpenAI-compatible** client against a **Databricks serving** base URL and a **token** (`DATABRICKS_TOKEN` / personal access token / OAuth, depending on the snippet).

Do **not** commit tokens or host URLs with secrets.

## 2. Run it once in a notebook

- Paste the snippet into a **new cell** in a repo notebook; run it.
- If it returns a completion, **§8 Step 2b** is satisfied.

## 3. Map to environment variables (Secrets)

For `src/nyaya_dhwani/llm_client.py` (OpenAI-compatible `chat/completions`):

| Env | Purpose |
|-----|---------|
| `LLM_CHAT_COMPLETIONS_URL` | **Full** URL to `POST` (if your snippet uses a single URL). **Or** omit and set `LLM_OPENAI_BASE_URL` instead. |
| `LLM_OPENAI_BASE_URL` | Base URL only; we append `/chat/completions` if needed. |
| `LLM_MODEL` | Model or endpoint name as required by your snippet. |
| `DATABRICKS_TOKEN` or `LLM_API_KEY` | Bearer token for the request (from Secrets in Jobs/Apps). |

Your **Get code** output may name variables differently — align them to the above or pass arguments explicitly in code.

## 4. RAG glue (next)

1. `chunks = ci.search(embedder.encode([query]), k=5)`  
2. Build a single **context** string from `chunks["text"]`.  
3. `messages = [{"role":"user","content": f"Context:\n{ctx}\n\nQuestion: {query}"}]` (add a system disclaimer: not legal advice).  
4. `llm_client.chat_completions(messages)` → parse assistant text.

## 5. Apps (Gradio or FastAPI)

When **§8 Step 4** is ready, the same `chat_completions` call runs inside **Databricks Apps**. A **Gradio** hello-world deploy is enough to prove the path; extend it with:

- **Volume** — App identity must be allowed to **read** `/Volumes/main/india_legal/.../nyaya_index/` (UC grants on the Volume + external location if any).
- **Secrets** — Configure **App secrets** or env for `DATABRICKS_TOKEN`, `LLM_*`, and embedding/RAG deps (`faiss-cpu`, `sentence-transformers`, …) in `requirements.txt` / app spec.
- **Cold start** — On first request (or at import), `CorpusIndex.load(INDEX_DIR)` + `SentenceEmbedder`; can take tens of seconds on Medium compute.

See [PLAN.md §9](PLAN.md#9-vector-search-and-apps-on-free-edition-you-have-both).
