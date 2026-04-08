"""Flask entrypoint: NyaaAIk Legal Research — RAG + Maverick + Live Cases."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Repo root on Databricks Repos / local clone
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd
from flask import Flask, request, jsonify, send_from_directory

from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text
from nyaya_dhwani.retriever import Retriever, get_retriever
from nyaya_dhwani.case_search import (
    search_precedent_cases,
    build_cases_context,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOPIC_SEEDS: dict[str, str] = {
    "Theft / Robbery": "What is the punishment for theft under BNS and what are landmark cases?",
    "Murder / Homicide": "What are the legal provisions for murder under BNS Section 101 and relevant precedents?",
    "Bail Application": "What are the grounds for granting bail in non-bailable offences under BNSS?",
    "Divorce Law": "What are the grounds for divorce under Indian law for mutual consent?",
    "Consumer Cases": "How do I file a consumer complaint in India for defective goods?",
    "Property Dispute": "What documents should I check before buying residential property in India?",
    "Domestic Violence": "What legal protections exist for victims of domestic violence in India?",
    "FIR / Police": "What is the procedure to file an FIR and what are my rights when arrested?",
    "Cyber Crime": "What are the legal provisions for cybercrime and online fraud under BNS?",
    "Cheque Bounce": "What is the legal process for a cheque bounce case under NI Act Section 138?",
}

COURT_CHOICES = [
    ("All Courts", "all"),
    ("Supreme Court", "SC"),
    ("High Courts", "HC"),
    ("District Courts", "DC"),
]

ARGUMENT_STYLE_CHOICES = [
    ("Balanced Analysis", "neutral"),
    ("Arguments in Favour", "favour"),
    ("Arguments Against", "against"),
]

DISCLAIMER = (
    "This information is for general awareness only and does not constitute legal advice. "
    "Consult a qualified lawyer for your specific situation."
)


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

def _build_system_prompt(argument_style: str, court_filter: str) -> str:
    style_instruction = {
        "favour": "Present arguments primarily IN FAVOUR of the querying party. Highlight supporting precedents and legal provisions.",
        "against": "Present arguments primarily AGAINST the opposing party. Identify weaknesses in potential defenses.",
        "neutral": "Provide a balanced legal analysis covering arguments from both sides.",
    }.get(argument_style, "Provide a balanced legal analysis.")

    court_instruction = {
        "SC": "Prioritize Supreme Court precedents when available.",
        "HC": "Prioritize High Court precedents when available.",
        "DC": "Include District Court level precedents when available.",
        "all": "Consider precedents from all court levels.",
    }.get(court_filter, "Consider precedents from all court levels.")

    return f"""You are NyaaAIk, an AI legal research assistant for Indian advocates and legal professionals.

ROLE: Provide detailed legal analysis with proper case citations, explanations, and statutory references.

INSTRUCTIONS:
1. APPLICABLE LAW: Cite specific BNS (Bharatiya Nyaya Sanhita 2023) sections. If relevant, mention the corresponding old IPC sections.
2. PRECEDENT CASES — Do NOT just cite case names. For each case:
   - State the FACTS briefly (what happened)
   - State the RULING (what the court decided)
   - Explain WHY it is relevant to the user's query
   - Include the court name, year, and link if available
