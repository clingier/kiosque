"""embed.py — Headline embeddings. The real model is imported lazily (heavy dependency)."""

import os
import tempfile
from pathlib import Path
from typing import Protocol

import numpy as np

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return one L2-normalized row per text."""


def _ensure_writable_hf_home() -> None:
    """Every Hugging Face cache (hub models, xet chunks, token) lives under HF_HOME, which
    defaults to ~/.cache/huggingface and is read once at import. Databricks serverless workers
    have a home directory that does not exist and cannot be created, so point HF_HOME at the
    temp dir there before huggingface_hub is imported."""
    home = Path.home()
    if "HF_HOME" in os.environ or (home.is_dir() and os.access(home, os.W_OK)):
        return
    os.environ["HF_HOME"] = str(Path(tempfile.gettempdir()) / "hf-home")


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = MODEL_NAME, device: str | None = None):
        _ensure_writable_hf_home()
        from sentence_transformers import SentenceTransformer

        # device=None lets the library pick (CUDA/MPS/CPU); pass "cpu" inside forked
        # workers on macOS, where the Metal backend cannot initialise after fork.
        self._model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
