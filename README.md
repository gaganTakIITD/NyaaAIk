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
    U[User Query] --> Refiner[LLM Query Refiner\n(Llama 4 Maverick)]
    
    %% Ingestion & Vector Search Pipeline
    subgraph DataPlatform[Databricks Data Intelligence Platform]
        direction TB
        BNS[(Chunk Set 1: Delta Tables\nBNS, BNSS, BSA)]
        FallBk[/"(Planned) Chunk Set 2:\n2000 Case Fallback"/]
        
        Genie([Databricks Genie\nAuto-Chunking]) --> BNS
        Genie -.-> FallBk
        
        BNS --> VS1[(Databricks Vector Search\nIndex 1)]
        FallBk -.-> VS2[/"(Planned) Vector Search\nIndex 2"/]
    end
    
    %% Live Searching
    subgraph WebScraping[Live Web Scraping]
        Kanoon([Indian Kanoon API])
    end

    %% Retrieval Layer
    Refiner -- Semantic Query --> VS1 & VS2
    Refiner -- Refined Keywords --> Kanoon

    VS1 -- "Highly Relevant Statutes" --> Synth
    VS2 -.-x|"Data Unavailable"| Synth
    Kanoon -- "Top 5-10 Live Cases" --> Synth

    %% Synthesis Layer
    subgraph LLM[LLM Synthesis Engine]
        direction TB
        Persona[UI Prompts/Modifiers\nAdvocate vs Citizen] --> Synth[Meta Llama 4 Maverick\nOpen Source LLM]
        U -- Original Context --> Synth
    end

    %% Output
    Synth --> Out[Generation:\nStructured Legal Response\n+ Properly Cited Cases]
    
    classDef db fill:#ff3621,stroke:#333,stroke-width:1px,color:#fff;
    classDef os fill:#1a73e8,stroke:#333,stroke-width:1px,color:#fff;
    classDef planned fill:#f0f0f0,stroke:#666,stroke-width:2px,stroke-dasharray: 5 5,color:#666;
    
    class Gen,VS1,Refiner db;
    class Synth os;
    class FallBk,VS2 planned;
```

*Note: Highlighted components leverage the open-source Meta Llama 4 Maverick model and extensive Databricks enterprise infrastructure.*

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
│       ├── retriever.py      ← Databricks Vector Search retriever
│       └── case_search.py    ← Indian Kanoon API integration
│
├── app.yaml                  ← Databricks App config
├── setup_secrets.py          ← Notebook to create secret scope
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

This stores API keys securely. Instead of writing code, you can use the pre-built notebook:

1. In your Databricks Workspace, click **Workspace → Import**.
2. Select the **`setup_secrets.py`** file from this repository.
3. Databricks will automatically open it as a rich, interactive Notebook.
4. Open the notebook, paste your **Indian Kanoon** and **Sarvam** API keys into the designated cells.
5. Click **Run All** to securely save your secrets to the Databricks Vault.

> ✅ Values always show as `[REDACTED]` in Databricks logs — that is correct behaviour.

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
| `Unexpected token '<'` | API returned HTML instead of JSON | Check app logs for Python errors |
| `Sarvam STT: NOT configured` | Key not loaded | Re-check secret scope + app resources |
| `Indian Kanoon: NOT configured` | Same | Same |
| UI loads but chat fails | Backend import error | Check Databricks app logs |
| `CRLF` / YAML parse error | Windows line endings in git | `.gitattributes` handles this; don't override |
| Voice mic button missing | Browser doesn't support MediaRecorder | Use Chrome or Edge |
| PDF upload fails | File > 20 MB | Compress or split the PDF |

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
