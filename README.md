# Nyaya Dhwani

**AI-powered legal research assistant for Indian advocates** — search BNS/IPC provisions, find relevant court precedents with cited cases, and get structured legal analysis in 13 languages.

Built on **Databricks Free Edition** with **FAISS / Vector Search RAG**, **Llama 4 Maverick** (AI Gateway), **Indian Kanoon API** (live case search), and **Sarvam AI** (translation, STT, TTS). Deployed as a **Databricks App** via Gradio.

> **Not legal advice.** General information only — consult a qualified lawyer for your specific situation.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DATA PREPARATION (Databricks)                       │
│                                                                              │
│  CHUNK SET 1 (Static Law)              CHUNK SET 2 (Fallback Cases)         │
│  ┌─────────────────────┐               ┌──────────────────────┐             │
│  │ BNS 2023 Full Text  │               │ ~2000 Pre-downloaded │             │
│  │ Constitution of     │  → Genie →    │ court cases by       │  → Genie →  │
│  │ India, Statutes     │   Chunking    │ domain: murder,      │   Chunking  │
│  └─────────────────────┘      │        │ theft, civil, etc.   │      │      │
│                               ↓        └──────────────────────┘      ↓      │
│                         Delta Table 1                          Delta Table 2 │
│                               ↓                                      ↓      │
│                     Vector Search Index 1                  Vector Search     │
│                     (law sections)                         Index 2 (cases)   │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         QUERY TIME (Live)                                    │
│                                                                              │
│  User Query (any of 13 languages)                                            │
│       │                                                                      │
│       ↓                                                                      │
│  Sarvam Mayura → English Query                                               │
│       │                                                                      │
│       ├─────────────────────┬───────────────────────┐                        │
│       ↓                    ↓                        ↓                        │
│  Vector Search         LLM Refines Query      Vector Search                  │
│  Index 1               → Optimized legal      Index 2                        │
│  (BNS/Constitution)      search terms         (fallback cases)               │
│       │                    │                        │                        │
│       │                    ↓                        │                        │
│       │             Indian Kanoon API               │                        │
│       │             (live case search)              │                        │
│       │                    │                        │                        │
│       │              5-10 cited cases               │                        │
│       │              with full text                  │                        │
│       ↓                    ↓                        ↓                        │
│  ┌──────────────────────────────────────────────────────┐                    │
│  │            COMBINE ALL CONTEXT                       │                    │
│  │  Law sections + Live cases + Fallback cases          │                    │
│  │  + User preferences (court, argument style)          │                    │
│  └─────────────────────┬────────────────────────────────┘                    │
│                        ↓                                                     │
│                 Llama 4 Maverick (AI Gateway)                                │
│                        │                                                     │
│                        ↓                                                     │
│               Structured Legal Analysis                                      │
│               with BNS citations + case precedents                           │
│                        │                                                     │
│                        ↓                                                     │
│              Sarvam Translate Back + TTS                                      │
│                        ↓                                                     │
│                  User (Advocate)                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Key Features

- **Live Precedent Search**: Searches Indian Kanoon API for real court cases matching the user's query, with proper citations (case name, court, date, judge)
- **LLM Query Refinement**: Maverick converts user questions into optimized legal search queries with BNS/IPC section identification
- **Court Preference**: Filter cases by Supreme Court, High Courts, or District Courts
- **Argument Style**: Get analysis framed as "in favour", "against", or "balanced"
- **Multilingual**: 13 Indian languages via Sarvam Mayura translation
- **Voice Support**: Microphone input (Sarvam Saaras STT) + read-aloud (Sarvam Bulbul TTS)
- **3-Layer Fallback**: Indian Kanoon API → Google CSE → Pre-loaded Delta Lake cases

## How it works

