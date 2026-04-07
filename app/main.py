"""Gradio entrypoint: RAG + Maverick + Sarvam + Live Case Search. See docs/PLAN.md."""

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
import numpy as np

# ---------- Monkey-patch gradio_client bug (1.3.0 + Gradio 4.44.x) ----------
# get_api_info() crashes on Chatbot schemas where additionalProperties is True
# (a bool).  The internal recursive calls use the module-level name, so we must
# replace the actual function objects in the module namespace.
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

# Patch module-level names so internal recursive calls also go through guards.
_gc_utils._json_schema_to_python_type = _safe_inner
_gc_utils.get_type = _safe_get_type
# ---------- End monkey-patch ------------------------------------------------

from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text, rag_user_message
from nyaya_dhwani.retriever import Retriever, get_retriever
from nyaya_dhwani.case_search import (
    search_precedent_cases,
    build_cases_context,
)
from nyaya_dhwani.sarvam_client import (
    is_configured as sarvam_configured,
    numpy_audio_to_wav_bytes,
    speech_to_text_file,
    strip_markdown_for_tts,
    text_to_speech_wav_bytes,
    transcript_from_stt_response,
    translate_text,
    wav_bytes_to_numpy_float32,
)

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

SARVAM_LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("bn", "Bengali"),
    ("te", "Telugu"),
    ("mr", "Marathi"),
    ("ta", "Tamil"),
    ("gu", "Gujarati"),
    ("kn", "Kannada"),
    ("ml", "Malayalam"),
    ("pa", "Punjabi"),
    ("or", "Odia"),
    ("ur", "Urdu"),
    ("as", "Assamese"),
]

