"""Gradio entrypoint: RAG + Maverick + Sarvam (STT / Mayura / Bulbul). See docs/PLAN.md."""

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

from nyaya_dhwani.embedder import SentenceEmbedder
from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text, rag_user_message
from nyaya_dhwani.retrieval import CorpusIndex
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

# UC Volume path (only accessible from notebooks/clusters, not Databricks Apps).
_VOLUME_INDEX_PATH = "/Volumes/main/india_legal/legal_files/nyaya_index"
# Local cache dir where the index is downloaded at startup on Databricks Apps.
_LOCAL_INDEX_CACHE = "/tmp/nyaya_index"
DEFAULT_INDEX_DIR = _VOLUME_INDEX_PATH

TOPIC_SEEDS: dict[str, str] = {
    "Tenant rights": "What are my basic rights as a tenant in India regarding eviction and rent increases?",
    "Divorce law": "What are the grounds for divorce under Indian law for mutual consent?",
    "Consumer cases": "How do I file a consumer complaint in India for defective goods?",
    "Property law": "What documents should I check before buying residential property in India?",
    "Labour rights": "What are an employee's rights regarding notice period and gratuity?",
    "FIR / Police": "What is the procedure to file an FIR and what are my rights when arrested?",
    "Domestic violence": "What legal protections exist for victims of domestic violence in India?",
    "RTI": "How do I file a Right to Information application and what fees apply?",
}

SARVAM_LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("hi", "Hindi · हिन्दी"),
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

# UI ISO-ish code → BCP-47 for Mayura / STT hints (best-effort for ur/as)
UI_TO_BCP47: dict[str, str] = {
    "en": "en-IN",
    "hi": "hi-IN",
    "bn": "bn-IN",
    "te": "te-IN",
    "mr": "mr-IN",
    "ta": "ta-IN",
    "gu": "gu-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "pa": "pa-IN",
    "or": "od-IN",
    "ur": "hi-IN",
    "as": "bn-IN",
}

DISCLAIMER_EN = (
    "This information is for general awareness only and does not constitute legal advice. "
    "Consult a qualified lawyer for your specific situation."
)

SYSTEM_PROMPT = (
    "You are Nyaya Dhwani, an assistant for Indian legal information. "
    "Answer using the Context below when it is relevant. Cite Acts or sections when the context supports it. "
    "If the context is insufficient, say so briefly. "
    "Do not claim to be a lawyer. Keep answers clear and structured. "
    "Respond in English."
)


