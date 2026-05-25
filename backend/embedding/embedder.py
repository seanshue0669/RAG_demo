"""Sentence-Transformers embedding wrapper for the Cloud RAG Security Demo.

This module exposes a thin wrapper around `sentence-transformers` so that
the rest of the backend (data seeding, RAG retriever, homomorphic-encryption
search) can obtain a consistent embedding interface without depending on the
upstream library directly.

The model is loaded lazily on the first `encode` / `encode_batch` call to
avoid paying the download/initialisation cost at import time. A
module-level singleton accessor `get_embedder()` is provided so callers
share one model instance per process.

Typical usage:

    from backend.embedding.embedder import get_embedder

    embedder = get_embedder()
    vector = embedder.encode("一些查詢文字")
    vectors = embedder.encode_batch(["doc 1", "doc 2"], batch_size=32)
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from backend.config.settings import get_settings

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from sentence_transformers import SentenceTransformer


class Embedder:
    """Wraps `sentence-transformers/gtr-t5-base` for the RAG demo.

    The underlying `SentenceTransformer` model is loaded lazily on the first
    call to `encode` or `encode_batch`. This keeps import side-effects light
    and lets unit tests construct the object without triggering a model
    download.

    Attributes:
        model_name: HuggingFace identifier of the sentence-transformers model.
        device: The torch device string the model is pinned to.
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
    ) -> None:
        """Initialise the embedder configuration.

        Args:
            model_name: Optional override of the model identifier. Defaults
                to `settings.EMBEDDING_MODEL_NAME`.
            device: Optional override of the torch device (e.g. "cuda" or
                "cpu"). When `None`, the device is auto-detected — CUDA is
                preferred when available, otherwise CPU.
        """
        settings = get_settings()
        self.model_name: str = model_name or settings.EMBEDDING_MODEL_NAME
        self.device: str = device or self._auto_detect_device()
        self._model: SentenceTransformer | None = None
        # `_dim` is populated lazily from the loaded model. We fall back to
        # the configured `EMBEDDING_DIM` if the model has not been loaded
        # yet, to keep the `dim` property cheap.
        self._configured_dim: int = settings.EMBEDDING_DIM

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _auto_detect_device() -> str:
        """Return "cuda" if a CUDA device is available, otherwise "cpu".

        Returns:
            The torch device string.
        """
        try:
            import torch  # type: ignore[import-not-found]
        except ImportError:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _ensure_loaded(self) -> SentenceTransformer:
        """Load the SentenceTransformer model on first access.

        Returns:
            The loaded `SentenceTransformer` instance.
        """
        if self._model is None:
            # Import here to keep module import cost low and avoid forcing
            # `sentence_transformers` as a hard dep at import time.
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
            )
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def encode(self, text: str) -> list[float]:
        """Encode a single text into an embedding vector.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats representing the embedding. ChromaDB expects
            plain Python lists (not numpy arrays), so the numpy output is
            converted before returning.
        """
        model = self._ensure_loaded()
        vector = model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=False,
        )
        return [float(x) for x in vector.tolist()]

    def encode_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Encode a batch of texts into embedding vectors.

        Args:
            texts: The list of input texts to embed.
            batch_size: Number of texts to push through the model per step.

        Returns:
            A list of embedding vectors, in the same order as `texts`.
            Each vector is a plain Python `list[float]` for ChromaDB
            compatibility. An empty input yields an empty output.
        """
        if not texts:
            return []
        model = self._ensure_loaded()
        matrix = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=False,
        )
        # `matrix` is a 2-D numpy array of shape (N, dim).
        return [[float(x) for x in row] for row in matrix.tolist()]

    @property
    def dim(self) -> int:
        """Return the dimensionality of the embeddings.

        If the model is already loaded, the value is read from the model
        (most authoritative). Otherwise the configured `EMBEDDING_DIM` from
        settings is returned, which avoids triggering a model load just to
        ask for the dimensionality.

        Returns:
            The embedding dimensionality as an int.
        """
        if self._model is not None:
            try:
                return int(self._model.get_sentence_embedding_dimension())
            except Exception:  # pragma: no cover - defensive fallback
                pass
        return self._configured_dim


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Return a process-wide singleton `Embedder` instance.

    The instance is constructed with default settings (model name from
    `settings.EMBEDDING_MODEL_NAME`, device auto-detected). Subsequent
    calls return the same object, so the underlying model is loaded at
    most once per process.

    Returns:
        The shared `Embedder` instance.
    """
    return Embedder()


__all__: list[str] = ["Embedder", "get_embedder"]
