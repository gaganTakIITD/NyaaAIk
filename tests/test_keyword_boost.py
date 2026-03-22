"""Tests for IPC/BNS section reference detection and keyword boosting."""

import pandas as pd
import pytest

from nyaya_dhwani.keyword_boost import detect_section_references, boost_with_keywords


class TestDetectSectionReferences:
    def test_ipc_section(self):
        assert detect_section_references("Explain IPC Section 413") == [("IPC", "413")]

    def test_bns_section(self):
        assert detect_section_references("What is BNS 303(1)?") == [("BNS", "303(1)")]

    def test_section_of_ipc(self):
        assert detect_section_references("Section 378 of IPC") == [("IPC", "378")]

    def test_multiple_refs(self):
        refs = detect_section_references("Compare IPC Section 413 and BNS 317(4)")
        assert ("IPC", "413") in refs
        assert ("BNS", "317(4)") in refs

    def test_no_refs(self):
        assert detect_section_references("What is theft?") == []

    def test_case_insensitive(self):
        assert detect_section_references("ipc section 302") == [("IPC", "302")]

    def test_bns_section_keyword(self):
        assert detect_section_references("BNS Section 109") == [("BNS", "109")]


class TestBoostWithKeywords:
    @pytest.fixture()
    def all_chunks(self):
        return pd.DataFrame([
            {"chunk_id": "MAP_BNS317", "text": "BNS 317(4) replaces IPC 413 (Habitually dealing in stolen property)", "source": "BNS_IPC_MAPPING", "doc_type": "law_mapping", "title": "BNS 317(4) replaces IPC 413"},
            {"chunk_id": "BNS_S168", "text": "BNS Section 168: Punishment for unlawful assembly...", "source": "BNS_2023", "doc_type": "criminal_law", "title": "BNS Section 168"},
            {"chunk_id": "BNS_S303", "text": "BNS Section 303: Theft...", "source": "BNS_2023", "doc_type": "criminal_law", "title": "BNS Section 303"},
            {"chunk_id": "MAP_BNS303", "text": "BNS 303(1) replaces IPC 378 (Theft)", "source": "BNS_IPC_MAPPING", "doc_type": "law_mapping", "title": "BNS 303(1) replaces IPC 378"},
        ])

    @pytest.fixture()
    def semantic_results(self):
        return pd.DataFrame([
            {"chunk_id": "BNS_S168", "text": "BNS Section 168...", "score": 0.8, "rank": 0, "source": "BNS_2023", "doc_type": "criminal_law", "title": "BNS Section 168"},
            {"chunk_id": "BNS_S303", "text": "BNS Section 303...", "score": 0.7, "rank": 1, "source": "BNS_2023", "doc_type": "criminal_law", "title": "BNS Section 303"},
        ])

    def test_boost_adds_mapping_chunk(self, semantic_results, all_chunks):
        result = boost_with_keywords("IPC Section 413", semantic_results, all_chunks, k=5)
        assert "MAP_BNS317" in result["chunk_id"].tolist()

    def test_boost_deduplicates(self, semantic_results, all_chunks):
        result = boost_with_keywords("IPC Section 378", semantic_results, all_chunks, k=5)
        # MAP_BNS303 should appear, BNS_S303 is already in semantic results
        ids = result["chunk_id"].tolist()
        assert len(ids) == len(set(ids)), "Duplicates found"

    def test_no_boost_for_generic_query(self, semantic_results, all_chunks):
        result = boost_with_keywords("What is theft?", semantic_results, all_chunks, k=5)
        # No section references → same as semantic results
        assert result["chunk_id"].tolist() == semantic_results["chunk_id"].tolist()

    def test_respects_k_limit(self, semantic_results, all_chunks):
        result = boost_with_keywords("IPC Section 413", semantic_results, all_chunks, k=2)
        assert len(result) <= 2

    def test_keyword_hit_ranked_first(self, semantic_results, all_chunks):
        result = boost_with_keywords("IPC Section 413", semantic_results, all_chunks, k=5)
        assert result.iloc[0]["chunk_id"] == "MAP_BNS317"