3. ARGUMENT STYLE: {style_instruction}
4. COURT PREFERENCE: {court_instruction}
5. STRUCTURE your response as:
   (a) Applicable Legal Provisions (BNS/IPC sections with brief explanation)
   (b) Relevant Precedents (case name, facts, ruling, and relevance — explained clearly)
   (c) Legal Analysis (connecting law + cases to the user's situation)
   (d) Conclusion / Recommendation
6. If the user asks a follow-up question, use the conversation history to maintain context.
7. Always end with a brief disclaimer that this is AI-generated legal research.

Respond in English. Be thorough but structured. Explain cases so a layperson can understand."""


# ---------------------------------------------------------------------------
# RAG Runtime
# ---------------------------------------------------------------------------

class RAGRuntime:
    def __init__(self) -> None:
        self._retriever: Retriever | None = None
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            self._retriever = get_retriever()
            logger.info("Retriever loaded: %s", type(self._retriever).__name__)
        except Exception as e:
            logger.warning("Could not load retriever (Indian Kanoon only): %s", e)
            self._retriever = None

    @property
    def retriever(self) -> Retriever | None:
        return self._retriever


_runtime: RAGRuntime | None = None


def get_runtime() -> RAGRuntime:
    global _runtime
    if _runtime is None:
        _runtime = RAGRuntime()
    return _runtime


# ---------------------------------------------------------------------------
# Citation formatters
# ---------------------------------------------------------------------------

def _format_law_citations(chunks_df) -> str:
    lines: list[str] = []
    for _, row in chunks_df.iterrows():
        title = row.get("title") or ""
        source = row.get("source") or ""
        doc_type = row.get("doc_type") or ""
        bits = [str(x).strip() for x in (title, source, doc_type) if x and str(x).strip()]
        if bits:
            lines.append(" | ".join(bits[:3]))
    return lines if lines else []


def _format_case_citations(cases: list[dict]) -> list[dict]:
    if not cases:
        return []
    result = []
    for c in cases:
        result.append({
            "title": c.get("title", "Unknown"),
            "court": c.get("court", ""),
            "date": c.get("date", ""),
            "url": c.get("url", ""),
        })
    return result


# ---------------------------------------------------------------------------
# Core RAG pipeline
# ---------------------------------------------------------------------------

def _rag_answer_with_cases(
    query: str,
    court_filter: str,
    argument_style: str,
    chat_history: list | None = None,
) -> dict:
    rt = get_runtime()
    rt.load()
    q = query.strip()

    # --- Chunk Set 1: BNS/Constitution retrieval ---
    chunks_df = pd.DataFrame()
    law_context = ""
    if rt.retriever is not None:
        try:
            chunks_df = rt.retriever.search(q, k=7)
            law_texts = chunks_df["text"].tolist() if "text" in chunks_df.columns else []
            law_context = "\n\n".join(
                f"[LAW] {str(t).strip()}" for t in law_texts if t and str(t).strip()
            )
        except Exception as e:
            logger.warning("Retriever search failed: %s", e)

    # --- Live Case Search ---
    try:
        live_cases, refined = search_precedent_cases(
            q, court_filter=court_filter, top_k=7, max_fetch_text=5,
        )
    except Exception as e:
        logger.warning("Live case search failed: %s", e)
        live_cases = []

    cases_context = build_cases_context(live_cases)

    # --- Build LLM prompt with full history ---
    system_prompt = _build_system_prompt(argument_style, court_filter)

    user_content = f"""RELEVANT LAW SECTIONS (BNS / Constitution / Statutes):
{law_context}

PRECEDENT COURT CASES:
{cases_context}

USER QUERY: {q}"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add ALL previous turns for full context
    if chat_history:
        for turn in chat_history:
            if turn.get("role") == "user":
                messages.append({"role": "user", "content": turn["content"]})
            elif turn.get("role") == "assistant":
                messages.append({"role": "assistant", "content": turn["content"]})

    messages.append({"role": "user", "content": user_content})

    raw = chat_completions(messages, max_tokens=4096, temperature=0.2)
    assistant_text = extract_assistant_text(raw)

    return {
        "answer": assistant_text,
        "law_sources": _format_law_citations(chunks_df),
        "case_sources": _format_case_citations(live_cases),
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=str(_ROOT / "app" / "static"))


@app.route("/")
def index():
    return send_from_directory(str(Path(__file__).parent / "static"), "index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(str(Path(__file__).parent / "static"), filename)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    query = data.get("query", "").strip()
    court = data.get("court", "all")
    style = data.get("style", "neutral")
    history = data.get("history", [])

    if not query:
        return jsonify({"error": "Please enter a legal question."}), 400

    try:
        result = _rag_answer_with_cases(query, court, style, history)
        return jsonify(result)
    except Exception as e:
        logger.exception("api_chat error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/topics", methods=["GET"])
def api_topics():
    return jsonify(TOPIC_SEEDS)


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok", "app": "NyaaAIk"})


# ---------------------------------------------------------------------------
# Secrets loading
# ---------------------------------------------------------------------------

def _load_secrets_from_scope() -> None:
    mapping = {
        "INDIAN_KANOON_API_TOKEN": ("nyaya-dhwani", "indian_kanoon_api_token"),
    }
    for env_var, (scope, key) in mapping.items():
        if os.environ.get(env_var, "").strip():
            continue
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            val = w.secrets.get_secret(scope=scope, key=key)
            if val and val.value:
                import base64
                try:
                    decoded = base64.b64decode(val.value).decode("utf-8")
                except Exception:
                    decoded = val.value
                os.environ[env_var] = decoded
                logger.info("Loaded %s from scope %s/%s", env_var, scope, key)
        except Exception as exc:
            logger.warning("Could not load %s: %s", env_var, exc)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    _load_secrets_from_scope()

    logger.info("Indian Kanoon API: %s",
                "configured" if os.environ.get("INDIAN_KANOON_API_TOKEN") else "NOT configured")

    port = int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", "8000")))
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")

    logger.info("Starting NyaaAIk on %s:%d", host, port)
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
