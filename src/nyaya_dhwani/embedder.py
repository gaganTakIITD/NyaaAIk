"""Sentence embeddings for RAG (same model at index build and query time)."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceEmbedder:
    """Thin wrapper around sentence-transformers with fixed model id."""

    def __init__(self, model_name: str = DEFAULT_MODEL, normalize: bool = True) -> None:
        self.model_name = model_name
        self.normalize = normalize
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "Install RAG extras: pip install 'nyaya-dhwani[rag]'"
                ) from e
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def embedding_dim(self) -> int:
        m = self._load_model()
        return int(m.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> "NDArray[np.float32]":
        """Return float32 array of shape (n, dim)."""
        m = self._load_model()
        emb = m.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=len(texts) > 32,
        )
        return np.asarray(emb, dtype=np.float32)


@lru_cache(maxsize=8)
def get_embedder(model_name: str = DEFAULT_MODEL, normalize: bool = True) -> SentenceEmbedder:
    return SentenceEmbedder(model_name=model_name, normalize=normalize)
