# NyaaAIk — AI-Powered Legal Research Assistant

> **Bharat Bricks Hacks 2026 · IIT Delhi**
> Built on Databricks · Powered by Meta Llama 4 Maverick · Indian Law RAG

## 📖 Project Story & Motivation

The motivation behind NyaaAIk is to democratize the accessibility and affordability of legal resources in India. Navigating the Indian judicial system can be daunting and prohibitively expensive for the average citizen.

NyaaAIk is a **Databricks-native legal assistant** using **Llama 4 Maverick** and **Sarvam Saaras v3**. It employs a state-of-the-art Hybrid RAG architecture: Databricks Genie autonomously chunks statutory laws into Delta Tables, synced natively with Vector Search. Simultaneously, an LLM refines user queries for parallel semantic vector retrieval and live web scraping of recent rulings. This bridges the gap—providing courtroom-grade insight to advocates while translating complex statutory laws into actionable, plain-language guidance for everyday citizens.

---

## What is NyaaAIk?

NyaaAIk is an AI legal assistant for Indian users that:
- Searches the **Bharatiya Nyaya Sanhita (BNS)**, BNSS, and BSA using RAG
- Finds live **court judgments** from Indian Kanoon
- Understands **voice in Hindi, Tamil, Bengali, Telugu** and 7 more Indian languages (Sarvam Saaras v3)
- Analyzes **uploaded PDFs, Word docs, and screenshots** using Llama 4 Maverick vision
- Responds in two modes: **Advocate** (courtroom English) and **Citizen** (plain language)
- Works in **Dark and Light themes**

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| **LLM** | Meta Llama 4 Maverick (via Databricks AI Gateway) | Chat, RAG answers, document vision |
| **Vector Search** | Databricks Vector Search | Semantic search over BNS/BNSS/BSA legal corpus |
| **Live Cases** | Indian Kanoon API | Real-time court judgment retrieval |
| **STT** | Sarvam Saaras v3 (`saaras:v3`) | Indian language voice → text (10 languages) |
| **Backend** | Python + Flask | REST API server |
| **Frontend** | React + Vite | Single-page app |
| **Deployment** | Databricks Apps | Hosting on Databricks workspace |
| **Secrets** | Databricks Secret Scopes | Secure API key storage |
| **Storage** | In-memory (per-session) | Uploaded documents + chat context |
| **Persistence** | Browser localStorage | Chat history across sessions |

---

## 🏛️ System Architecture & Data Flow

```mermaid
flowchart TD
    %% Base Inputs
    U[User Query] --> Refiner[LLM Query Refiner<br/>Llama 4 Maverick]

    %% Ingestion & Vector Search Pipeline
    subgraph DataPlatform[Databricks Data Intelligence Platform]
        direction TB
        BNS[(Delta Tables<br/>BNS / BNSS / BSA)]
        FallBk["/Planned: Chunk Set 2<br/>2000 Case Fallback<br/>Not done — data unavailable in cluster"/]

        Genie([Databricks Genie<br/>Auto-Chunking]) --> BNS
        Genie -.-> FallBk

        BNS --> VS1[(Databricks Vector Search<br/>Index 1)]
        FallBk -.-> VS2["/Planned: Vector Search Index 2<br/>Not done — data unavailable in cluster"/]
    end

    %% Live Searching
    subgraph WebScraping[Live Web Scraping]
        Kanoon([Indian Kanoon API])
    end

    %% Retrieval Layer
    Refiner -- Semantic Query --> VS1 & VS2
    Refiner -- Refined Keywords --> Kanoon

    VS1 -- Highly Relevant Statutes --> Synth
    VS2 -.->|Data Unavailable| Synth
    Kanoon -- Top 5-10 Live Cases --> Synth

    %% Synthesis Layer
    subgraph LLM[LLM Synthesis Engine]
        direction TB
        Persona["UI Prompts/Modifiers<br/>Advocate vs Citizen"] --> Synth["Meta Llama 4 Maverick<br/>Open Source LLM"]
        U -- Original Context --> Synth
    end

    %% Output
    Synth --> Out["Structured Legal Response<br/>+ Properly Cited Cases"]

    classDef db fill:#ff3621,stroke:#333,stroke-width:1px,color:#fff;
    classDef os fill:#1a73e8,stroke:#333,stroke-width:1px,color:#fff;
    classDef planned fill:#f0f0f0,stroke:#666,stroke-width:2px,stroke-dasharray: 5 5,color:#666;

    class VS1,Refiner db;
    class Synth os;
    class FallBk,VS2 planned;
```

