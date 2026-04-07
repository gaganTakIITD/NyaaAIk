# NyaaAIk

**AI-powered legal research assistant for Indian advocates** — search BNS/IPC provisions, find relevant court precedents with cited cases, and get structured legal analysis.

Built on **Databricks** with **Vector Search RAG**, **Llama 4 Maverick** (AI Gateway), and **Indian Kanoon API** (live case search). Deployed as a **Databricks App** via Gradio.

> **Not legal advice.** General information only — consult a qualified lawyer for your specific situation.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DATA PREPARATION (Databricks)                       │
│                                                                              │
│  CHUNK SET 1 (Static Law)              CHUNK SET 2 (Fallback Cases)         │
│  ┌─────────────────────┐               ┌──────────────────────┐             │
│  │ BNS 2023 Full Text  │               │ ~2000 Pre-downloaded │             │
│  │ Constitution of     │  → Chunking → │ court cases by       │ → Chunking →│
│  │ India, Statutes     │       │       │ domain: murder,      │      │      │
│  └─────────────────────┘       ↓       │ theft, civil, etc.   │      ↓      │
│                          Delta Table 1  └──────────────────────┘ Delta Table │
│                               ↓                                      ↓      │
│                     Vector Search Index 1                  Vector Search     │
│                     (law sections)                         Index 2 (cases)   │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         QUERY TIME (Live)                                    │
│                                                                              │
│  User Query (English)                                                        │
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
│                        ↓                                                     │
│                  User (Advocate)                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Key Features

- **Live Precedent Search**: Searches Indian Kanoon API for real court cases with proper citations
- **LLM Query Refinement**: Maverick converts user questions into optimized legal search queries
- **Court Preference**: Filter cases by Supreme Court, High Courts, or District Courts
- **Argument Style**: Get analysis framed as "in favour", "against", or "balanced"
- **3-Layer Fallback**: Indian Kanoon API → Google CSE → Pre-loaded Delta Lake cases

## How it works

```
Question → LLM refines query → Vector Search (BNS sections) + Indian Kanoon API (live cases)
  → Semantic re-ranking → Llama 4 Maverick → Structured legal analysis with citations
```

## Quick start

### For developers

```bash
# 1. Authenticate (replace with YOUR workspace URL)
databricks auth login --host https://<your-workspace>.cloud.databricks.com

# 2. Store secrets
databricks secrets create-scope nyaya-dhwani
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

## Repository layout

| Path | Purpose |
|------|---------|
| [`app/main.py`](app/main.py) | Gradio app (RAG + Live Case Search + LLM) |
| [`app.yaml`](app.yaml) | Databricks Apps entry point + env config |
| [`src/nyaya_dhwani/`](src/nyaya_dhwani/) | Python package: case_search, embedder, retrieval, llm_client |
| [`src/nyaya_dhwani/case_search.py`](src/nyaya_dhwani/case_search.py) | Live precedent case search pipeline |
| [`notebooks/`](notebooks/) | Data ingestion + index build |
| [`requirements.txt`](requirements.txt) | Databricks Apps pip install |
| [`tests/`](tests/) | pytest suite + integration tests |

## Technology stack

| Component | Technology |
|-----------|-----------|
| LLM | Databricks Llama 4 Maverick (AI Gateway) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector search | FAISS / Databricks Vector Search |
| Live case search | Indian Kanoon API |
| App framework | Gradio 4.44 on Databricks Apps |
| Data platform | Databricks (Delta Lake, Unity Catalog, Volumes, Apps) |

## Databricks technologies used

- **Delta Lake**: Structured storage for legal corpus
- **Apache Spark**: Data ingestion and text processing
- **Unity Catalog + Volumes**: Data governance, index storage
- **Vector Search / FAISS**: Semantic retrieval for RAG pipeline
- **AI Gateway**: LLM routing (Llama 4 Maverick)
- **Databricks Apps**: Production deployment

## Author

**Gagan Tak** — IIT Delhi
