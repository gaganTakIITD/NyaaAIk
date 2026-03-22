"""Gradio entrypoint: RAG + Databricks Llama Maverick. Deploy on Databricks Apps (see docs/PLAN.md)."""

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

from nyaya_dhwani.embedder import SentenceEmbedder
from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text, rag_user_message
from nyaya_dhwani.retrieval import CorpusIndex

logger = logging.getLogger(__name__)

DEFAULT_INDEX_DIR = "/Volumes/main/india_legal/legal_files/nyaya_index"

# UI_design.md — topic chips (English seed questions; P0 text path)
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

# (code, label) — subset of Sarvam-supported languages; session language for future STT/TTS (P1)
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

DISCLAIMER_EN = (
    "This information is for general awareness only and does not constitute legal advice. "
    "Consult a qualified lawyer for your specific situation."
)

SYSTEM_PROMPT = (
    "You are Nyaya Dhwani, an assistant for Indian legal information. "
    "Answer using the Context below when it is relevant. Cite Acts or sections when the context supports it. "
    "If the context is insufficient, say so briefly. "
    "Do not claim to be a lawyer. Keep answers clear and structured."
)


def index_dir() -> str:
    return os.environ.get("NYAYA_INDEX_DIR", DEFAULT_INDEX_DIR).strip()


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


def answer_question(user_text: str) -> str:
    """Retrieve + Maverick completion + citations + disclaimer."""
    rt = get_runtime()
    rt.load()
    q = user_text.strip()
    emb = rt.embedder.encode([q])
    chunks_df = rt.ci.search(emb, k=5)
    texts = chunks_df["text"].tolist() if "text" in chunks_df.columns else []
    user_content = rag_user_message([str(t) for t in texts], q)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    raw = chat_completions(messages, max_tokens=2048, temperature=0.2)
    assistant = extract_assistant_text(raw)
    cites = _format_citations(chunks_df)
    return (
        f"{assistant}\n\n---\n**Sources (retrieval)**\n{cites}\n\n---\n*{DISCLAIMER_EN}*"
    )


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
                info="P0: questions work best in **English** (multilingual STT/translate in P1).",
            )

            begin_btn = gr.Button("Begin / शुरू करें", variant="primary")
            gr.Markdown(
                "<small>Not a substitute for legal counsel · General information only</small>"
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
                type="messages",
            )
            msg = gr.Textbox(
                placeholder="Type your legal question (English recommended for P0)…",
                show_label=False,
                lines=2,
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

        def chat_fn(message: str, history: list | None):
            history = list(history) if history else []
            if not message or not str(message).strip():
                return "", history
            try:
                reply = answer_question(message)
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": reply})
                return "", history
            except Exception as e:
                logger.exception("chat_fn")
                err = f"**Error:** {e}"
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": err})
                return "", history

        submit.click(chat_fn, inputs=[msg, chatbot], outputs=[msg, chatbot])
        msg.submit(chat_fn, inputs=[msg, chatbot], outputs=[msg, chatbot])

        gr.Markdown(
            "<small>Retrieval from your workspace index · LLM: Databricks Llama Maverick · "
            "Sarvam voice/translate: planned (P1)</small>"
        )

    return demo


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    port = int(os.environ.get("PORT", "7860"))
    host = os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0")
    demo = build_app()
    demo.queue()
    demo.launch(
        server_name=host,
        server_port=port,
        show_api=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
