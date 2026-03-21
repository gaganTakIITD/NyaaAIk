"""Build FAISS index + chunk Parquet + manifest from embedded corpus rows."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from nyaya_dhwani.manifest import RAGManifest, utc_now_iso

if TYPE_CHECKING:
    from numpy.typing import NDArray

try:
    import faiss  # type: ignore[import-untyped]
except ImportError:
    faiss = None  # type: ignore[assignment]


def _require_faiss() -> None:
    if faiss is None:
        raise ImportError("Install RAG extras: pip install 'nyaya-dhwani[rag]'")


def build_flat_ip_index(embeddings: "NDArray[np.float32]") -> "faiss.Index":
    """Inner-product index; use with L2-normalized vectors for cosine similarity."""
    _require_faiss()
    n, d = embeddings.shape
    index = faiss.IndexFlatIP(d)
    vectors = np.ascontiguousarray(embeddings, dtype=np.float32)
    faiss.normalize_L2(vectors)
    index.add(vectors)
    return index


def save_rag_artifacts(
    output_dir: str | Path,
    embeddings: "NDArray[np.float32]",
    chunks_df: pd.DataFrame,
    embedding_model: str,
    catalog: str,
    schema: str,
    source_table: str,
    normalize_embeddings: bool = True,
) -> RAGManifest:
    """
    Write `corpus.faiss`, `chunks.parquet`, `manifest.json` under output_dir.

    chunks_df must have rows in the same order as embedding rows (0..n-1 == FAISS ids).
    Expected columns at minimum: chunk_id, text (title/source optional).
    """
    _require_faiss()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    n, d = embeddings.shape
    if len(chunks_df) != n:
        raise ValueError(f"chunks_df rows ({len(chunks_df)}) != embeddings rows ({n})")

    index = build_flat_ip_index(embeddings)
    faiss_path = output_dir / "corpus.faiss"
    faiss.write_index(index, str(faiss_path))

    parquet_path = output_dir / "chunks.parquet"
    chunks_df = chunks_df.reset_index(drop=True)
    chunks_df.insert(0, "faiss_id", range(n))
    chunks_df.to_parquet(parquet_path, index=False)

    manifest = RAGManifest(
        embedding_model=embedding_model,
        embedding_dim=d,
        faiss_index_file=faiss_path.name,
        chunks_parquet_file=parquet_path.name,
        num_vectors=n,
        catalog=catalog,
        schema=schema,
        source_table=source_table,
        created_at_utc=utc_now_iso(),
        normalize_embeddings=normalize_embeddings,
        metric="inner_product",
    )
    mp = output_dir / "manifest.json"
    mp.write_text(manifest.to_json(), encoding="utf-8")
    return manifest