```
Question (any of 13 languages)
  → Sarvam Mayura translates to English
  → LLM refines query for legal search
  → Vector Search retrieves BNS/law sections (Chunk Set 1)
  → Indian Kanoon API fetches live precedent cases
  → Semantic re-ranking picks top 5-10 most relevant cases
  → Llama 4 Maverick generates structured legal analysis with citations
  → Sarvam Mayura translates back to selected language
  → Bilingual response + case citations + source links
```

**Supported languages:** English, Hindi, Bengali, Kannada, Tamil, Telugu, Malayalam, Marathi, Gujarati, Odia, Punjabi, Assamese, Urdu.

## Quick start

### For users

Open the app URL → select language → choose court preference & argument style → ask a question.

### For developers

```bash
# 1. Authenticate
databricks auth login --host https://dbc-6651e87a-25a5.cloud.databricks.com --profile free-aws
export DATABRICKS_CONFIG_PROFILE=free-aws

# 2. Store secrets
databricks secrets create-scope nyaya-dhwani
databricks secrets put-secret nyaya-dhwani sarvam_api_key
databricks secrets put-secret nyaya-dhwani indian_kanoon_api_token

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

### Local development

```bash
pip install -e ".[dev,rag,rag_embed,app]"
cp .env.example .env   # fill in values
export $(grep -v '^#' .env | xargs)
python app/main.py
```

### Demo steps

1. Open the app URL
2. Select language (e.g., English or Hindi)
3. Click "Begin"
4. Open "Research Settings" → select court (e.g., "Supreme Court") and argument style
5. Click a topic like "Murder / Homicide" or type your own question
6. Click "Search"
7. View the response with: applicable law sections, cited court cases with links, legal analysis

## Repository layout

| Path | Purpose |
|------|---------
| [`app/main.py`](app/main.py) | Gradio app (RAG + Live Case Search + LLM + Sarvam multilingual) |
| [`app.yaml`](app.yaml) | Databricks Apps entry point + env config |
| [`src/nyaya_dhwani/`](src/nyaya_dhwani/) | Python package: case_search, embedder, retrieval, llm_client, sarvam_client |
| [`src/nyaya_dhwani/case_search.py`](src/nyaya_dhwani/case_search.py) | Live precedent case search pipeline (Indian Kanoon + Google CSE + fallback) |
| [`notebooks/`](notebooks/) | Data ingestion + FAISS index build |
| [`requirements.txt`](requirements.txt) | Databricks Apps pip install |
| [`tests/`](tests/) | pytest suite + integration tests |
| [`docs/`](docs/) | All documentation |

## Technology stack

| Component | Technology |
|-----------|-----------|
| LLM | Databricks Llama 4 Maverick (AI Gateway) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector search | FAISS (IndexFlatIP) / Databricks Vector Search |
| Live case search | Indian Kanoon API + Google Custom Search (backup) |
| Translation | Sarvam Mayura |
| Speech-to-text | Sarvam Saaras |
| Text-to-speech | Sarvam Bulbul |
| App framework | Gradio 4.44 on Databricks Apps |
| Data platform | Databricks (Delta Lake, Unity Catalog, Volumes, Apps, Genie) |

## Testing

```bash
pip install -e ".[dev,rag]"
pytest tests/ -v

# Live integration test (requires INDIAN_KANOON_API_TOKEN)
python tests/test_full_integration.py
```

## Databricks technologies used

- **Delta Lake**: Structured storage for legal corpus (BNS, Constitution, court cases)
- **Apache Spark / PySpark**: Data ingestion and text processing at scale
- **Unity Catalog + Volumes**: Data governance, index storage
- **Vector Search / FAISS**: Semantic retrieval for RAG pipeline
- **AI Gateway**: LLM routing (Llama 4 Maverick)
- **Databricks Apps**: Production deployment of Gradio frontend
- **Genie**: Data chunking and exploration
- **MLflow**: Experiment tracking (optional)

## Indian-origin models used

- **Sarvam Mayura**: Translation across 13 Indian languages
- **Sarvam Saaras**: Speech-to-text for voice input
- **Sarvam Bulbul**: Text-to-speech for read-aloud
