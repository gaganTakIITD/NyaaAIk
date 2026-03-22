"""Unit tests for Sarvam helpers (no network)."""

from __future__ import annotations

import numpy as np
import pytest

from nyaya_dhwani.sarvam_client import (
    _extract_translation_output,
    numpy_audio_to_wav_bytes,
    wav_bytes_to_numpy_float32,
)


def test_extract_translation_output() -> None:
    assert _extract_translation_output({"translated_text": " hello "}) == "hello"
    assert _extract_translation_output({"output": "x"}) == "x"
    assert _extract_translation_output({"text": "y"}) == "y"


def test_extract_translation_output_missing() -> None:
    with pytest.raises(ValueError):
        _extract_translation_output({})


def test_wav_roundtrip_mono() -> None:
    x = np.array([0.0, 0.25, -0.25, 0.1], dtype=np.float32)
    raw = numpy_audio_to_wav_bytes(x, 16_000)
    sr, y = wav_bytes_to_numpy_float32(raw)
    assert sr == 16_000
    assert y.shape == (4,)
    assert np.max(np.abs(y)) <= 1.0
