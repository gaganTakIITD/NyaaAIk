"""Helpers for llm_client (no network)."""

from nyaya_dhwani.llm_client import extract_assistant_text, rag_user_message


def test_extract_assistant_text():
    out = extract_assistant_text(
        {"choices": [{"message": {"content": "  hello  "}}]}
    )
    assert out == "hello"


def test_rag_user_message():
    msg = rag_user_message(["a", "b"], "q?")
    assert "a" in msg and "b" in msg and "q?" in msg
