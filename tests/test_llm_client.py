"""Helpers for llm_client (no network)."""

import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from nyaya_dhwani.llm_client import (
    _chat_url,
    complete_with_openai_sdk,
    extract_assistant_text,
    rag_user_message,
)


def test_extract_assistant_text():
    out = extract_assistant_text(
        {"choices": [{"message": {"content": "  hello  "}}]}
    )
    assert out == "hello"


def test_rag_user_message():
    msg = rag_user_message(["a", "b"], "q?")
    assert "a" in msg and "b" in msg and "q?" in msg


def test_chat_url_ai_gateway_mlflow_v1():
    with patch.dict(
        os.environ,
        {
            "LLM_CHAT_COMPLETIONS_URL": "",
            "LLM_OPENAI_BASE_URL": "https://123.ai-gateway.cloud.databricks.com/mlflow/v1",
        },
        clear=False,
    ):
        assert _chat_url() == (
            "https://123.ai-gateway.cloud.databricks.com/mlflow/v1/chat/completions"
        )


def test_chat_url_openai_style_base():
    with patch.dict(
        os.environ,
        {
            "LLM_CHAT_COMPLETIONS_URL": "",
            "LLM_OPENAI_BASE_URL": "https://api.openai.com/v1",
        },
        clear=False,
    ):
        assert _chat_url() == "https://api.openai.com/v1/chat/completions"


def test_chat_url_full_override():
    with patch.dict(
        os.environ,
        {
            "LLM_CHAT_COMPLETIONS_URL": "https://host/custom/chat/completions",
            "LLM_OPENAI_BASE_URL": "ignored",
        },
        clear=False,
    ):
        assert _chat_url() == "https://host/custom/chat/completions"


def test_complete_with_openai_sdk_fake_module():
    """No real ``openai`` package required — inject a minimal fake into ``sys.modules``."""
    saved = sys.modules.pop("openai", None)
    calls: dict = {}

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url):
            calls["init"] = (api_key, base_url)

        class chat:
            class completions:
                @staticmethod
                def create(*, model, messages, temperature, max_tokens):
                    calls["create"] = (model, messages, temperature, max_tokens)
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(message=SimpleNamespace(content="  answer  "))
                        ]
                    )

    fake = ModuleType("openai")
    fake.OpenAI = FakeOpenAI
    sys.modules["openai"] = fake
    try:
        with patch.dict(
            os.environ,
            {
                "LLM_OPENAI_BASE_URL": "https://w.ai-gateway.cloud.databricks.com/mlflow/v1",
                "DATABRICKS_TOKEN": "dapi-test",
                "LLM_MODEL": "databricks-llama-4-maverick",
            },
            clear=False,
        ):
            out = complete_with_openai_sdk(
                [{"role": "user", "content": "hi"}],
                max_tokens=100,
            )
        assert out == "answer"
        assert calls["init"] == (
            "dapi-test",
            "https://w.ai-gateway.cloud.databricks.com/mlflow/v1",
        )
        assert calls["create"][0] == "databricks-llama-4-maverick"
        assert calls["create"][3] == 100
    finally:
        del sys.modules["openai"]
        if saved is not None:
            sys.modules["openai"] = saved