# UI ISO-ish code -> BCP-47 for Mayura / STT hints
UI_TO_BCP47: dict[str, str] = {
    "en": "en-IN", "hi": "hi-IN", "bn": "bn-IN", "te": "te-IN",
    "mr": "mr-IN", "ta": "ta-IN", "gu": "gu-IN", "kn": "kn-IN",
    "ml": "ml-IN", "pa": "pa-IN", "or": "od-IN", "ur": "hi-IN",
    "as": "bn-IN",
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

DISCLAIMER_EN = (
    "This information is for general awareness only and does not constitute legal advice. "
    "Consult a qualified lawyer for your specific situation."
)

# ---------------------------------------------------------------------------
# System Prompts
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

    return f"""You are Nyaya Dhwani, an AI legal research assistant for Indian advocates and legal professionals.

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
# Translation helpers
# ---------------------------------------------------------------------------

def bcp47_target(lang: str) -> str:
    return UI_TO_BCP47.get(lang, "en-IN")


_TRANSLATE_CHUNK_LIMIT = 500


def _chunked_translate(text: str, *, source: str, target: str) -> str:
    paragraphs = text.split("\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 > _TRANSLATE_CHUNK_LIMIT and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        chunks.append(current)

    translated_parts = []
    for chunk in chunks:
        if not chunk.strip():
            translated_parts.append(chunk)
            continue
        try:
            result = translate_text(chunk, source_language_code=source, target_language_code=target)
            translated_parts.append(result)
        except Exception as e:
            logger.warning("Mayura chunk translate failed, keeping original: %s", e)
            translated_parts.append(chunk)
    return "\n".join(translated_parts)


def _maybe_translate(text: str, *, source: str, target: str) -> str:
    if source == target:
        return text
    if not sarvam_configured():
        return text
    if len(text) > _TRANSLATE_CHUNK_LIMIT:
        return _chunked_translate(text, source=source, target=target)
    try:
        return translate_text(text, source_language_code=source, target_language_code=target)
    except Exception as e:
        logger.warning("Mayura translate failed, using original: %s", e)
        return text


def text_to_query_english(user_text: str, lang: str) -> str:
    t = user_text.strip()
    if not t:
        return t
    if lang == "en":
        return t
    if not sarvam_configured():
        logger.warning("SARVAM_API_KEY missing -- using raw text for retrieval (degraded).")
        return t
    return _maybe_translate(t, source="auto", target="en-IN")


# ---------------------------------------------------------------------------
# RAG Runtime
# ---------------------------------------------------------------------------

class RAGRuntime:
    """Lazy-load retriever (FAISS, Vector Search, or fallback combo)."""

    def __init__(self) -> None:
        self._retriever: Retriever | None = None

    def load(self) -> None:
        if self._retriever is not None:
            return
        self._retriever = get_retriever()
        logger.info("Retriever loaded: %s", type(self._retriever).__name__)

    @property
    def retriever(self) -> Retriever:
        if self._retriever is None:
            raise RuntimeError("RAGRuntime not loaded")
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
    query_en: str,
    court_filter: str,
    argument_style: str,
) -> tuple[str, str, str]:
    """Full pipeline: RAG (Chunk Set 1) + Live Cases + LLM answer.

    Returns (assistant_en, law_citations, case_citations).
    """
    rt = get_runtime()
    rt.load()
    q = query_en.strip()

    # --- Chunk Set 1: BNS/Constitution/Law retrieval ---
    chunks_df = rt.retriever.search(q, k=7)
    law_texts = chunks_df["text"].tolist() if "text" in chunks_df.columns else []
    law_context = "\n\n".join(
        f"[LAW] {str(t).strip()}" for t in law_texts if t and str(t).strip()
    )

    # --- Live Case Search (Chunk Set 2 + Indian Kanoon) ---
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
    assistant_en = extract_assistant_text(raw)

    law_cites = _format_law_citations(chunks_df)
    case_cites = _format_case_citations(live_cases)

    return assistant_en, law_cites, case_cites


# ---------------------------------------------------------------------------
# Voice input
# ---------------------------------------------------------------------------

def resolve_user_message(
    text: str,
    audio: tuple[int, np.ndarray] | None,
    lang: str,
) -> tuple[str, str]:
    """Returns (user_bubble_text, query_english)."""
    text = (text or "").strip()
    logger.debug("resolve_user_message: text=%r, audio type=%s",
                 text[:80] if text else "", type(audio).__name__)

    if text:
        q_en = text_to_query_english(text, lang)
        return (text, q_en)

    if audio is not None:
        sr, data = audio
        if data is not None and len(np.asarray(data)) > 0:
            if not sarvam_configured():
                raise RuntimeError("Set SARVAM_API_KEY for voice input (Sarvam STT).")
            wav = numpy_audio_to_wav_bytes(np.asarray(data), int(sr))
            mode = os.environ.get("SARVAM_STT_MODE", "translate").strip()
            lang_hint = bcp47_target(lang) if mode == "transcribe" else None
            st = speech_to_text_file(wav, mode=mode, language_code=lang_hint)
            tr = transcript_from_stt_response(st)
            if mode == "translate":
                return (f"[Voice] {tr}", tr.strip())
            q_en = _maybe_translate(tr, source="auto", target="en-IN")
            return (f"[Voice] {tr}", q_en.strip())

    raise ValueError("Type a question or record audio. If you just recorded, wait for the audio to finish processing then try again.")


# ---------------------------------------------------------------------------
# Response formatting
# ---------------------------------------------------------------------------

def build_reply_markdown(
    assistant_en: str,
    law_cites: str,
    case_cites: str,
    lang: str,
) -> str:
    """Build response with law citations, case citations, and optional translation."""

    sources_block = (
        f"**Statutory Sources**\n{law_cites}\n\n"
        f"**Precedent Cases Cited**\n{case_cites}"
    )

    if lang == "en" or not sarvam_configured():
        return (
            f"{assistant_en}\n\n---\n{sources_block}"
            f"\n\n---\n*{DISCLAIMER_EN}*"
        )

    tgt = bcp47_target(lang)
    body_translated = _maybe_translate(assistant_en, source="en-IN", target=tgt)
    disc_translated = _maybe_translate(DISCLAIMER_EN, source="en-IN", target=tgt)

    lang_label = dict(SARVAM_LANGUAGES).get(lang, lang)
    return (
        f"**{lang_label}:**\n\n{body_translated}\n\n"
        f"---\n**English:**\n\n{assistant_en}\n\n"
        f"---\n{sources_block}"
        f"\n\n---\n*{disc_translated}*"
    )


def maybe_tts(text_markdown: str, lang: str, enabled: bool) -> tuple[int, np.ndarray] | None:
    if not enabled or not sarvam_configured():
        return None
    narrative = text_markdown.split("\n---\n", 1)[0]
    import re
    narrative = re.sub(r"^\*\*[^*]+:\*\*\s*", "", narrative.strip())
    plain = strip_markdown_for_tts(narrative)
    if not plain.strip():
        return None
    tgt = bcp47_target(lang)
    try:
        wav = text_to_speech_wav_bytes(plain, target_language_code=tgt)
        sr, arr = wav_bytes_to_numpy_float32(wav)
        return (sr, arr)
    except Exception as e:
        logger.warning("TTS failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Gradio turn handler
# ---------------------------------------------------------------------------

def run_turn(
    message: str,
    audio: tuple[int, np.ndarray] | None,
    history: list | None,
    lang: str,
    tts_on: bool,
    court_filter: str,
    argument_style: str,
) -> tuple[str, list, tuple[int, np.ndarray] | None, None]:
    """Process one chat turn: user input -> RAG + Cases -> LLM -> response."""
    history = [list(pair) for pair in history] if history else []
    try:
        user_show, q_en = resolve_user_message(message, audio, lang)
        assistant_en, law_cites, case_cites = _rag_answer_with_cases(
            q_en, court_filter, argument_style,
        )
        reply_md = build_reply_markdown(assistant_en, law_cites, case_cites, lang)
        history.append([user_show, reply_md])
        audio_out = maybe_tts(reply_md, lang, tts_on)
        return "", history, audio_out, None
    except Exception as e:
        logger.exception("run_turn")
        err = f"**Error:** {e}"
        history.append([message or "[Voice] (audio)", err])
        return "", history, None, None


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def build_app() -> gr.Blocks:
    custom_css = """
    .gradio-container { background-color: #F7F3ED !important; }
    footer { font-size: 0.85rem; color: #2A5297; }
    h1 { color: #0D1B3E; font-family: Georgia, serif; }

    @media (prefers-color-scheme: dark) {
        .gradio-container { background-color: #1a1a2e !important; }
        h1 { color: #e0d8cc; }
        footer { color: #8ea4c8; }
    }
    .dark .gradio-container { background-color: #1a1a2e !important; }
    .dark h1 { color: #e0d8cc; }
    .dark footer { color: #8ea4c8; }

    /* Advocate tool styling */
    .settings-panel { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
    """

    with gr.Blocks(
        theme=gr.themes.Soft(primary_hue="slate", secondary_hue="orange"),
        css=custom_css,
        title="Nyaya Dhwani - Legal Research Assistant",
    ) as demo:
        gr.Markdown(
            "# Nyaya Dhwani\n"
            "*AI-powered legal research assistant for Indian advocates*\n\n"
            "Search BNS/IPC provisions and find relevant court precedents with cited cases."
        )

        lang_state = gr.State("en")

        # ---- Welcome Screen ----
        with gr.Column(visible=True) as welcome_col:
            gr.Markdown("### Welcome")
            gr.Markdown(
                "Nyaya Dhwani helps advocates and legal professionals research Indian law. "
                "It retrieves relevant BNS/IPC sections **and** searches for real court "
                "precedent cases from Indian Kanoon to provide cited legal analysis."
            )
            lang_radio = gr.Radio(
                choices=[(c[1], c[0]) for c in SARVAM_LANGUAGES],
                value="en",
                label="Select your language",
                info="Non-English questions are translated for retrieval, "
                "then answers are translated back to your language.",
            )
            begin_btn = gr.Button("Begin", variant="primary")
            gr.Markdown(
                "<small>Not a substitute for legal counsel. General information only. "
                "Powered by Databricks (Llama Maverick) + Indian Kanoon API + Sarvam AI</small>"
            )

        # ---- Chat Screen ----
        with gr.Column(visible=False) as chat_col:
            current_lang = gr.Markdown("*Session language: English*")

            # -- Research Settings --
            with gr.Accordion("Research Settings", open=False):
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

            # -- Topic chips --
            topic = gr.Radio(
                choices=list(TOPIC_SEEDS.keys()),
                label="Common Legal Topics",
                value=None,
            )

            # -- Chat area --
            chatbot = gr.Chatbot(
                label="Nyaya Dhwani",
                height=480,
                bubble_full_width=False,
            )

            with gr.Row():
                msg = gr.Textbox(
                    placeholder="Ask your legal question... e.g. 'What is punishment for theft under BNS?'",
                    show_label=False,
                    lines=2,
                    scale=4,
                )
                submit = gr.Button("Search", variant="primary", scale=1)

            with gr.Accordion("Voice Input & TTS", open=False):
                audio_in = gr.Audio(
                    sources=["microphone"],
                    type="numpy",
                    label="Speak your question",
                )
                tts_cb = gr.Checkbox(label="Read answer aloud (TTS)", value=False)
                tts_out = gr.Audio(
                    label="Listen to answer",
                    type="numpy",
                    interactive=False,
                )

        # ---- Event handlers ----
        def on_begin(lang_code: str):
            labels = dict(SARVAM_LANGUAGES)
            label = labels.get(lang_code, lang_code)
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                lang_code,
                f"*Session language: {label}*",
            )

        begin_btn.click(
            on_begin,
            inputs=[lang_radio],
            outputs=[welcome_col, chat_col, lang_state, current_lang],
        )

        def fill_topic(choice: str | None):
            if not choice:
                return gr.update()
            seed = TOPIC_SEEDS.get(choice, "")
            return gr.update(value=seed)

        topic.change(fill_topic, inputs=[topic], outputs=[msg])

        _run_turn_io = dict(
            fn=run_turn,
            inputs=[msg, audio_in, chatbot, lang_state, tts_cb, court_radio, style_radio],
            outputs=[msg, chatbot, tts_out, audio_in],
        )
        submit.click(**_run_turn_io)
        msg.submit(**_run_turn_io)
        audio_in.stop_recording(**_run_turn_io)

        gr.Markdown(
            "<small>Powered by Databricks (Llama 4 Maverick + Vector Search) | "
            "Indian Kanoon API (precedent search) | "
            "Sarvam AI (translation, STT, TTS)</small>"
        )

    return demo


# ---------------------------------------------------------------------------
# Secrets loading (Databricks Apps)
# ---------------------------------------------------------------------------

def _load_secrets_from_scope() -> None:
    """Load secrets from Databricks secret scope into env vars."""
    mapping = {
        "SARVAM_API_KEY": ("nyaya-dhwani", "sarvam_api_key"),
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

    # Log which external services are configured
    logger.info("Indian Kanoon API: %s", "configured" if os.environ.get("INDIAN_KANOON_API_TOKEN") else "NOT configured")
    logger.info("Google CSE: %s", "configured" if os.environ.get("GOOGLE_API_KEY") else "NOT configured")
    logger.info("Sarvam API: %s", "configured" if sarvam_configured() else "NOT configured")

    demo = build_app()
    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()