*Note: Highlighted components leverage the open-source Meta Llama 4 Maverick model and extensive Databricks enterprise infrastructure.*

---

## 🗃️ Databricks Notebook Pipeline — How We Build the RAG Index

The entire data pipeline that powers NyaaAIk's legal knowledge base is run through **two Databricks notebooks**, executed in sequence inside the workspace. The diagram below shows exactly what each notebook does and how data flows end-to-end from raw law files to the deployed app.

### End-to-End Pipeline Diagram

```mermaid
flowchart TD
    classDef notebook fill:#1a3c6e,stroke:#4a90d9,stroke-width:2px,color:#fff
    classDef delta fill:#cc3300,stroke:#ff6644,stroke-width:2px,color:#fff
    classDef volume fill:#2d6a4f,stroke:#52b788,stroke-width:2px,color:#fff
    classDef app fill:#1a5c1a,stroke:#52b788,stroke-width:2px,color:#fff
    classDef source fill:#444,stroke:#999,stroke-width:1px,color:#fff

    %% ── RAW DATA SOURCES ─────────────────────────────────────────────────
    subgraph Sources["Raw Data Sources"]
        CSV["BNS Sections CSV<br/>Volume upload or GitHub mirror"]
        PDF["Official Law PDFs<br/>BNS / BNSS / BSA / Constitution<br/>MHA Gazette / Indiacode.nic.in"]
        HF["Hugging Face Dataset<br/>IPC to BNS Mapping"]
    end

    %% ── NOTEBOOK 1 ───────────────────────────────────────────────────────
    subgraph NB1["NOTEBOOK 1 — india_legal_policy_ingest.ipynb"]
        direction TB
        N1_0["Step 0: Install Dependencies<br/>requests pandas bs4 pymupdf openpyxl"]
        N1_1["Step 1: Config and Helpers<br/>Read secrets from nyaya-dhwani scope<br/>CATALOG=main / SCHEMA=india_legal"]
        N1_1b["Step 1b: Sarvam Connectivity Test<br/>Optional ping to sarvam.ai"]
        N1_2["Step 2: Unity Catalog Setup<br/>CREATE DATABASE main.india_legal<br/>CREATE VOLUME legal_files"]
        N1_3["Step 3: Load BNS Sections<br/>1 Try Volume CSV / 2 GitHub mirrors<br/>3 PDF + ai_parse_document fallback"]
        N1_4["Step 3c: Download Official Law PDFs<br/>BNS / BNSS / BSA / Constitution<br/>Saved to Unity Catalog Volume"]
        N1_5["Step 4: BNS to IPC Mapping Table<br/>Fetch from Hugging Face<br/>Fallback: 7-row built-in stub"]
        N1_6["Step 5: Build legal_rag_corpus<br/>Merge BNS + IPC mapping chunks<br/>Save as Delta Table"]
        N1_7["Step 6: Verify Tables<br/>SHOW TABLES IN main.india_legal<br/>SELECT preview from legal_rag_corpus"]

        N1_0 --> N1_1 --> N1_1b --> N1_2 --> N1_3 --> N1_4 --> N1_5 --> N1_6 --> N1_7
    end

    %% ── DELTA TABLES ─────────────────────────────────────────────────────
    subgraph DeltaLayer["Delta Lake — main.india_legal"]
        T1["bns_sections<br/>Delta Table"]
        T2["bns_ipc_mapping<br/>Delta Table"]
        T3["legal_rag_corpus<br/>chunk_id / source / doc_type / title / text"]
        T4["bns_parsed_elements<br/>Optional — PDF ai_parse_document path"]
    end

    %% ── NOTEBOOK 2 ───────────────────────────────────────────────────────
    subgraph NB2["NOTEBOOK 2 — build_rag_index.ipynb"]
        direction TB
        N2_0["Cell 1: Set REPO_ROOT<br/>Edit path to your workspace clone"]
        N2_1["Cell 1 run: Install RAG Stack<br/>numpy / faiss-cpu 1.7.x / sentence-transformers<br/>pip install -e repo rag rag_embed"]
        N2_2["Cell 2: Load Corpus from Delta<br/>SELECT from legal_rag_corpus to Pandas"]
        N2_3["Cell 3: Embed All Chunks<br/>all-MiniLM-L6-v2 / normalize / float32"]
        N2_4["Cell 4: Save RAG Artifacts<br/>corpus.faiss / chunks.parquet / manifest.json<br/>to nyaya_index Volume"]
        N2_5["Cell 5: Smoke Test<br/>Load index / search theft under BNS / top 5"]

        N2_0 --> N2_1 --> N2_2 --> N2_3 --> N2_4 --> N2_5
    end

    subgraph NB3["NOTEBOOK 3 — setup_vector_search.py (Optional)"]
        direction TB
        N3_1["Create VS Endpoint: nyaya_vs_endpoint<br/>STANDARD type / 20-50ms latency"]
        N3_2["Enable CDF on legal_rag_corpus<br/>Required for Delta Sync index"]
        N3_3["Create Delta Sync Index<br/>legal_rag_corpus_index<br/>Embedding: databricks-bge-large-en"]
        N3_4["Trigger Sync and Wait for ONLINE<br/>Grant CAN_QUERY to App service principal"]

        N3_1 --> N3_2 --> N3_3 --> N3_4
    end

    subgraph NB4["NOTEBOOK 4 — run_benchmark.py (Evaluation)"]
        direction TB
        B1["Phase 1: Retrieval Eval<br/>FAISS vs Vector Search<br/>Recall@7 and MRR"]
        B2["Phase 2: MCQ Accuracy<br/>Internal + BhashaBench-Legal<br/>English and Hindi"]
        B3["Phase 3: Open-Ended Quality<br/>Keyword coverage / chunk recall"]
        B4["Phase 4: Multilingual<br/>Sarvam translation round-trip<br/>Save results to Delta"]

        B1 --> B2 --> B3 --> B4
    end

    %% ── VOLUME OUTPUT ────────────────────────────────────────────────────
    subgraph VolumeOut["Unity Catalog Volume — nyaya_index"]
        V1["nyaya_index/<br/>corpus.faiss — FAISS index<br/>chunks.parquet — metadata<br/>manifest.json — model info"]
    end

    %% ── DEPLOYED APP ─────────────────────────────────────────────────────
    subgraph AppLayer["Deployed NyaaAIk — Databricks Apps"]
        Retriever["retriever.py<br/>Vector Search + FAISS fallback"]
        Flask["Flask API app/main.py<br/>/api/chat / /api/transcribe / /api/upload"]
        React["React Frontend<br/>Advocate / Citizen / Voice / Upload"]
    end

    %% ── DATA FLOW ────────────────────────────────────────────────────────
    CSV --> N1_3
    HF  --> N1_5
    PDF --> N1_4

    N1_3 --> T1
    N1_5 --> T2
    N1_6 --> T3
    N1_3 -.->|PDF path only| T4

    T3 --> N2_2
    N2_4 --> V1

    T3 -.->|Optional VS setup| N3_2
    N3_3 --> VS_IDX[("legal_rag_corpus_index<br/>Databricks Vector Search")]

    V1  --> Retriever
    VS_IDX --> Retriever
    T3  --> Retriever
    Retriever --> Flask --> React

    V1 -.->|Evaluation| B1
    T3 -.->|Evaluation| B1

    %% ── CLASS ASSIGNMENTS ────────────────────────────────────────────────
    class NB1,NB2,NB3,NB4 notebook
    class T1,T2,T3,T4,VS_IDX delta
    class V1 volume
    class Retriever,Flask,React app
    class CSV,PDF,HF source
```

