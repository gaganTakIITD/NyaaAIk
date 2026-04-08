# NyaaAIk: Project Architecture & Data Flow

## 📖 Project Story & Motivation
The motivation behind NyaaAIk is to democratize the accessibility and affordability of legal resources in India. Navigating the Indian judicial system can be daunting and prohibitively expensive for the average citizen. By leveraging cutting-edge, open-source AI, NyaaAIk bridges this gap, providing courtroom-grade insight to advocates while translating complex statutory laws into actionable, plain-language guidance for everyday citizens.

To accomplish this mission, **NyaaAIk is built as a Databricks-native legal assistant using Llama 4 Maverick and Sarvam Saaras v3.** It employs a state-of-the-art Hybrid Web & Vector RAG (Retrieval-Augmented Generation) architecture: Databricks Genie autonomously chunks statutory laws into Delta Tables, which are natively synced with Databricks Vector Search. Simultaneously, an LLM refines user queries for parallel semantic vector retrieval and live web scraping of recent rulings. This ensures our AI is never outdated and always cites real precedence.

---

## 🏛️ System Architecture 

NyaaAIk is an advanced, autonomous AI legal assistant built exclusively on the Databricks Data Intelligence Platform. 

This infrastructure heavily utilizes Open Source Intelligence alongside Databricks enterprise capabilities:
* **Open Source LLM:** Meta Llama 4 Maverick (via Databricks AI Gateway) for reasoning, RAG synthesis, and multimodal vision.
* **Open Source STT:** Sarvam Saaras v3 for multilingual Indic voice-to-text processing.
* **Databricks Ecosystem:** Databricks Apps, Databricks Vector Search, Databricks Genie, Delta Tables, Databricks Secret Scopes, and Databricks Model Serving.

This document outlines the end-to-end Data Flow Diagram (DFD) and system architecture, detailing how statutory data, precedent cases, and live legal search are orchestrated.

---

## 1. Data Ingestion & Pre-Processing (Databricks Foundations)

The core knowledge base of the application relies on two distinct chunk sets managed natively within Databricks Delta Tables. These sets are autonomously chunked and maintained using **Databricks Genie**, eliminating the need for manual orchestration scripts or notebooks.

### Chunk Set 1: Statutory Law & Framework
* **Sources:** The Constitution of India, Bharatiya Nyaya Sanhita 2023 (BNS), BNSS, BSA, and other relevant foundational legal documents.
* **Process:** These fixed statutory documents are ingested into Databricks, processed into semantic chunks by Genie, and stored as Delta Tables.
* **Purpose:** Forms the ground truth for statutory law and procedural rules, ensuring the AI responses are firmly rooted in current Indian legal code.

### Chunk Set 2: Precedent Case Law (Fallback Corpus)
* **Sources:** A curated dataset of approximately 2,000 landmark and high-frequency judgments categorized under primary legal domains (e.g., Murder, Theft, Civil Disputes, Cyber Crime).
* **Process:** Similar to Chunk Set 1, these cases are fragmented into semantic chunks and stored as Delta Tables.
* **Purpose:** Acts as a highly reliable fallback reservoir of legal precedent. If live web scraping fails or experiences latency, the system guarantees a baseline of relevant case law citations.

---

## 2. Automated Vector Search Indexing

Databricks Vector Search is seamlessly integrated with the underlying Delta Tables. 
* As Databricks Genie processes and chunks data into Chunk Set 1 and Chunk Set 2, **Databricks Vector Search Indexing** runs concurrently and automatically. 
* This provides a low-latency, scalable semantic search layer over the entire fixed legal corpus without requiring manual triggering or maintenance.

---

## 3. The Retrieval Pipeline (Hybrid RAG)

When a user submits a prompt, the system executes a multi-pronged retrieval strategy to gather the maximum possible context.

### Step 3.1: LLM-Driven Query Refinement
Raw user queries (especially from citizens) can often be unstructured or lack precise legal terminology. 
* An intermediary LLM intercepts the raw user query and refines it into structurally sound, semantically dense legal search queries.
* This refinement drastically improves the accuracy of both the vector search and the live web search.

### Step 3.2: Internal Vector Retrieval
The refined query is executed against the Databricks Vector Search indexes.
* Retrieves highly relevant, precise statutory clauses from **Chunk Set 1 (BNS)**.
* Retrieves semantically similar fallback judgments from **Chunk Set 2 (2000 Cases)**.

### Step 3.3: Live Web Searching & Scraping
Simultaneously, the refined query is used to scrape and search live legal databases (e.g., Indian Kanoon).
* The system retrieves **5 to 10 highly relevant, contemporary case citations** directly from the web.
* This ensures the application has access to the most recent rulings that may not yet exist in Chunk Set 2.

---

## 4. LLM Synthesis & Persona Modeling (Llama 4 Maverick)

Once the retrieval phase gathers all contextual puzzle pieces, they are fed into the final generation model, **Llama 4 Maverick**. Using an Open Source model provides full transparency and control over the inference pipeline inside Databricks.

**The Final Prompt Injection consists of:**
1. **User Query:** The original user context and question.
2. **Chunk Set 1 Data:** Relevant statutory laws and constitutional articles.
3. **Chunk Set 2 Data:** Similar pre-downloaded fallback case laws.
4. **Live Scraped Cases:** The 5-10 freshly scraped, highly relevant live judgments.
5. **Pre-defined Operational Prompts:** Dynamic system instructions.

### Dynamic Modifiers ("Buttering")
The pre-defined operational prompts are dynamically shaped by the user's selected UI filters before generation:
* **Persona:** Shifts the tone and structure between *Advocate* (formal courtroom English, rigorous citations) and *Citizen* (plain language, practical actionable steps).
* **Stance:** Instructs the LLM to structure arguments *In Favour* of the user, *Against* the opposing party, or maintain a *Balanced/Neutral* analysis.
* **Court Level Preference:** Filters prioritization of precedents based on the selected jurisdiction (Supreme Court, High Courts, or District Courts).

## 5. Output Generation

The LLM processes this massive, rich context window and outputs a highly structured, accurate response. Because of the hybrid retrieval (Internal Vector + Live Scraping) and the LLM query refinement, the output contains properly attributed statutory references and pinpoint case law citations, specifically tailored to the strategic needs of the user.
