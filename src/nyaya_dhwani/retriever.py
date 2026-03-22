"""Unified retriever interface with FAISS and Vector Search backends.

Usage::

    from nyaya_dhwani.retriever import get_retriever

    retriever = get_retriever()           # reads NYAYA_RETRIEVAL_BACKEND env var
    results_df = retriever.search("What is theft under BNS?", k=7)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Retriever(Protocol):
    """Uniform search interface for RAG retrieval backends."""

    def search(self, query: str, k: int = 7) -> pd.DataFrame:
        """Return top-k chunks as a DataFrame.

        Expected columns: text, title, source, doc_type, score, rank.
        """
        ...


# ---------------------------------------------------------------------------
# FAISS backend
# ---------------------------------------------------------------------------

class FaissRetriever:
    """Wraps ``CorpusIndex`` + ``SentenceEmbedder`` behind the ``Retriever`` interface."""

    def __init__(self, index_dir: str | Path) -> None:
        self._index_dir = str(index_dir)
        self._ci = None
        self._embedder = None

    def _load(self) -> None:
        if self._ci is not None:
            return
        from nyaya_dhwani.retrieval import CorpusIndex
        from nyaya_dhwani.embedder import SentenceEmbedder

        logger.info("FaissRetriever: loading index from %s", self._index_dir)
        self._ci = CorpusIndex.load(self._index_dir)
        m = self._ci.manifest
        self._embedder = SentenceEmbedder(
            model_name=m.embedding_model,
            normalize=m.normalize_embeddings,
        )
        logger.info("FaissRetriever: loaded %d vectors, model %s", m.num_vectors, m.embedding_model)

    def search(self, query: str, k: int = 7) -> pd.DataFrame:
        self._load()
        assert self._ci is not None and self._embedder is not None
        emb = self._embedder.encode([query.strip()])
        semantic_df = self._ci.search(emb, k=k)

        # Apply keyword boosting for IPC/BNS section references.
        from nyaya_dhwani.keyword_boost import boost_with_keywords
        return boost_with_keywords(query, semantic_df, self._ci.chunks, k=k)


# ---------------------------------------------------------------------------
# Fallback wrapper
# ---------------------------------------------------------------------------

class FallbackRetriever:
    """Tries *primary*, falls back to *fallback* on failure or empty result."""

    def __init__(self, primary: Retriever, fallback: Retriever) -> None:
        self._primary = primary
        self._fallback = fallback

    def search(self, query: str, k: int = 7) -> pd.DataFrame:
        try:
            result = self._primary.search(query, k)
            if result is not None and not result.empty:
                return result
            logger.warning("Primary retriever returned empty, falling back")
        except Exception:
            logger.warning("Primary retriever failed, falling back", exc_info=True)
        return self._fallback.search(query, k)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_LOCAL_INDEX_CACHE = "/tmp/nyaya_index"


def _download_from_volume(volume_path: str, local_dir: str) -> str:
    """Download index files from a UC Volume via the Databricks SDK."""
    local = Path(local_dir)
    if (local / "manifest.json").exists():
        logger.info("Index already cached at %s", local)
        return str(local)
    logger.info("Downloading index from Volume %s → %s", volume_path, local)
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    local.mkdir(parents=True, exist_ok=True)
    for item in w.files.list_directory_contents(volume_path):
        if item.is_directory:
            continue
        dest = local / item.name
        logger.info("  downloading %s", item.name)
        with w.files.download(item.path).contents as src, open(dest, "wb") as dst:
            while True:
                chunk = src.read(8 * 1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
    logger.info("Index download complete → %s", local)
    return str(local)


def _resolve_index_dir() -> str:
    """Resolve FAISS index directory, downloading from UC Volume if needed."""
    default = "/Volumes/main/india_legal/legal_files/nyaya_index"
    path = os.environ.get("NYAYA_INDEX_DIR", default).strip()
    if path.startswith("/Volumes/") and not Path(path).exists():
        try:
            path = _download_from_volume(path, _LOCAL_INDEX_CACHE)
        except Exception as e:
            logger.warning("Could not download index from Volume: %s", e)
    return path


def get_retriever() -> Retriever:
    """Instantiate the configured retriever backend.

    Reads ``NYAYA_RETRIEVAL_BACKEND`` env var:

    - ``"vector_search"`` → ``VectorSearchRetriever`` with FAISS fallback
    - ``"faiss"`` (default) → ``FaissRetriever``
    """
    backend = os.environ.get("NYAYA_RETRIEVAL_BACKEND", "faiss").strip().lower()

    faiss_dir = _resolve_index_dir()
    faiss_ret = FaissRetriever(faiss_dir)

    if backend == "vector_search":
        endpoint = os.environ.get("NYAYA_VS_ENDPOINT_NAME", "").strip()
        index_name = os.environ.get("NYAYA_VS_INDEX_NAME", "").strip()
        if endpoint and index_name:
            try:
                from nyaya_dhwani.vs_retriever import VectorSearchRetriever
                vs_ret = VectorSearchRetriever(endpoint, index_name)
                logger.info("Using VectorSearchRetriever (endpoint=%s) with FAISS fallback", endpoint)
                return FallbackRetriever(primary=vs_ret, fallback=faiss_ret)
            except Exception:
                logger.warning("Failed to init VectorSearchRetriever, using FAISS", exc_info=True)
        else:
            logger.warning(
                "NYAYA_RETRIEVAL_BACKEND=vector_search but NYAYA_VS_ENDPOINT_NAME / "
                "NYAYA_VS_INDEX_NAME not set — falling back to FAISS"
            )

    logger.info("Using FaissRetriever (index_dir=%s)", faiss_dir)
    return faiss_ret