---

## 🚀 Running on Databricks — Notebook-by-Notebook Guide

Follow these steps **in order** inside your Databricks workspace. No local Python needed for data setup.

---

### Prerequisites

Before running any notebook, ensure:

- [ ] Databricks workspace with **Unity Catalog** enabled
- [ ] Secret scope `nyaya-dhwani` created (see [Deployment Step 4](#step-4--set-up-databricks-secret-scope)) containing:
  - `sarvam_api_key`
  - `indian_kanoon_api_token`
  - `datagov_api_key` *(optional)*
- [ ] Repo cloned into **Workspace → Repos** (see [Step 8](#step-8--connect-repo-to-databricks-workspace))
- [ ] A compute cluster or Serverless notebook attached

---

### ⚠️ First-Time Workspace Setup — If You Get `catalog 'main' not found`

This error means either:
- Unity Catalog is not fully configured in your workspace, **or**
- The `main` catalog doesn't exist yet, **or**
- You are on a trial workspace that uses a different default catalog name

**Fix Option A — Create the catalog and schema manually (recommended):**

Open any Databricks notebook, attach to a cluster, and run this **before** Notebook 1:

```sql
-- Run this in a SQL cell or notebook
CREATE CATALOG IF NOT EXISTS main;
CREATE SCHEMA  IF NOT EXISTS main.india_legal;
CREATE VOLUME  IF NOT EXISTS main.india_legal.legal_files;
```

Or via the UI: **Catalog → + Add → Add a catalog** → name it `main` → Create.

**Fix Option B — Use your own catalog name:**

If your workspace has a different catalog (e.g. `hive_metastore` or a custom one), open Notebook 1 and **edit Step 1** to change:

```python
CATALOG  = 'main'        # ← change to your catalog name, e.g. 'hive_metastore'
SCHEMA   = 'india_legal' # ← keep as-is or rename
VOLUME   = 'legal_files' # ← keep as-is or rename
```

> ⚠️ If you change `CATALOG`, also update `app.yaml` and `setup_vector_search.py` to use the same name consistently.

**Verify Unity Catalog is active:**
```sql
SHOW CATALOGS;
-- Should list 'main' and your workspace catalog
```

---

### NOTEBOOK 1 — Data Ingestion

**File:** `notebooks/india_legal_policy_ingest.ipynb`

Open this notebook in your Databricks workspace. Run **each cell in order**:

| Cell | What It Does |
|------|-------------|
| **Step 0** | Installs Python packages: `requests`, `pandas`, `beautifulsoup4`, `lxml`, `openpyxl`, `pymupdf` |
| **Step 1** | Reads secrets from `nyaya-dhwani` scope. Sets `CATALOG=main`, `SCHEMA=india_legal`, `VOLUME=legal_files` |
| **Step 1b** *(optional)* | Pings Sarvam API with a test message to confirm the key works |
| **Step 2** | Creates `main.india_legal` schema and `legal_files` Volume. **If you get `catalog not found`** — run the [First-Time Setup](#️-first-time-workspace-setup--if-you-get-catalog-main-not-found) SQL above first, or change `CATALOG` in Step 1 |
| **Step 3** | Loads BNS sections — tries Volume CSV first, then GitHub mirrors, then PDF fallback |
| **Step 3a** | GitHub mirror fallback (only runs if Step 3 Volume CSV is missing) |
| **Step 3b** | PDF + `ai_parse_document` + Sarvam enrichment (only if CSV and mirrors both fail) |
| **Step 3c** | Downloads official law PDFs from MHA Gazette to the Unity Catalog Volume |
| **Step 3d** | Saves `bns_sections` as a Delta table |
| **Step 4** | Fetches BNS ↔ IPC mapping from Hugging Face. Falls back to a 7-row built-in stub |
| **Build Corpus** | Merges all sources into `legal_rag_corpus` Delta table (`chunk_id`, `source`, `doc_type`, `title`, `text`) |
| **Verify** | `SHOW TABLES` + preview query to confirm data is populated |

**Expected output after this notebook:**
```
✅ Schema : main.india_legal
✅ Volume : /Volumes/main/india_legal/legal_files
🏛️  legal_rag_corpus: <N> total chunks
  BNS_2023         → <N> rows
  BNS_IPC_MAPPING  → <N> rows
```

> 💡 **Tip — Manual CSV upload**: If Step 3 fails to find a BNS CSV, download one from  
> [Kaggle: Bharatiya Nyaya Sanhita Dataset](https://www.kaggle.com/datasets/nandr39/bharatiya-nyaya-sanhita-dataset-bns),  
> upload via **Catalog → Volumes → legal_files → Upload to this volume**, then re-run Step 3.

---

### NOTEBOOK 2 — Build the RAG Index

**File:** `notebooks/build_rag_index.ipynb`

> ⚠️ **Run this notebook AFTER Notebook 1 completes** — it reads from `legal_rag_corpus`.

Open this notebook in Databricks. Run **each cell in order**:

| Cell | What It Does |
|------|-------------|
| **Cell 1 — Edit REPO_ROOT** | Set `REPO_ROOT` to your cloned repo path. Right-click the repo in the Workspace sidebar → **Copy path**. Example: `/Workspace/Users/you@domain.com/nyaya-dhwani-hackathon` |
| **Cell 1 — Run** | Installs RAG stack: `numpy<2`, `faiss-cpu<1.8`, `sentence-transformers`, `pyarrow`, `pandas`. Then runs `pip install -e <REPO_ROOT>[rag,rag_embed]` to make `import nyaya_dhwani` work |
| **Cell 2** | Loads corpus from Delta: `main.india_legal.legal_rag_corpus` → Pandas DataFrame |
| **Cell 3** | Embeds all text chunks using `sentence-transformers/all-MiniLM-L6-v2` with L2 normalization |
| **Cell 4** | Saves three RAG artifacts to the Unity Catalog Volume |
| **Cell 5** | Smoke test: loads the index and runs `"What is theft under BNS?"` → prints top-5 results |

**Expected output:**
```
✅ pip: numpy 1.x, pandas<3, faiss-cpu 1.7.x, pyarrow, sentence-transformers
✅ import nyaya_dhwani → /Workspace/Users/.../src/nyaya_dhwani
✅ import faiss OK
(<N_chunks>, 384)   ← embedding dimensions
✅ Artifacts saved to /Volumes/main/india_legal/legal_files/nyaya_index/
```

**Output artifacts saved to:**
```
/Volumes/main/india_legal/legal_files/nyaya_index/
├── corpus.faiss      ← FAISS similarity index
├── chunks.parquet    ← chunk metadata (id, source, title, text)
└── manifest.json     ← embedding model name, catalog, schema, timestamp
```

> 💡 **If `import nyaya_dhwani` fails**: Ensure `REPO_ROOT` exactly matches the path shown in the Workspace sidebar. Do **not** add `%restart_python` in the install cell — it breaks the kernel before later cells run.

---

### After Both Notebooks Complete

The `retriever.py` module in the deployed app automatically loads the FAISS index from the Volume path. No additional steps are needed — just deploy the app as described in Steps 9–10 below.

---

## Repository Structure

```
nyaya-dhwani-hackathon/
│
├── app/
│   ├── main.py              ← Flask backend (all API routes)
│   └── static/              ← Built React app (DO NOT edit manually)
│       ├── index.html
│       └── assets/
│
├── notebooks/
│   ├── india_legal_policy_ingest.ipynb  ← NOTEBOOK 1: Data ingestion → Delta tables
│   ├── build_rag_index.ipynb            ← NOTEBOOK 2: Build FAISS index → Volume
│   ├── setup_vector_search.py           ← NOTEBOOK 3: Create VS endpoint + Delta Sync index (optional)
│   └── run_benchmark.py                 ← NOTEBOOK 4: RAG evaluation — retrieval / MCQ / multilingual
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx          ← Root component + theme + state
│   │   ├── index.css        ← All styles (dark + light themes)
│   │   ├── components/
│   │   │   ├── Topbar.jsx        ← Header + theme toggle
│   │   │   ├── Sidebar.jsx       ← Chat history + docs list
│   │   │   ├── ControlsBar.jsx   ← Persona + Court + Style controls
│   │   │   ├── TopicsChips.jsx   ← Quick topic selector
│   │   │   ├── WelcomeScreen.jsx ← First-load suggestions
│   │   │   ├── ChatWindow.jsx    ← Message thread
│   │   │   ├── InputBar.jsx      ← Text input + mic + upload
│   │   │   └── UploadModal.jsx   ← Document upload UI
│   │   ├── hooks/
│   │   │   ├── useChat.js        ← Chat state + API calls
│   │   │   └── useSarvamVoice.js ← MediaRecorder → Sarvam STT
│   │   └── utils/
│   │       ├── api.js            ← All fetch calls to Flask
│   │       └── icons.jsx         ← SVG icon components
│   ├── package.json
│   └── vite.config.js
│
├── src/
│   └── nyaya_dhwani/
│       ├── sarvam_client.py  ← Sarvam API helpers (STT, TTS, translate)
│       ├── llm_client.py     ← Maverick LLM calls
│       ├── retriever.py      ← Databricks Vector Search + FAISS fallback
│       └── case_search.py    ← Indian Kanoon API integration
│
├── app.yaml                  ← Databricks App config
├── setup_secrets.py          ← Script to create secret scope
└── README.md
```

---

## Complete Deployment Guide (Step by Step)

Follow **every step** in order. Do not skip.

---

### STEP 1 — Prerequisites

Before starting, make sure you have:

- [ ] A Databricks workspace (Community Edition will NOT work — you need Databricks Apps access)
- [ ] Access to **Databricks AI Gateway** with Llama 4 Maverick configured
- [ ] A **Vector Search endpoint** with the BNS legal corpus indexed
- [ ] An **Indian Kanoon API token** → get it from [indiankanoon.org](https://api.indiankanoon.org/)
- [ ] A **Sarvam API key** → get it from [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)
- [ ] Git installed locally
- [ ] Node.js 18+ installed locally (for building the frontend)

---

### STEP 2 — Clone the Repository

```bash
git clone https://github.com/gaganTakIITD/NyaaAIk.git
cd NyaaAIk
```

---

### STEP 3 — Configure `app.yaml`

Open `app.yaml`. Update the values to match your Databricks workspace:

```yaml
command: ["python", "app/main.py"]

env:
  - name: LLM_OPENAI_BASE_URL
    value: "https://<YOUR-GATEWAY-ID>.ai-gateway.cloud.databricks.com/mlflow/v1"

  - name: LLM_MODEL
    value: "databricks-llama-4-maverick"

  - name: NYAYA_RETRIEVAL_BACKEND
    value: "vector_search"

  - name: NYAYA_VS_ENDPOINT_NAME
    value: "nyaya_vs_endpoint"         # ← your Vector Search endpoint name

  - name: NYAYA_VS_INDEX_NAME
    value: "main.india_legal.legal_rag_corpus_index"  # ← your index

  - name: SARVAM_STT_MODEL
    value: "saaras:v3"
```

> ⚠️ **Do NOT put API keys here.** They are loaded from Databricks Secrets (Step 4).

---

### STEP 4 — Set Up Databricks Secret Scope

This stores API keys securely. Run the following in a **Databricks notebook** (not locally):

**Cell 1 — Get workspace context**
```python
import requests

ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST  = ctx.apiUrl().get()
TOKEN = ctx.apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
print("Host:", HOST)
```

**Cell 2 — Create the secret scope**
```python
r = requests.post(f"{HOST}/api/2.0/secrets/scopes/create",
    headers=HEADERS,
    json={"scope": "nyaya-dhwani", "initial_manage_principal": "users"})
print(r.status_code, r.text)
# 200 = created   |   RESOURCE_ALREADY_EXISTS = already exists (both OK)
```

**Cell 3 — Store Indian Kanoon API token**
```python
r = requests.post(f"{HOST}/api/2.0/secrets/put",
    headers=HEADERS,
    json={
        "scope": "nyaya-dhwani",
        "key":   "indian_kanoon_api_token",
        "string_value": "YOUR_INDIAN_KANOON_TOKEN_HERE"
    })
print(r.status_code, r.text)
```

**Cell 4 — Store Sarvam API key**
```python
r = requests.post(f"{HOST}/api/2.0/secrets/put",
    headers=HEADERS,
    json={
        "scope": "nyaya-dhwani",
        "key":   "sarvam_api_key",
        "string_value": "YOUR_SARVAM_API_KEY_HERE"
    })
print(r.status_code, r.text)
```

**Cell 5 — Verify**
```python
r = requests.get(f"{HOST}/api/2.0/secrets/list?scope=nyaya-dhwani", headers=HEADERS)
print(r.json())
# Expected: {'secrets': [{'key': 'indian_kanoon_api_token', ...}, {'key': 'sarvam_api_key', ...}]}
```

> ✅ Values always show as `[REDACTED]` in Databricks — that is correct behaviour.

---

### STEP 5 — Add App Resources (Grant Secret Access)

In the Databricks Apps UI, before deploying, add both secrets as **resources** so the app's service principal can read them:

1. Go to **Compute → Apps → (your app) → Resources**
2. Add first resource:
   - Secret scope: `nyaya-dhwani`
   - Secret key: `indian_kanoon_api_token`
   - Permission: `Can read`
   - Resource key: `secret1`
3. Add second resource:
   - Secret scope: `nyaya-dhwani`
   - Secret key: `sarvam_api_key`
   - Permission: `Can read`
   - Resource key: `secret2`

> ⚠️ Without these resource declarations, the app cannot read the secrets even if they exist in the scope.

---

### STEP 5b — Run Notebook 1: Data Ingestion (inside Databricks)

1. Navigate to **Workspace → Repos → NyaaAIk → notebooks**
2. Open `india_legal_policy_ingest.ipynb`
3. Attach to a cluster (Standard or Serverless)
4. Run **all cells in order** — see the [Notebook 1 guide above](#notebook-1--data-ingestion)

---

### STEP 5c — Run Notebook 2: Build RAG Index (inside Databricks)

> Run this **after Notebook 1 completes** successfully.

1. Navigate to **notebooks → build_rag_index.ipynb**
2. **Edit `REPO_ROOT`** in Cell 1 to match your workspace path
3. Run **all cells in order** — see the [Notebook 2 guide above](#notebook-2--build-the-rag-index)

---

### STEP 6 — Build the Frontend (Run Locally)

The built files must be committed to git. **Run this on your local machine** (not Databricks):

```bash
cd frontend
npm install
npm run build
cd ..
```

This outputs compiled files to `app/static/`. Verify:
```
app/static/index.html          ← must exist
app/static/assets/index-*.js   ← must exist
app/static/assets/index-*.css  ← must exist
```

> ⚠️ **Never run `npm run build` on Databricks** — Node.js is not available there.

---

### STEP 7 — Push to GitHub

```bash
git add -A
git commit -m "deploy: update config and frontend build"
git push origin main
```

---

### STEP 8 — Connect Repo to Databricks Workspace

1. In your Databricks workspace, go to **Workspace → Repos → Add Repo**
2. URL: `https://github.com/gaganTakIITD/NyaaAIk.git`
3. Click **Create Repo**
4. After creation, click **Pull** to get the latest code

---

### STEP 9 — Deploy the App

1. Go to **Compute → Apps → Create App**
2. Choose **Custom App**
3. Set **Source** to the repo you added in Step 8
4. Set **App file**: `app.yaml`
5. Add the two secret resources (Step 5)
6. Click **Deploy**

The app starts. Watch the **Logs** tab for:
```
INFO - Indian Kanoon API: configured
INFO - Sarvam STT (Saaras): configured
INFO - Starting NyaaAIk on 0.0.0.0:8000
```

If you see `NOT configured` for any key → re-check Steps 4 and 5.

---

### STEP 10 — Access the App

Click the URL shown in the Apps dashboard. You should see the NyaaAIk interface.

---

## What to Do After Any Code Change

Every time you change code locally:

```bash
# If you changed frontend code (React/CSS):
cd frontend
npm run build
cd ..

# Always:
git add -A
git commit -m "your message"
git push origin main

# Then in Databricks:
# Workspace → Repos → NyaaAIk → Pull
# Compute → Apps → NyaaAIk → Deploy (or Restart)
```

---

## What NOT to Do

| ❌ Don't | ✅ Do instead |
|---|---|
| Put API keys in `app.yaml` | Use Databricks Secret Scope (Step 4) |
| Edit files inside `app/static/` manually | Edit source in `frontend/src/`, then `npm run build` |
| Run `npm run build` on Databricks | Build locally, commit the output |
| Commit after editing source but before building | Always build before committing |
| Use Windows line endings (CRLF) for Python/YAML | Keep `.gitattributes` — it enforces LF |
| Skip the resource declarations (Step 5) | Always add both secrets as App Resources |
| Run Notebook 2 before Notebook 1 finishes | Wait for `legal_rag_corpus` table to be created first |

---

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat` | POST | Main RAG query (persona, court, style, history, doc_ids) |
| `/api/upload` | POST | Upload PDF/DOCX/image for context |
| `/api/transcribe` | POST | Audio blob → Sarvam Saaras STT → transcript |
| `/api/topics` | GET | Legal topic seeds for quick chips |
| `/api/health` | GET | Health check |
| `/api/documents/:id` | DELETE | Remove an uploaded document |

---

## Features Reference

### Persona
| Persona | Response style |
|---|---|
| **Advocate** | Formal courtroom English, statutory citations (BNS/BNSS/BSA), ratio decidendi, legal doctrines |
| **Citizen** | Plain everyday language, jargon explained in brackets, practical step-by-step advice |

### Voice Input (Sarvam)
- Click the **mic button** → select language → speak → stop
- Supported: Hindi, English, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi
- Audio is recorded in browser, sent to `/api/transcribe`, processed by Sarvam Saaras v3

### Document Upload
- **PDF**: text extracted with pypdf
- **DOCX**: text extracted with python-docx
- **Images / Screenshots**: sent as base64 to Llama 4 Maverick vision API
- **Ctrl+V**: paste a screenshot directly into the input box
- Documents are **session-scoped** (in server memory) — re-upload after app restarts

### Theme
- **Dark**: `#131314` background, pure blue `#4dabf7` accent
- **Light**: `#ffffff` background, Google blue `#1a73e8` accent
- Toggle: ☀️/🌙 button top-right — saved to browser localStorage

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `catalog 'main' not found` | `main` catalog doesn't exist in this workspace | Run `CREATE CATALOG IF NOT EXISTS main;` in a SQL notebook first, or change `CATALOG = 'main'` in Notebook 1 Step 1 |
| `schema 'main.india_legal' not found` | Schema not created yet | Run Step 2 of Notebook 1, or `CREATE SCHEMA IF NOT EXISTS main.india_legal;` manually |
| `volume 'legal_files' not found` | Volume not created yet | Run Step 2 of Notebook 1, or `CREATE VOLUME IF NOT EXISTS main.india_legal.legal_files;` manually |
| `Unexpected token '<'` | API returned HTML instead of JSON | Check app logs for Python errors |
| `Sarvam STT: NOT configured` | Key not loaded | Re-check secret scope + app resources |
| `Indian Kanoon: NOT configured` | Same | Same |
| UI loads but chat fails | Backend import error | Check Databricks app logs |
| `CRLF` / YAML parse error | Windows line endings in git | `.gitattributes` handles this; don't override |
| Voice mic button missing | Browser doesn't support MediaRecorder | Use Chrome or Edge |
| PDF upload fails | File > 20 MB | Compress or split the PDF |
| `Cannot import nyaya_dhwani` | Wrong `REPO_ROOT` in Notebook 2 | Copy path from Workspace sidebar, set exactly |
| `legal_rag_corpus` table missing | Notebook 1 not run yet | Run `india_legal_policy_ingest.ipynb` first |
| FAISS index not found | Notebook 2 not run yet | Run `build_rag_index.ipynb` after Notebook 1 |
| No BNS data — CSV missing | Volume CSV not uploaded | Download from Kaggle, upload to Volume, re-run Step 3 |
| Sarvam 403 in Notebook | Key invalid or no billing | Check [dashboard.sarvam.ai](https://dashboard.sarvam.ai/) |

---

## Local Development (Optional)

To run locally for testing UI changes (no Databricks connection):

```bash
# Terminal 1 — backend (will error on Databricks-specific imports, use mock mode)
cd app
python main.py

# Terminal 2 — frontend dev server with proxy
cd frontend
npm run dev
```

Open `http://localhost:5173`

> Note: Vector search and live cases won't work locally without Databricks credentials.

---

*Built for Bharat Bricks Hacks 2026 · IIT Delhi · Team NyaaAIk*
