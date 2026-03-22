"""Sarvam HTTP helpers: chat, translation (Mayura), STT (Saaras), TTS (Bulbul).

Set ``SARVAM_API_KEY`` in the environment (same key for REST endpoints that use
``api-subscription-key`` and for chat ``Authorization: Bearer``).

In a Databricks notebook::

    import os
    os.environ[\"SARVAM_API_KEY\"] = dbutils.secrets.get(
        scope=\"nyaya-dhwani\", key=\"sarvam_api_key\"
    )
"""

from __future__ import annotations

import base64
import io
import os
import re
import wave
from typing import Any

import numpy as np
import requests

DEFAULT_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"
DEFAULT_MODEL = "sarvam-m"

DEFAULT_TRANSLATE_URL = "https://api.sarvam.ai/translate"
DEFAULT_STT_URL = "https://api.sarvam.ai/speech-to-text"
DEFAULT_TTS_URL = "https://api.sarvam.ai/text-to-speech"


def get_api_key() -> str:
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    # TODO: remove this debug log after confirming key loads correctly
    import logging as _logging
    _logging.getLogger(__name__).warning("SARVAM_API_KEY: %r (len=%d)", key, len(key))
    return key


def is_configured() -> bool:
    return bool(get_api_key())


def _bearer_headers() -> dict[str, str]:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Export it or set from dbutils.secrets in the notebook."
        )
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _subscription_headers(*, json_body: bool = True) -> dict[str, str]:
    """Headers for Sarvam REST (translate, STT multipart, TTS) per docs."""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Export it or set from dbutils.secrets in the notebook."
        )
    h = {"api-subscription-key": api_key}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def chat_completions(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 512,
    timeout: int = 60,
) -> dict[str, Any]:
    """OpenAI-compatible chat; returns parsed JSON."""
    r = requests.post(
        DEFAULT_CHAT_URL,
        headers=_bearer_headers(),
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


def translate_text(
    text: str,
    *,
    source_language_code: str = "auto",
    target_language_code: str = "en-IN",
    timeout: int = 60,
) -> str:
    """Mayura / Sarvam translate: ``POST /translate`` → translated string."""
    url = os.environ.get("SARVAM_TRANSLATE_URL", DEFAULT_TRANSLATE_URL).strip()
    body: dict[str, Any] = {
        "input": text,
        "source_language_code": source_language_code,
        "target_language_code": target_language_code,
    }
    r = requests.post(
        url,
        headers=_subscription_headers(),
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return _extract_translation_output(data)


def _extract_translation_output(data: dict[str, Any]) -> str:
    for key in ("translated_text", "output", "text"):
        v = data.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    raise ValueError(f"Unexpected translate response shape: {data!r}")


def speech_to_text_file(
    file_bytes: bytes,
    filename: str = "audio.wav",
    *,
    model: str | None = None,
    mode: str = "translate",
    language_code: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """POST ``/speech-to-text`` (multipart). Use ``mode=translate`` for English transcript."""
    url = os.environ.get("SARVAM_STT_URL", DEFAULT_STT_URL).strip()
    model = model or os.environ.get("SARVAM_STT_MODEL", "saaras:v3").strip()
    files = {"file": (filename, file_bytes, "audio/wav")}
    data: dict[str, str] = {"model": model, "mode": mode}
    if language_code:
        data["language_code"] = language_code
    r = requests.post(
        url,
        headers=_subscription_headers(json_body=False),
        files=files,
        data=data,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def transcript_from_stt_response(resp: dict[str, Any]) -> str:
    t = resp.get("transcript")
    if t is None:
        raise ValueError(f"Unexpected STT response shape: {resp!r}")
    return str(t).strip()


def text_to_speech_wav_bytes(
    text: str,
    *,
    target_language_code: str = "en-IN",
    speaker: str | None = None,
    model: str | None = None,
    timeout: int = 120,
) -> bytes:
    """POST ``/text-to-speech``; returns raw WAV bytes (first utterance)."""
    url = os.environ.get("SARVAM_TTS_URL", DEFAULT_TTS_URL).strip()
    model = model or os.environ.get("SARVAM_TTS_MODEL", "bulbul:v3").strip()
    body: dict[str, Any] = {
        "text": text[:2500],
        "target_language_code": target_language_code,
        "model": model,
    }
    if speaker:
        body["speaker"] = speaker
    r = requests.post(
        url,
        headers=_subscription_headers(),
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    audios = data.get("audios")
    if not audios:
        raise ValueError(f"Unexpected TTS response shape: {data!r}")
    return base64.b64decode(audios[0])


def wav_bytes_to_numpy_float32(wav_bytes: bytes) -> tuple[int, np.ndarray]:
    """Decode WAV bytes to ``(sample_rate, mono float32 -1..1)`` for Gradio Audio."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        sw = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    if sw == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        x = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sw}")
    if n_channels > 1:
        x = x.reshape(-1, n_channels).mean(axis=1)
    return sr, x


def numpy_audio_to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Float32 numpy (Gradio mic) → mono 16-bit WAV bytes for Sarvam STT."""
    if samples is None or len(samples) == 0:
        raise ValueError("Empty audio")
    s = np.asarray(samples, dtype=np.float32)
    if s.ndim == 2:
        s = s.mean(axis=1)
    s = np.clip(s, -1.0, 1.0)
    pcm = (s * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def strip_markdown_for_tts(text: str, *, max_chars: int = 2400) -> str:
    """Rough plain text for TTS."""
    t = re.sub(r"```[\s\S]*?```", " ", text)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[*_#>|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_chars]
