"""RAG index manifest written next to FAISS index and chunk metadata."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RAGManifest:
    """Metadata for loading the same index at query time."""

    embedding_model: str
    embedding_dim: int
    faiss_index_file: str
    chunks_parquet_file: str
    num_vectors: int
    catalog: str
    schema: str
    source_table: str
    created_at_utc: str
    normalize_embeddings: bool = True
    metric: str = "inner_product"  # cosine after L2 normalize

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RAGManifest:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def load(cls, path: str | Path) -> RAGManifest:
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
