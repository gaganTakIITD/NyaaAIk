"""OpenAI-compatible chat completions for Databricks Playground / serving endpoints.

Typical env (from Playground **Get code** — do not commit secrets).

**AI Gateway** (OpenAI SDK ``base_url`` often ends with ``/mlflow/v1``)::

    LLM_OPENAI_BASE_URL=https://<workspace-id>.ai-gateway.cloud.databricks.com/mlflow/v1
    LLM_MODEL=databricks-llama-4-maverick
    DATABRICKS_TOKEN=dapi...

We POST to ``{LLM_OPENAI_BASE_URL}/chat/completions`` (same as the OpenAI client).

See ``docs/PLAYGROUND_TO_APP.md``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120


def _chat_url() -> str:
    full = os.environ.get("LLM_CHAT_COMPLETIONS_URL", "").strip()
    if full:
        return full
    base = os.environ.get("LLM_OPENAI_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError(
            "Set LLM_CHAT_COMPLETIONS_URL (full POST URL) or LLM_OPENAI_BASE_URL "
            "(e.g. AI Gateway …/mlflow/v1 from Playground Get code)."
        )
    if base.endswith("/chat/completions"):
        return base
    # OpenAI SDK + AI Gateway Get code: base_url ends with …/mlflow/v1 (also ends with /v1).
    # OpenAI.com: …/v1  →  …/v1/chat/completions
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _bearer() -> str:
    token = (
        os.environ.get("DATABRICKS_TOKEN", "").strip()
        or os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )
    if token:
        return token
    return _sdk_oauth_token()


def _sdk_oauth_token() -> str:
    """Get a fresh OAuth token from the Databricks SDK (service principal auth).

    On Databricks Apps, the service principal uses OAuth M2M — there is no
    static PAT.  ``WorkspaceClient().config.token`` is ``None`` in that case.
    We call the SDK's internal token provider to get a short-lived token.
    """
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        logger.info("SDK auth_type=%s, host=%s", w.config.auth_type, w.config.host)
        # Try static token first (PAT auth).
        if w.config.token:
            logger.info("Using static token from SDK config")
            return w.config.token
        # OAuth M2M: config.authenticate() returns a header factory callable.
        # Calling that factory returns a dict like {"Authorization": "Bearer <token>"}.
        header_factory = w.config.authenticate()
        if callable(header_factory):
            headers = header_factory()
            if isinstance(headers, dict):
                auth = headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    logger.info("Got OAuth token from SDK (%d chars)", len(auth) - 7)
                    return auth[7:]
            logger.warning("SDK header_factory returned: %s", type(headers))
    except Exception as exc:
        logger.warning("SDK OAuth token failed: %s", exc)
    return ""


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


def complete_with_openai_sdk(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Same HTTP contract as Playground **Get code** using the official ``openai`` package.

    Requires ``pip install openai`` (optional extra ``llm_openai`` in pyproject).

    Uses ``LLM_OPENAI_BASE_URL`` (no trailing slash), ``DATABRICKS_TOKEN`` / ``LLM_API_KEY``, ``LLM_MODEL``.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("Install openai: pip install 'nyaya-dhwani[llm_openai]' or pip install openai") from e

    base = os.environ.get("LLM_OPENAI_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("Set LLM_OPENAI_BASE_URL to the Get code base_url (e.g. …/mlflow/v1).")
    token = _bearer()
    if not token:
        raise RuntimeError("Set DATABRICKS_TOKEN, LLM_API_KEY, or OPENAI_API_KEY.")
    model = (model or os.environ.get("LLM_MODEL", "")).strip()
    if not model:
        raise RuntimeError("Set LLM_MODEL (or pass model=).")

    client = OpenAI(api_key=token, base_url=base)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()
