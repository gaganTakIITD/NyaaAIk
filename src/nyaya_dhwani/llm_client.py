"""OpenAI-compatible chat completions for Databricks Playground / serving endpoints.

Typical env (from Playground **Get code** — do not commit secrets)::

    LLM_OPENAI_BASE_URL=https://.../serving-endpoints/<endpoint>/...   # or use LLM_CHAT_COMPLETIONS_URL
    LLM_MODEL=databricks-meta-llama-3-1-8b-instruct
    DATABRICKS_TOKEN=dapi...   # or LLM_API_KEY

See ``docs/PLAYGROUND_TO_APP.md``.
"""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_TIMEOUT = 120


def _chat_url() -> str:
    full = os.environ.get("LLM_CHAT_COMPLETIONS_URL", "").strip()
    if full:
        return full
    base = os.environ.get("LLM_OPENAI_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError(
            "Set LLM_CHAT_COMPLETIONS_URL (full POST URL) or LLM_OPENAI_BASE_URL (OpenAI-style base; "
            "/v1/chat/completions is appended when missing)."
        )
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _bearer() -> str:
    return (
        os.environ.get("DATABRICKS_TOKEN", "").strip()
        or os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )


def chat_completions(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """POST OpenAI-compatible chat/completions; returns parsed JSON body."""
    url = _chat_url()
    token = _bearer()
    if not token:
        raise RuntimeError(
            "Set DATABRICKS_TOKEN, LLM_API_KEY, or OPENAI_API_KEY for LLM calls."
        )
    model = (model or os.environ.get("LLM_MODEL", "")).strip()
    if not model:
        raise RuntimeError("Set LLM_MODEL (or pass model=).")
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def extract_assistant_text(response: dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Unexpected LLM response shape: {response!r}") from e


def rag_user_message(context_chunks: list[str], question: str) -> str:
    """Single user message with retrieved context (Playground-style)."""
    ctx = "\n\n".join(c.strip() for c in context_chunks if c and str(c).strip())
    return f"Context:\n{ctx}\n\nQuestion: {question}"
