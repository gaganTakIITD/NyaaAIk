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


def _parquet_safe_str(x: object) -> str:
    """Coerce cell values to str for Parquet; drops Spark driver junk (e.g. PlanMetrics)."""
    if x is None:
        return ""
    if isinstance(x, (str, int, bool, np.integer, np.bool_)):
        return str(x)
    if isinstance(x, (float, np.floating)):
        return "" if np.isnan(float(x)) else str(float(x))
    # Any other type (including Databricks PlanMetrics): stringify
    return str(x)


def _sanitize_chunks_df(df: pd.DataFrame) -> pd.DataFrame:
    """Strip Spark/Databricks driver types so pyarrow Parquet write does not fail."""
    out = df.reset_index(drop=True).copy()
    for col in out.columns:
        out[col] = [_parquet_safe_str(v) for v in out[col].tolist()]
    return out


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
    d_int = int(d)
    n_int = int(n)
    if len(chunks_df) != n_int:
        raise ValueError(f"chunks_df rows ({len(chunks_df)}) != embeddings rows ({n_int})")

    chunks_df = _sanitize_chunks_df(chunks_df)

    index = build_flat_ip_index(embeddings)
    faiss_path = output_dir / "corpus.faiss"
    faiss.write_index(index, str(faiss_path))

    parquet_path = output_dir / "chunks.parquet"
    chunks_df.insert(0, "faiss_id", range(n_int))
    chunks_df.to_parquet(parquet_path, index=False)

    manifest = RAGManifest(
        embedding_model=str(embedding_model),
        embedding_dim=d_int,
        faiss_index_file=faiss_path.name,
        chunks_parquet_file=parquet_path.name,
        num_vectors=n_int,
        catalog=str(catalog),
        schema=str(schema),
        source_table=str(source_table),
        created_at_utc=utc_now_iso(),
        normalize_embeddings=normalize_embeddings,
        metric="inner_product",
    )
    mp = output_dir / "manifest.json"
    mp.write_text(manifest.to_json(), encoding="utf-8")
    return manifest
