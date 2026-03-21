"""FAISS roundtrip — requires [rag] extras."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("faiss")

from nyaya_dhwani.index_builder import save_rag_artifacts
from nyaya_dhwani.retrieval import CorpusIndex


def test_save_and_load_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    n, d = 20, 32
    emb = rng.standard_normal((n, d)).astype(np.float32)
    # unit-normalize like a real embedding matrix
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = emb / np.clip(norms, 1e-12, None)

    df = pd.DataFrame(
        {
            "chunk_id": [f"c{i}" for i in range(n)],
            "text": [f"text {i}" for i in range(n)],
            "source": ["test"] * n,
        }
    )
    save_rag_artifacts(
        tmp_path,
        embeddings=emb,
        chunks_df=df,
        embedding_model="test-model",
        catalog="main",
        schema="india_legal",
        source_table="legal_rag_corpus",
    )
    idx = CorpusIndex.load(tmp_path)
    assert idx.manifest.num_vectors == n
    q = emb[0:1].copy()
    out = idx.search(q, k=3)
    assert len(out) <= 3
    assert "score" in out.columns
    assert out.iloc[0]["chunk_id"] == "c0"


def test_save_rag_artifacts_sanitizes_non_primitive_cells(tmp_path):
    """Spark toPandas() can leak driver objects (e.g. PlanMetrics); Parquet must still write."""
    rng = np.random.default_rng(1)
    n, d = 1, 16
    emb = rng.standard_normal((n, d)).astype(np.float32)
    emb = emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-12, None)

    class _Foreign:
        def __str__(self) -> str:
            return "ok"

    df = pd.DataFrame(
        {
            "chunk_id": ["c0"],
            "text": [_Foreign()],
            "source": ["test"],
        }
    )
    save_rag_artifacts(
        tmp_path,
        embeddings=emb,
        chunks_df=df,
        embedding_model="test-model",
        catalog="main",
        schema="india_legal",
        source_table="legal_rag_corpus",
    )
    reread = pd.read_parquet(tmp_path / "chunks.parquet")
    assert reread.iloc[0]["text"] == "ok"
