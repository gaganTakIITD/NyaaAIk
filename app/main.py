"""Flask entrypoint: NyaaAIk Legal Research — RAG + Maverick + Live Cases + Document Upload."""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import uuid
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
# In-memory document store (keyed by doc_id UUID)
# Each entry: { "filename": str, "text": str, "page_count": int | None }
# This is per-process state — fine for Databricks Apps (single worker)
# ---------------------------------------------------------------------------
_DOC_STORE: dict[str, dict] = {}

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
# Document text extraction (server-side, lightweight)
# Maverick handles all the heavy reasoning — we just need raw text.
# ---------------------------------------------------------------------------

# MIME types for images supported by Maverick vision API
_IMAGE_EXTS = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
_TEXT_EXTS = {"pdf", "docx", "doc", "txt", "md", "text", "rst"}


def _extract_text_pdf(file_bytes: bytes) -> tuple[str, int]:
    """Extract text from PDF bytes using pypdf. Returns (text, page_count)."""
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages), len(reader.pages)
    except ImportError:
        raise RuntimeError("pypdf not installed. Run: pip install pypdf")
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def _extract_text_docx(file_bytes: bytes) -> tuple[str, int]:
    """Extract text from DOCX bytes using python-docx."""
    try:
        import docx  # type: ignore
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        word_count = len(text.split())
        page_count = max(1, round(word_count / 500))
        return text, page_count
    except ImportError:
        raise RuntimeError("python-docx not installed. Run: pip install python-docx")
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}")


def _extract_text_plain(file_bytes: bytes) -> tuple[str, int]:
    """Extract text from plain text / markdown files."""
    try:
        text = file_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        text = file_bytes.decode("latin-1", errors="replace").strip()
    word_count = len(text.split())
    page_count = max(1, round(word_count / 500))
    return text, page_count


def _extract_document(filename: str, file_bytes: bytes) -> tuple[str, int]:
    """Dispatch to the right extractor based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return _extract_text_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return _extract_text_docx(file_bytes)
    elif ext in ("txt", "md", "text", "rst"):
        return _extract_text_plain(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Supported: PDF, DOCX, TXT, MD, PNG, JPG, WEBP")


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

def _build_system_prompt(argument_style: str, court_filter: str, persona: str = "advocate") -> str:
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

    if persona == "citizen":
        # Plain language for ordinary people with no legal background
        return f"""You are NyaaAIk, a friendly AI legal assistant helping ordinary Indian citizens understand the law.

PERSONA: You are speaking to a common person who has NO legal background. They need clarity, not jargon.

LANGUAGE RULES (STRICT):
- Use SIMPLE everyday English. Avoid Latin phrases, legal jargon, and technical terms.
- If you must use a legal term (e.g. "bail"), explain it in brackets immediately: bail (temporary release from police custody).
- Use short sentences. Write like you're explaining to a friend.
- Replace "pursuant to" with "under", "aforementioned" with "the above", "notwithstanding" with "even though".
- Use analogies and real-life examples to explain abstract concepts.

STRUCTURE:
1. **What the law says** (in simple words — what is this law about)
2. **What it means for you** (practical implication in your situation)
3. **What relevant court cases have decided** (explain what happened and the outcome simply)
4. **What you should do next** (practical steps — e.g. go to police station, consult a lawyer, file complaint)
5. **Important warning** (brief disclaimer in plain words)

ARGUMENT STYLE: {style_instruction}
COURT PREFERENCE: {court_instruction}

Remember: Empathy first. This person may be scared or confused. Be reassuring and clear.
Always end with: "I strongly recommend consulting a lawyer for your specific situation." """

    else:
        # Advocate / legal professional — full courtroom English
        return f"""You are NyaaAIk, an AI legal research assistant for Indian advocates and legal professionals.

PERSONA: You are addressing a trained legal professional — advocate, solicitor, or legal researcher.

ROLE: Provide rigorous legal analysis with precise statutory citations, ratio decidendi, and persuasive legal reasoning.

INSTRUCTIONS:
1. STATUTORY FRAMEWORK: Cite specific provisions of BNS (Bharatiya Nyaya Sanhita 2023), BNSS (Bharatiya Nagarik Suraksha Sanhita), BSA (Bharatiya Sakshya Adhiniyam). Cross-reference corresponding IPC / CrPC / Evidence Act provisions where applicable.
2. PRECEDENT ANALYSIS — For each case cited:
   - State the full citation (case name, court, year, AIR/SCC/SCR reference if known)
   - State the ratio decidendi (the legal principle that binds)
   - Distinguish obiter dicta where relevant
   - Explain its precedential weight and applicability to the instant matter
