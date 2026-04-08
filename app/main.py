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

ROLE: Provide detailed legal analysis with proper case citations, explanations, and statutory references.

INSTRUCTIONS:
1. APPLICABLE LAW: Cite specific BNS (Bharatiya Nyaya Sanhita 2023) sections. If relevant, mention the corresponding old IPC sections for reference since many precedents cite IPC.
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
6. If the user asks a follow-up question, use the conversation history to maintain context. Don't repeat information already given unless asked.
7. Always end with a brief disclaimer that this is AI-generated legal research.

Respond in English. Be thorough but structured. Explain cases so a layperson can understand."""


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
    chat_history: list | None = None,
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

    # Build messages with conversation history for multi-turn
    messages = [{"role": "system", "content": system_prompt}]

    # Add previous turns for context (last 3 exchanges)
    if chat_history:
        for prev_user, prev_bot in chat_history[-3:]:
            if prev_user:
                messages.append({"role": "user", "content": prev_user})
            if prev_bot:
                # Strip the sources/disclaimer block from previous responses
                clean_bot = prev_bot.split("\n---\n**Statutory Sources**")[0].strip()
                messages.append({"role": "assistant", "content": clean_bot})

    messages.append({"role": "user", "content": user_content})

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
            q, court_filter, argument_style, history
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .gradio-container {
        background: #0f172a !important;
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
        max-width: 900px !important;
        margin: 0 auto !important;
    }

    /* Header */
    .header-block {
        text-align: center;
        padding: 2rem 1rem 1rem;
    }
    .header-block h1 {
        font-size: 2.2rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-block h1 span { color: #fbbf24; }
    .header-block p {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-top: 0.3rem;
    }

    /* Cards */
    .gr-panel, .gr-box, .gr-form {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
    }

    /* Labels */
    label, .gr-input-label, span.text-lg {
        color: #cbd5e1 !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
    }

    /* Radio buttons */
    .gr-radio-row label {
        background: #1e293b !important;
        border: 1px solid #475569 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        transition: all 0.2s ease;
    }
    .gr-radio-row label:hover {
        border-color: #fbbf24 !important;
    }
    .gr-radio-row input:checked + label {
        background: #fbbf24 !important;
        color: #0f172a !important;
        border-color: #fbbf24 !important;
        font-weight: 600 !important;
    }

    /* Chat bubbles */
    .message {
        border-radius: 12px !important;
        font-size: 0.9rem !important;
        line-height: 1.65 !important;
    }
    .user .message-bubble-border {
        background: #1d4ed8 !important;
        border: none !important;
    }
    .bot .message-bubble-border {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
    }

    /* Input */
    textarea, input[type="text"] {
        background: #1e293b !important;
        border: 1px solid #475569 !important;
        color: #f1f5f9 !important;
        border-radius: 10px !important;
        font-size: 0.9rem !important;
    }
    textarea:focus {
        border-color: #fbbf24 !important;
        box-shadow: 0 0 0 2px rgba(251,191,36,0.15) !important;
    }

    /* Primary button */
    .gr-button-primary {
        background: #fbbf24 !important;
        color: #0f172a !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        border: none !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease;
    }
    .gr-button-primary:hover {
        background: #f59e0b !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(251,191,36,0.25);
    }

    /* Accordion */
    .gr-accordion {
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        background: #1e293b !important;
    }

    /* Chatbot container */
    .chatbot {
        background: #0f172a !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
    }

    /* Footer */
    .footer-block p, .footer-block span {
        color: #64748b !important;
        font-size: 0.75rem !important;
        text-align: center;
    }

    /* Topic pills */
    .topic-row .gr-radio-row label {
        font-size: 0.8rem !important;
        padding: 6px 14px !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    """

    with gr.Blocks(
        theme=gr.themes.Base(
            primary_hue=gr.themes.colors.amber,
            secondary_hue=gr.themes.colors.slate,
            neutral_hue=gr.themes.colors.slate,
        ),
        css=custom_css,
        title="NyaaAIk — AI Legal Research",
    ) as demo:

        # ---- Header ----
        gr.HTML(
            '<div class="header-block">'
            '<h1>⚖️ <span>NyaaAIk</span></h1>'
            '<p>AI Legal Research Assistant for Indian Advocates</p>'
            '</div>'
        )

        # ---- Settings row ----
        with gr.Row(equal_height=True):
            court_radio = gr.Radio(
                choices=[(label, val) for label, val in COURT_CHOICES],
                value="all",
                label="Court",
            )
            style_radio = gr.Radio(
                choices=[(label, val) for label, val in ARGUMENT_STYLE_CHOICES],
                value="neutral",
                label="Style",
            )

        # ---- Quick topics ----
        topic = gr.Radio(
            choices=list(TOPIC_SEEDS.keys()),
            label="Quick Topics",
            value=None,
            elem_classes=["topic-row"],
        )

        # ---- Chat ----
        chatbot = gr.Chatbot(
            height=480,
            show_label=False,
            bubble_full_width=False,
            avatar_images=(None, None),
        )

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Type your legal question here...",
                show_label=False,
                lines=1,
                scale=5,
                container=False,
            )
            submit = gr.Button("Search", variant="primary", scale=1, min_width=100)

        # ---- Handlers ----
        def fill_topic(choice: str | None):
            if not choice:
                return gr.update()
            return gr.update(value=TOPIC_SEEDS.get(choice, ""))

        topic.change(fill_topic, inputs=[topic], outputs=[msg])

        _io = dict(
            fn=run_turn,
            inputs=[msg, chatbot, court_radio, style_radio],
            outputs=[msg, chatbot],
        )
        submit.click(**_io)
        msg.submit(**_io)

        # ---- Footer ----
        gr.HTML(
            '<div class="footer-block">'
            '<p>Powered by Databricks (Llama 4 Maverick + Vector Search) · Indian Kanoon API · '
            'Not legal advice — consult a qualified lawyer</p>'
            '</div>'
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
