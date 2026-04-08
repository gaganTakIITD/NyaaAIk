"""Gradio entrypoint: RAG + Maverick + Live Case Search. See docs/PLAN.md."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Repo root on Databricks Repos / local clone
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import gradio as gr

# ---------- Monkey-patch gradio_client bug (1.3.0 + Gradio 4.44.x) ----------
import gradio_client.utils as _gc_utils  # noqa: E402

_orig_inner = _gc_utils._json_schema_to_python_type
_orig_get_type = _gc_utils.get_type

def _safe_inner(schema, defs=None):
    if not isinstance(schema, dict):
        return "Any"
    return _orig_inner(schema, defs)

def _safe_get_type(schema):
    if not isinstance(schema, dict):
        return "Any"
    return _orig_get_type(schema)

_gc_utils._json_schema_to_python_type = _safe_inner
_gc_utils.get_type = _safe_get_type
# ---------- End monkey-patch ------------------------------------------------

from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text
from nyaya_dhwani.retriever import Retriever, get_retriever
from nyaya_dhwani.case_search import (
    search_precedent_cases,
    build_cases_context,
)
import pandas as pd

logger = logging.getLogger(__name__)

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
    """Build a dynamic system prompt based on user preferences."""

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

ROLE: Provide detailed legal analysis with proper case citations and statutory references.

INSTRUCTIONS:
1. APPLICABLE LAW: Cite specific BNS (Bharatiya Nyaya Sanhita 2023) sections. If relevant, mention the corresponding old IPC sections for reference since many precedents cite IPC.
2. PRECEDENT CASES: Reference the court cases provided in context with proper citations (Case Name, Court, Year). Quote key observations from judgments when available.
3. ARGUMENT STYLE: {style_instruction}
4. COURT PREFERENCE: {court_instruction}
5. STRUCTURE your response as:
   (a) Applicable Legal Provisions (BNS/IPC sections)
   (b) Relevant Precedents (case citations with key holdings)
   (c) Legal Analysis
   (d) Conclusion / Recommendation
6. Always end with a brief disclaimer that this is AI-generated legal research.

Respond in English. Be thorough but structured."""


# ---------------------------------------------------------------------------
# RAG Runtime
# ---------------------------------------------------------------------------

class RAGRuntime:
    """Lazy-load retriever (FAISS, Vector Search, or fallback combo)."""

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
            logger.warning("Could not load retriever (will use Indian Kanoon only): %s", e)
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
# Citation formatting
# ---------------------------------------------------------------------------

def _format_law_citations(chunks_df) -> str:
    """Format Chunk Set 1 (BNS/Constitution) citations."""
    lines: list[str] = []
    for _, row in chunks_df.iterrows():
        title = row.get("title") or ""
        source = row.get("source") or ""
        doc_type = row.get("doc_type") or ""
        bits = [str(x).strip() for x in (title, source, doc_type) if x and str(x).strip()]
        if bits:
            lines.append("- " + " | ".join(bits[:3]))
    return "\n".join(lines) if lines else "(no law sources)"


