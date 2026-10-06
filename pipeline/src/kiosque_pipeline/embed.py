"""embed.py — Headline embeddings. The real model is imported lazily (heavy dependency)."""

from typing import Protocol

import numpy as np

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return one L2-normalized row per text."""


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = MODEL_NAME, device: str | None = None):
        from sentence_transformers import SentenceTransformer

        # device=None lets the library pick (CUDA/MPS/CPU); pass "cpu" inside forked
        # workers on macOS, where the Metal backend cannot initialise after fork.
        self._model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