def _download_index_from_volume(volume_path: str, local_dir: str) -> str:
    """Download index files from a UC Volume to a local directory using the Databricks SDK.

    UC Volume paths (``/Volumes/...``) are FUSE-mounted on clusters/notebooks but
    **not** available in Databricks Apps.  The SDK ``files`` API can read them.
    """
    from pathlib import Path
    local = Path(local_dir)
    if (local / "manifest.json").exists():
        logger.info("Index already cached at %s", local)
        return str(local)

    logger.info("Downloading index from Volume %s → %s", volume_path, local)
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    local.mkdir(parents=True, exist_ok=True)
    for item in w.files.list_directory_contents(volume_path):
        if item.is_directory:
            continue
        dest = local / item.name
        logger.info("  downloading %s (%s bytes)", item.name, item.file_size)
        with w.files.download(item.path).contents as src, open(dest, "wb") as dst:
            while True:
                chunk = src.read(8 * 1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
    logger.info("Index download complete → %s", local)
    return str(local)


def index_dir() -> str:
    """Resolve the index directory, downloading from the UC Volume if needed."""
    path = os.environ.get("NYAYA_INDEX_DIR", DEFAULT_INDEX_DIR).strip()
    # If the path is a UC Volume and doesn't exist locally (Databricks Apps),
    # download via the SDK.
    if path.startswith("/Volumes/") and not Path(path).exists():
        path = _download_index_from_volume(path, _LOCAL_INDEX_CACHE)
    return path


def bcp47_target(lang: str) -> str:
    return UI_TO_BCP47.get(lang, "en-IN")


class RAGRuntime:
    """Lazy-load FAISS + embedder (same embedding model as manifest)."""

    def __init__(self) -> None:
        self._ci: CorpusIndex | None = None
        self._embedder: SentenceEmbedder | None = None

    def load(self) -> None:
        if self._ci is not None:
            return
        path = index_dir()
        logger.info("Loading CorpusIndex from %s", path)
        self._ci = CorpusIndex.load(path)
        m = self._ci.manifest
        self._embedder = SentenceEmbedder(
            model_name=m.embedding_model,
            normalize=m.normalize_embeddings,
        )
        logger.info("Loaded index (%d vectors), embedder %s", m.num_vectors, m.embedding_model)

    @property
    def ci(self) -> CorpusIndex:
        if self._ci is None:
            raise RuntimeError("RAGRuntime not loaded")
        return self._ci

    @property
    def embedder(self) -> SentenceEmbedder:
        if self._embedder is None:
            raise RuntimeError("RAGRuntime not loaded")
        return self._embedder


_runtime: RAGRuntime | None = None


def get_runtime() -> RAGRuntime:
    global _runtime
    if _runtime is None:
        _runtime = RAGRuntime()
    return _runtime


def _format_citations(chunks_df) -> str:
    lines: list[str] = []
    for _, row in chunks_df.iterrows():
        title = row.get("title") or ""
        source = row.get("source") or ""
        doc_type = row.get("doc_type") or ""
        bits = [str(x).strip() for x in (title, source, doc_type) if x and str(x).strip()]
        if bits:
            lines.append("- " + " · ".join(bits[:3]))
    return "\n".join(lines) if lines else "(no metadata)"


def _rag_answer_english(query_en: str) -> tuple[str, str]:
    """LLM answer in English + citations block."""
    rt = get_runtime()
    rt.load()
    q = query_en.strip()
    emb = rt.embedder.encode([q])
    chunks_df = rt.ci.search(emb, k=5)
    texts = chunks_df["text"].tolist() if "text" in chunks_df.columns else []
    user_content = rag_user_message([str(t) for t in texts], q)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    raw = chat_completions(messages, max_tokens=2048, temperature=0.2)
    assistant_en = extract_assistant_text(raw)
    cites = _format_citations(chunks_df)
    return assistant_en, cites


def _maybe_translate(text: str, *, source: str, target: str) -> str:
    if source == target:
        return text
    if not sarvam_configured():
        return text
    try:
        return translate_text(text, source_language_code=source, target_language_code=target)
    except Exception as e:
        logger.warning("Mayura translate failed, using English: %s", e)
        return text


def text_to_query_english(user_text: str, lang: str) -> str:
    """Non-English typed input → English for embedding/RAG (Mayura)."""
    t = user_text.strip()
    if not t:
        return t
    if lang == "en":
        return t
    if not sarvam_configured():
        logger.warning("SARVAM_API_KEY missing — using raw text for retrieval (degraded).")
        return t
    return _maybe_translate(t, source="auto", target="en-IN")


def resolve_user_message(
    text: str,
    audio: tuple[int, np.ndarray] | None,
    lang: str,
) -> tuple[str, str]:
    """Returns ``(user_bubble_text, query_english)``."""
    text = (text or "").strip()
    logger.debug("resolve_user_message: text=%r, audio type=%s",
                 text[:80] if text else "", type(audio).__name__)

    # Prefer typed text over audio (Gradio retains stale audio recordings).
    if text:
        q_en = text_to_query_english(text, lang)
        return (text, q_en)

    # Fall back to audio only when no text was typed.
    if audio is not None:
        sr, data = audio
        if data is not None and len(np.asarray(data)) > 0:
            if not sarvam_configured():
                raise RuntimeError("Set SARVAM_API_KEY for voice input (Sarvam STT).")
            wav = numpy_audio_to_wav_bytes(np.asarray(data), int(sr))
            mode = os.environ.get("SARVAM_STT_MODE", "translate").strip()
            lang_hint = bcp47_target(lang) if mode == "transcribe" else None
            st = speech_to_text_file(
                wav,
                mode=mode,
                language_code=lang_hint,
            )
            tr = transcript_from_stt_response(st)
            if mode == "translate":
                return (f"🎤 {tr}", tr.strip())
            q_en = _maybe_translate(tr, source="auto", target="en-IN")
            return (f"🎤 {tr}", q_en.strip())

    raise ValueError("Type a question or record audio.")


def build_reply_markdown(assistant_en: str, cites: str, lang: str) -> str:
    """Translate answer + disclaimer when session language ≠ English and Sarvam is configured."""
    if lang == "en" or not sarvam_configured():
        disc = DISCLAIMER_EN
        body = assistant_en
    else:
        tgt = bcp47_target(lang)
        body = _maybe_translate(assistant_en, source="en-IN", target=tgt)
        disc = _maybe_translate(DISCLAIMER_EN, source="en-IN", target=tgt)

    return (
        f"{body}\n\n---\n**Sources (retrieval)**\n{cites}\n\n---\n*{disc}*"
    )


def maybe_tts(text_markdown: str, lang: str, enabled: bool) -> tuple[int, np.ndarray] | None:
    if not enabled or not sarvam_configured():
        return None
    # Narrative only (before Sources); avoid reading citation list aloud
    narrative = text_markdown.split("\n---\n", 1)[0]
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


def run_turn(
    message: str,
    audio: tuple[int, np.ndarray] | None,
    history: list | None,
    lang: str,
    tts_on: bool,
) -> tuple[str, list, tuple[int, np.ndarray] | None, None]:
    # Tuple pairs [[user, assistant], ...] — default Chatbot format. Avoids
    # `type="messages"` JSON schemas that break gradio_client api_info on Gradio 4.44.x.
    # Returns (msg_text, history, tts_audio, audio_in_clear).
    history = [list(pair) for pair in history] if history else []
    try:
        user_show, q_en = resolve_user_message(message, audio, lang)
        assistant_en, cites = _rag_answer_english(q_en)
        reply_md = build_reply_markdown(assistant_en, cites, lang)
        history.append([user_show, reply_md])
        audio_out = maybe_tts(reply_md, lang, tts_on)
        return "", history, audio_out, None
    except Exception as e:
        logger.exception("run_turn")
        err = f"**Error:** {e}"
        history.append([message or "🎤 (audio)", err])
        return "", history, None, None


def build_app() -> gr.Blocks:
    custom_css = """
    .gradio-container { background-color: #F7F3ED !important; }
    footer { font-size: 0.85rem; color: #2A5297; }
    h1 { color: #0D1B3E; font-family: Georgia, serif; }
    """

    with gr.Blocks(
        theme=gr.themes.Soft(primary_hue="slate", secondary_hue="orange"),
        css=custom_css,
        title="Nyaya Dhwani",
    ) as demo:
        gr.Markdown(
            "# Nyaya Dhwani · न्याय ध्वनि\n"
            "*Legal information assistant for India · Not a substitute for legal counsel*"
        )

        lang_state = gr.State("en")

        with gr.Column(visible=True) as welcome_col:
            gr.Markdown("### Welcome")
            lang_radio = gr.Radio(
                choices=[(c[0], c[1]) for c in SARVAM_LANGUAGES],
                value="en",
                label="Select your language / अपनी भाषा चुनें",
                info="Typed questions in other languages use **Mayura** (needs SARVAM_API_KEY). "
                "Retrieval/embeddings use English after translation.",
            )

            begin_btn = gr.Button("Begin / शुरू करें", variant="primary")
            gr.Markdown(
                "<small>Not a substitute for legal counsel · General information only · "
                "Powered by Sarvam (STT / translate / TTS) when configured</small>"
            )

        with gr.Column(visible=False) as chat_col:
            gr.Markdown("### Chat")
            current_lang = gr.Markdown("*Session language: English*")

            topic = gr.Radio(
                choices=list(TOPIC_SEEDS.keys()),
                label="Common topics",
                value=None,
            )
            chatbot = gr.Chatbot(
                label="Nyaya Dhwani",
                height=420,
                bubble_full_width=False,
            )
            msg = gr.Textbox(
                placeholder="Type your legal question (any supported language if Sarvam is set)…",
                show_label=False,
                lines=2,
            )
            audio_in = gr.Audio(
                sources=["microphone"],
                type="numpy",
                label="Or speak your question",
            )
            tts_cb = gr.Checkbox(
                label="Read answer aloud (Sarvam Bulbul TTS)",
                value=False,
            )
            tts_out = gr.Audio(
                label="Listen to answer",
                type="numpy",
                interactive=False,
            )
            submit = gr.Button("Send", variant="primary")

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

        submit.click(
            run_turn,
            inputs=[msg, audio_in, chatbot, lang_state, tts_cb],
            outputs=[msg, chatbot, tts_out, audio_in],
        )
        msg.submit(
            run_turn,
            inputs=[msg, audio_in, chatbot, lang_state, tts_cb],
            outputs=[msg, chatbot, tts_out, audio_in],
        )

        gr.Markdown(
            "<small>RAG index on UC Volume · LLM: Databricks Llama Maverick · "
            "Sarvam: Saaras STT, Mayura translate, Bulbul TTS (`SARVAM_API_KEY`)</small>"
        )

    return demo


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    demo = build_app()
    demo.queue()
    # Match Databricks app-templates: bare launch() lets the platform
    # inject GRADIO_SERVER_NAME, GRADIO_SERVER_PORT, GRADIO_ROOT_PATH etc.
    demo.launch()


if __name__ == "__main__":
    main()