def _format_case_citations(cases: list[dict]) -> str:
    """Format live case search citations for display."""
    if not cases:
        return "(no precedent cases found)"
    lines = []
    for c in cases:
        parts = [c.get("title", "Unknown")]
        if c.get("court"):
            parts.append(c["court"])
        if c.get("date"):
            parts.append(c["date"])
        url = c.get("url", "")
        cite_line = " | ".join(parts)
        if url:
            cite_line += f"\n  Link: {url}"
        lines.append(f"- {cite_line}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core answer pipeline
# ---------------------------------------------------------------------------

def _rag_answer_with_cases(
    query: str,
    court_filter: str,
    argument_style: str,
) -> tuple[str, str, str]:
    """Full pipeline: RAG (Chunk Set 1) + Live Cases + LLM answer.

    Returns (assistant_text, law_citations, case_citations).
    """
    rt = get_runtime()
    rt.load()
    q = query.strip()

    # --- Chunk Set 1: BNS/Constitution/Law retrieval ---
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
    else:
        logger.info("No retriever available — using Indian Kanoon only")

    # --- Live Case Search (Indian Kanoon API) ---
    try:
        live_cases, refined = search_precedent_cases(
            q,
            court_filter=court_filter,
            top_k=7,
            max_fetch_text=5,
            skip_refinement=False,
        )
    except Exception as e:
        logger.warning("Live case search failed, continuing without: %s", e)
        live_cases = []
        refined = {}

    cases_context = build_cases_context(live_cases)

    # --- Build LLM prompt ---
    system_prompt = _build_system_prompt(argument_style, court_filter)

    user_content = f"""RELEVANT LAW SECTIONS (BNS / Constitution / Statutes):
{law_context}

PRECEDENT COURT CASES:
{cases_context}

USER QUERY: {q}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    raw = chat_completions(messages, max_tokens=3072, temperature=0.2)
    assistant_text = extract_assistant_text(raw)

    law_cites = _format_law_citations(chunks_df)
    case_cites = _format_case_citations(live_cases)

    return assistant_text, law_cites, case_cites


# ---------------------------------------------------------------------------
# Gradio turn handler
# ---------------------------------------------------------------------------

def run_turn(
    message: str,
    history: list | None,
    court_filter: str,
    argument_style: str,
) -> tuple[str, list]:
    """Process one chat turn: user input -> RAG + Cases -> LLM -> response."""
    history = [list(pair) for pair in history] if history else []
    q = (message or "").strip()
    if not q:
        history.append(["", "Please type a legal question to search."])
        return "", history

    try:
        assistant_text, law_cites, case_cites = _rag_answer_with_cases(
            q, court_filter, argument_style,
        )

        sources_block = (
            f"\n\n---\n**Statutory Sources**\n{law_cites}\n\n"
            f"**Precedent Cases Cited**\n{case_cites}"
        )

        reply = f"{assistant_text}{sources_block}\n\n---\n*{DISCLAIMER}*"
        history.append([q, reply])
        return "", history
    except Exception as e:
        logger.exception("run_turn")
        err = f"**Error:** {e}"
        history.append([q, err])
        return "", history


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def build_app() -> gr.Blocks:
    custom_css = """
    .gradio-container {
        background: linear-gradient(135deg, #0D1B3E 0%, #1a2a4a 50%, #2a3a5a 100%) !important;
    }
    h1 { color: #F4D03F; font-family: Georgia, serif; }
    h3, .markdown-text { color: #e0d8cc; }
    footer { font-size: 0.85rem; color: #8ea4c8; }
    """

    with gr.Blocks(
        theme=gr.themes.Soft(primary_hue="amber", secondary_hue="slate"),
        css=custom_css,
        title="NyaaAIk - Legal Research Assistant",
    ) as demo:
        gr.Markdown(
            "# ⚖️ NyaaAIk\n"
            "*AI-powered legal research assistant for Indian advocates*\n\n"
            "Search BNS/IPC provisions and find relevant court precedents with cited cases."
        )

        # ---- Research Settings ----
        with gr.Accordion("⚙️ Research Settings", open=True):
            with gr.Row():
                court_radio = gr.Radio(
                    choices=[(label, val) for label, val in COURT_CHOICES],
                    value="all",
                    label="Court Preference",
                    info="Filter precedent cases by court level",
                )
                style_radio = gr.Radio(
                    choices=[(label, val) for label, val in ARGUMENT_STYLE_CHOICES],
                    value="neutral",
                    label="Argument Style",
                    info="How the analysis should be framed",
                )

        # ---- Topic chips ----
        topic = gr.Radio(
            choices=list(TOPIC_SEEDS.keys()),
            label="📌 Common Legal Topics (click to fill)",
            value=None,
        )

        # ---- Chat area ----
        chatbot = gr.Chatbot(
            label="Legal Research",
            height=500,
            bubble_full_width=False,
        )

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Ask your legal question... e.g. 'What is punishment for theft under BNS?'",
                show_label=False,
                lines=2,
                scale=4,
            )
            submit = gr.Button("🔍 Search", variant="primary", scale=1)

        # ---- Event handlers ----
        def fill_topic(choice: str | None):
            if not choice:
                return gr.update()
            seed = TOPIC_SEEDS.get(choice, "")
            return gr.update(value=seed)

        topic.change(fill_topic, inputs=[topic], outputs=[msg])

        _run_turn_io = dict(
            fn=run_turn,
            inputs=[msg, chatbot, court_radio, style_radio],
            outputs=[msg, chatbot],
        )
        submit.click(**_run_turn_io)
        msg.submit(**_run_turn_io)

        gr.Markdown(
            "<small>Powered by **Databricks** (Llama 4 Maverick + Vector Search) | "
            "**Indian Kanoon API** (precedent search) | "
            "Not legal advice — consult a qualified lawyer.</small>"
        )

    return demo


# ---------------------------------------------------------------------------
# Secrets loading (Databricks Apps)
# ---------------------------------------------------------------------------

def _load_secrets_from_scope() -> None:
    """Load secrets from Databricks secret scope into env vars."""
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
                logger.info("Loaded %s from secret scope %s/%s", env_var, scope, key)
        except Exception as exc:
            logger.warning("Could not load %s from secret scope: %s", env_var, exc)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    _load_secrets_from_scope()

    logger.info("Indian Kanoon API: %s",
                "configured" if os.environ.get("INDIAN_KANOON_API_TOKEN") else "NOT configured")

    demo = build_app()
    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()
