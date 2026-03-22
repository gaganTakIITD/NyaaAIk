"""Tests for the retriever abstraction and fallback logic."""

import os
from unittest.mock import MagicMock

import pandas as pd
import pytest

from nyaya_dhwani.retriever import FallbackRetriever


class TestFallbackRetriever:
    def _make_df(self, chunk_ids: list[str]) -> pd.DataFrame:
        return pd.DataFrame([
            {"chunk_id": cid, "text": f"text_{cid}", "score": 0.9, "rank": i,
             "title": "", "source": "", "doc_type": ""}
            for i, cid in enumerate(chunk_ids)
        ])

    def test_uses_primary_when_successful(self):
        primary = MagicMock()
        primary.search.return_value = self._make_df(["A", "B"])
        fallback = MagicMock()

        ret = FallbackRetriever(primary, fallback)
        result = ret.search("test query", k=5)

        assert list(result["chunk_id"]) == ["A", "B"]
        fallback.search.assert_not_called()

    def test_falls_back_on_exception(self):
        primary = MagicMock()
        primary.search.side_effect = RuntimeError("VS unavailable")
        fallback = MagicMock()
        fallback.search.return_value = self._make_df(["C", "D"])

        ret = FallbackRetriever(primary, fallback)
        result = ret.search("test query", k=5)

        assert list(result["chunk_id"]) == ["C", "D"]

    def test_falls_back_on_empty_result(self):
        primary = MagicMock()
        primary.search.return_value = pd.DataFrame()
        fallback = MagicMock()
        fallback.search.return_value = self._make_df(["E"])

        ret = FallbackRetriever(primary, fallback)
        result = ret.search("test query", k=5)

        assert list(result["chunk_id"]) == ["E"]