3. ARGUMENT STYLE: {style_instruction}
4. COURT PREFERENCE: {court_instruction}
5. STRUCTURE your response as a legal brief:
   (a) Statutory Provisions (precise section numbers, sub-sections, provisos)
   (b) Case Law Analysis (citation, ratio, relevance, precedential value)
   (c) Legal Principles (applicable doctrines — mens rea, actus reus, locus standi, res judicata etc.)
   (d) Submission / Analysis (connecting statutory + case law to the matter at hand)
   (e) Conclusion & Recommendation
6. If documents are provided, analyze them through the relevant legal lens and identify issues.
7. Use formal courtroom English throughout. Precision over brevity.

Always conclude with the standard disclaimer regarding AI-generated legal research."""



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

def _format_law_citations(chunks_df) -> list:
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
    doc_ids: list | None = None,
    persona: str = "advocate",
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

    # --- Uploaded Document Context (via Maverick) ---
    # Text docs: injected as text blocks into the prompt
    # Image docs: injected as base64 vision parts in the final user message
    doc_context = ""
    image_doc_parts: list[dict] = []  # multimodal vision content items
    if doc_ids:
        text_parts = []
        for doc_id in doc_ids:
            doc = _DOC_STORE.get(doc_id)
            if not doc:
                continue
            if doc.get("is_image"):
                # Maverick vision: send base64 image directly
                mime = doc["mime_type"]
                b64 = doc["b64"]
                image_doc_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
                text_parts.append(f"--- IMAGE DOCUMENT: {doc['filename']} (attached above for visual analysis) ---")
            else:
                truncated = doc["text"][:6000]
                if len(doc["text"]) > 6000:
                    truncated += "\n\n[... document truncated for context limit ...]"
                text_parts.append(
                    f"--- DOCUMENT: {doc['filename']} ---\n{truncated}\n--- END DOCUMENT ---"
                )
        if text_parts:
            doc_context = "\n\n".join(text_parts)

    # --- Build LLM prompt with full history ---
    system_prompt = _build_system_prompt(argument_style, court_filter, persona)

    # Compose user content block
    content_parts = []
    if law_context:
        content_parts.append(f"RELEVANT LAW SECTIONS (BNS / Constitution / Statutes):\n{law_context}")
    if cases_context:
        content_parts.append(f"PRECEDENT COURT CASES:\n{cases_context}")
    if doc_context:
        content_parts.append(f"UPLOADED DOCUMENT CONTEXT (analyze alongside law and precedents):\n{doc_context}")
    content_parts.append(f"USER QUERY: {q}")

    user_content = "\n\n".join(content_parts)

    messages = [{"role": "system", "content": system_prompt}]

    # Add ALL previous turns for full context
    if chat_history:
        for turn in chat_history:
            if turn.get("role") == "user":
                messages.append({"role": "user", "content": turn["content"]})
            elif turn.get("role") == "assistant":
                messages.append({"role": "assistant", "content": turn["content"]})

    # If there are image docs, use multimodal content format for the final user message
    if image_doc_parts:
        final_user_content: list[dict] | str = [
            {"type": "text", "text": user_content},
            *image_doc_parts,
        ]
    else:
        final_user_content = user_content

    messages.append({"role": "user", "content": final_user_content})

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


# React Router: serve index.html for all non-API routes (SPA fallback)
@app.route("/<path:path>")
def spa_fallback(path):
    if path.startswith("api/"):
        from flask import abort
        abort(404)
    static_dir = str(Path(__file__).parent / "static")
    static_file = Path(static_dir) / path
    if static_file.is_file():
        return send_from_directory(static_dir, path)
    return send_from_directory(static_dir, "index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    query = data.get("query", "").strip()
    court = data.get("court", "all")
    style = data.get("style", "neutral")
    persona = data.get("persona", "advocate")
    history = data.get("history", [])
    doc_ids = data.get("doc_ids", [])

    if not query:
        return jsonify({"error": "Please enter a legal question."}), 400

    try:
        result = _rag_answer_with_cases(query, court, style, history, doc_ids, persona)
        return jsonify(result)
    except Exception as e:
        logger.exception("api_chat error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    """Receive audio blob from browser MediaRecorder → Sarvam Saaras v3 STT → transcript."""
    from src.nyaya_dhwani.sarvam_client import is_configured, speech_to_text_file, transcript_from_stt_response

    if not is_configured():
        return jsonify({"error": "SARVAM_API_KEY is not configured on this server."}), 503

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    language_code = request.form.get("language", "hi-IN")
    audio_bytes = audio_file.read()

    if len(audio_bytes) < 1000:
        return jsonify({"error": "Audio too short — please speak for at least 1 second."}), 400
    if len(audio_bytes) > 20 * 1024 * 1024:
        return jsonify({"error": "Audio too large (max 20 MB)"}), 413

    try:
        # Sarvam STT: mode=transcribe keeps original language, mode=translate → English
        resp = speech_to_text_file(
            audio_bytes,
            filename=audio_file.filename or "recording.webm",
            mode="transcribe",
            language_code=language_code,
        )
        transcript = transcript_from_stt_response(resp)
        return jsonify({"transcript": transcript, "language": language_code})
    except Exception as e:
        logger.exception("api_transcribe error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Accept a document, extract text server-side, store for Maverick injection."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    try:
        file_bytes = file.read()
        if len(file_bytes) > 10 * 1024 * 1024:  # 10 MB limit
            return jsonify({"error": "File too large. Maximum size is 10 MB."}), 413

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        doc_id = str(uuid.uuid4())

        if ext in _IMAGE_EXTS:
            # ---- Image: store as base64 → Maverick processes it natively via vision API ----
            import base64 as _b64
            b64_str = _b64.b64encode(file_bytes).decode("ascii")
            mime = _IMAGE_EXTS[ext]
            _DOC_STORE[doc_id] = {
                "filename": file.filename,
                "is_image": True,
                "b64": b64_str,
                "mime_type": mime,
                "page_count": 1,
                "text": "",  # No text extraction — Maverick sees it directly
            }
            preview = f"Image file — Maverick will analyze visually ({len(file_bytes)//1024} KB)"
            page_count = 1
            logger.info("Uploaded image: %s (%s, doc_id=%s)", file.filename, mime, doc_id)
        else:
            # ---- Text/PDF/DOCX: extract text ----
            text, page_count = _extract_document(file.filename, file_bytes)
            if not text.strip():
                return jsonify({"error": "Could not extract text from this file. It may be a scanned image — try uploading it as PNG/JPG for Maverick vision analysis."}), 422
            _DOC_STORE[doc_id] = {
                "filename": file.filename,
                "is_image": False,
                "text": text,
                "page_count": page_count,
            }
            preview = text.strip()[:150].replace("\n", " ")
            logger.info("Uploaded doc: %s (%d pages, doc_id=%s)", file.filename, page_count, doc_id)

        return jsonify({
            "doc_id": doc_id,
            "filename": file.filename,
            "page_count": page_count,
            "preview": preview,
            "is_image": ext in _IMAGE_EXTS,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("api_upload error")
        return jsonify({"error": f"Upload processing failed: {e}"}), 500


@app.route("/api/documents", methods=["GET"])
def api_documents():
    """List currently stored documents (metadata only, no text)."""
    docs = [
        {
            "doc_id": doc_id,
            "filename": info["filename"],
            "page_count": info["page_count"],
            "char_count": len(info["text"]),
        }
        for doc_id, info in _DOC_STORE.items()
    ]
    return jsonify(docs)


@app.route("/api/documents/<doc_id>", methods=["DELETE"])
def api_delete_document(doc_id):
    """Remove a document from the store."""
    if doc_id in _DOC_STORE:
        del _DOC_STORE[doc_id]
        return jsonify({"status": "deleted", "doc_id": doc_id})
    return jsonify({"error": "Document not found"}), 404


@app.route("/api/topics", methods=["GET"])
def api_topics():
    return jsonify(TOPIC_SEEDS)


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "app": "NyaaAIk",
        "docs_stored": len(_DOC_STORE),
        "model": os.environ.get("LLM_MODEL", "unknown"),
    })


# ---------------------------------------------------------------------------
# Secrets loading
# ---------------------------------------------------------------------------

def _load_secrets_from_scope() -> None:
    mapping = {
        "INDIAN_KANOON_API_TOKEN": ("nyaya-dhwani", "indian_kanoon_api_token"),
        "SARVAM_API_KEY":          ("nyaya-dhwani", "sarvam_api_key"),
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
    logger.info("Sarvam STT (Saaras): %s",
                "configured" if os.environ.get("SARVAM_API_KEY") else "NOT configured — voice input disabled")

    port = int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", "8000")))
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")

    logger.info("Starting NyaaAIk on %s:%d", host, port)
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
