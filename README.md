# Nyaya Dhwani

**Multilingual legal information assistant for Indian law** — ask questions about the Bharatiya Nyaya Sanhita (BNS), Indian Penal Code (IPC), and their mappings in 13 languages.

Built on **Databricks Free Edition** with **FAISS RAG**, **Llama Maverick** (AI Gateway), and **Sarvam AI** (translation, speech-to-text, text-to-speech). Deployed as a **Databricks App** via Gradio.

> **Not legal advice.** General information only — consult a qualified lawyer for your specific situation.

## How it works

```
Question (any of 13 languages)
  → Sarvam Mayura translates to English
  → FAISS semantic search (900+ legal text chunks)
  → Databricks Llama Maverick generates answer with citations
  → Sarvam Mayura translates back to selected language
  → Bilingual response (selected language + English) + sources
```

**Supported languages:** English, Hindi, Bengali, Kannada, Tamil, Telugu, Malayalam, Marathi, Gujarati, Odia, Punjabi, Assamese, Urdu.

**Voice support:** microphone input via Sarvam Saaras STT, answer read aloud via Sarvam Bulbul TTS.

## Documentation

| Document | Audience | What it covers |
|----------|----------|----------------|
| **[App User Guide](docs/APP_USER_GUIDE.md)** | End users | How to use the app — language selection, asking questions, understanding responses, voice features |
| **[Developer Guide](docs/DEVELOPER_GUIDE.md)** | Developers | Deploying the app, secrets/auth, Gradio + Databricks Apps pitfalls, translation pipeline, dependency pins |
| [UI Design](docs/UI_design.md) | Designers / developers | UI/UX spec and Sarvam pipeline design |
| [Playground to App](docs/PLAYGROUND_TO_APP.md) | Developers | Mapping Playground "Get code" to app env vars |
| [Workspace Setup](docs/WORKSPACE_SETUP.md) | Admins | Databricks secret scopes, GitHub Repos, key rotation |
| [Plan](docs/PLAN.md) | Team | Product plan and architecture decisions |

## Quick start

### For users

Open the app URL → select language → ask a question. See [App User Guide](docs/APP_USER_GUIDE.md).

### For developers

```bash
# 1. Authenticate
databricks auth login --host https://dbc-6651e87a-25a5.cloud.databricks.com --profile free-aws
export DATABRICKS_CONFIG_PROFILE=free-aws

# 2. Store secrets
databricks secrets create-scope nyaya-dhwani
databricks secrets put-secret nyaya-dhwani sarvam_api_key

# 3. Run notebooks (on a Databricks cluster)
#    - notebooks/india_legal_policy_ingest.ipynb  (ingest → legal_rag_corpus table)
#    - notebooks/build_rag_index.ipynb            (FAISS index → UC Volume)

# 4. Deploy the app
#    Compute → Apps → Create → connect this Git repo → Deploy

# 5. Grant service principal permissions
#    - CAN_QUERY on AI Gateway endpoint
#    - READ on UC Volume main.india_legal.legal_files
#    - READ on secret scope nyaya-dhwani
```

Full details: [Developer Guide](docs/DEVELOPER_GUIDE.md).

### Local development

```bash
pip install -e ".[dev,rag,rag_embed,app]"
cp .env.example .env   # fill in values
export $(grep -v '^#' .env | xargs)
python app/main.py
```

## Repository layout

| Path | Purpose |
|------|---------|
| [`app/main.py`](app/main.py) | Gradio app (RAG + LLM + Sarvam multilingual) |
| [`app.yaml`](app.yaml) | Databricks Apps entry point + env config |
| [`src/nyaya_dhwani/`](src/nyaya_dhwani/) | Python package: embedder, retrieval, llm_client, sarvam_client |
| [`notebooks/`](notebooks/) | Data ingestion + FAISS index build |
| [`requirements.txt`](requirements.txt) | Databricks Apps pip install |
| [`tests/`](tests/) | pytest suite |
| [`docs/`](docs/) | All documentation (see table above) |

## Testing

```bash
pip install -e ".[dev,rag]"
pytest tests/ -v
```

## Technology stack

| Component | Technology |
|-----------|-----------|
| LLM | Databricks Llama 4 Maverick (AI Gateway) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector search | FAISS (IndexFlatIP, cosine similarity) |
| Translation | Sarvam Mayura |
| Speech-to-text | Sarvam Saaras |
| Text-to-speech | Sarvam Bulbul |
| App framework | Gradio 4.44 on Databricks Apps |
| Data platform | Databricks (Unity Catalog, Volumes, Apps) |
