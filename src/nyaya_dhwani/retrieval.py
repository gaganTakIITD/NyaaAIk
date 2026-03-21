"""Load FAISS + chunk table and run top-k similarity search."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from nyaya_dhwani.faiss_compat import get_faiss
from nyaya_dhwani.manifest import RAGManifest

if TYPE_CHECKING:
    from numpy.typing import NDArray


class CorpusIndex:
    """In-memory FAISS + metadata for retrieval."""

    def __init__(self, manifest: RAGManifest, index, chunks: pd.DataFrame) -> None:
        self.manifest = manifest
        self.index = index
        self.chunks = chunks

    @classmethod
    def load(cls, index_dir: str | Path) -> CorpusIndex:
        faiss = get_faiss()
        index_dir = Path(index_dir)
        manifest = RAGManifest.load(index_dir / "manifest.json")
        idx = faiss.read_index(str(index_dir / manifest.faiss_index_file))
        chunks = pd.read_parquet(index_dir / manifest.chunks_parquet_file)
        return cls(manifest, idx, chunks)

    def search(
        self,
        query_embedding: "NDArray[np.float32]",
        k: int = 5,
    ) -> pd.DataFrame:
        """Return top-k rows with scores; query_embedding shape (1, dim) or (dim,)."""
        q = np.asarray(query_embedding, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        get_faiss().normalize_L2(q)
        scores, ids = self.index.search(q, min(k, self.manifest.num_vectors))
        rows = []
        for rank, (score, iid) in enumerate(zip(scores[0], ids[0])):
            if iid < 0:
                continue
            rec = self.chunks[self.chunks["faiss_id"] == iid]
            if rec.empty:
                continue
            r = rec.iloc[0].to_dict()
            r["score"] = float(score)
            r["rank"] = rank
            rows.append(r)
        return pd.DataFrame(rows)
