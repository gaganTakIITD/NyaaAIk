"""Sarvam HTTP helpers (chat, etc.). Set ``SARVAM_API_KEY`` in the environment.

In a Databricks notebook, set once from Secrets::

    import os
    os.environ[\"SARVAM_API_KEY\"] = dbutils.secrets.get(
        scope=\"nyaya-dhwani\", key=\"sarvam_api_key\"
    )
"""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"
DEFAULT_MODEL = "sarvam-m"


def get_api_key() -> str:
    return os.environ.get("SARVAM_API_KEY", "").strip()


def chat_completions(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 512,
    timeout: int = 60,
) -> dict[str, Any]:
    """OpenAI-compatible chat; returns parsed JSON."""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Export it or set from dbutils.secrets in the notebook."
        )
    r = requests.post(
        DEFAULT_CHAT_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
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


def extract_message_text(response: dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Unexpected Sarvam response shape: {response!r}") from e
