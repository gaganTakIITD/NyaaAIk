"""Databricks Vector Search retriever backend.

Uses managed embeddings (Databricks computes embeddings from the ``text`` column)
and supports hybrid search + metadata filters for IPC/BNS section lookups.
"""

from __future__ import annotations

import logging

import pandas as pd

from nyaya_dhwani.keyword_boost import detect_section_references

logger = logging.getLogger(__name__)

_RESULT_COLUMNS = ["chunk_id", "text", "title", "source", "doc_type"]


class VectorSearchRetriever:
    """Query a Databricks Vector Search index via the SDK."""

    def __init__(self, endpoint_name: str, index_name: str) -> None:
        self._endpoint_name = endpoint_name
        self._index_name = index_name
        self._index = None

    def _get_index(self):
        if self._index is not None:
            return self._index
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        self._index = w.vector_search_indexes.get_index(self._index_name)
        logger.info("VectorSearchRetriever: connected to index %s on endpoint %s",
                     self._index_name, self._endpoint_name)
        return self._index

    def search(self, query: str, k: int = 7) -> pd.DataFrame:
        """Similarity search with optional metadata filters for section references."""
        index = self._get_index()

        # Detect IPC/BNS section references for targeted filtering.
        refs = detect_section_references(query)
        filters = None
        num_results = k
        if refs:
            # Request extra results so we can mix mapping chunks with section chunks.
            num_results = k + 3
            # Filter to boost mapping chunks when specific sections are mentioned.
            filters = {"doc_type": "law_mapping"}

        try:
            # First: if we have section references, do a filtered search for mappings.
            mapping_rows = []
            if filters:
                try:
                    mapping_resp = index.similarity_search(
                        columns=_RESULT_COLUMNS,
                        query_text=query,
                        num_results=3,
                        filters=filters,
                    )
                    mapping_rows = _response_to_rows(mapping_resp)
                except Exception:
                    logger.debug("Filtered VS search failed, continuing with unfiltered", exc_info=True)

            # Main unfiltered search.
            resp = index.similarity_search(
                columns=_RESULT_COLUMNS,
                query_text=query,
                num_results=k,
            )
            main_rows = _response_to_rows(resp)

            # Merge: mapping results first, then main results (deduplicated).
            seen_ids = set()
            combined = []
            for row in mapping_rows + main_rows:
                cid = row.get("chunk_id")
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                combined.append(row)

            combined = combined[:k]
            for i, row in enumerate(combined):
                row["rank"] = i

            if not combined:
                return pd.DataFrame(columns=_RESULT_COLUMNS + ["score", "rank"])
            return pd.DataFrame(combined)

        except Exception as e:
            logger.warning("VectorSearchRetriever.search failed: %s", e)
            return pd.DataFrame(columns=_RESULT_COLUMNS + ["score", "rank"])


def _response_to_rows(resp) -> list[dict]:
    """Convert a VS similarity_search response to a list of dicts."""
    rows = []
    # The response format depends on the SDK version.
    # Typically: {"manifest": {"columns": [...]}, "result": {"data_array": [[...], ...]}}
    try:
        manifest = resp.get("manifest", {}) if isinstance(resp, dict) else getattr(resp, "manifest", {})
        result = resp.get("result", {}) if isinstance(resp, dict) else getattr(resp, "result", {})

        if isinstance(manifest, dict):
            col_names = [c.get("name", f"col_{i}") for i, c in enumerate(manifest.get("columns", []))]
        else:
            col_names = [c.name for c in (manifest.columns or [])]

        data_array = result.get("data_array", []) if isinstance(result, dict) else (result.data_array or [])

        for row_data in data_array:
            row = dict(zip(col_names, row_data))
            # VS returns a score column (typically named "score" or the last column).
            if "score" not in row:
                row["score"] = row.pop(col_names[-1], 0.0) if len(col_names) > len(_RESULT_COLUMNS) else 0.0
            rows.append(row)
    except Exception:
        logger.warning("Failed to parse VS response", exc_info=True)
    return rows
