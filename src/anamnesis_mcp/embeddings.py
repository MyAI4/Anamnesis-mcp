"""Embedding pipeline — local sentence-transformers by default, optional OpenAI."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

import numpy as np

# Thread pool for running blocking embedding operations without stalling the event loop
_executor = ThreadPoolExecutor(max_workers=1)

# Default local model — small, fast, good quality
DEFAULT_LOCAL_MODEL = "all-MiniLM-L6-v2"  # 384-dim, ~80MB


class EmbeddingBackend(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...


class LocalEmbedding(EmbeddingBackend):
    """Local embeddings via sentence-transformers. No API key needed."""

    def __init__(self, model_name: str = DEFAULT_LOCAL_MODEL):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        vec = self._model.encode(text, convert_to_numpy=True)
        return vec.astype(np.float32).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vecs = self._model.encode(texts, convert_to_numpy=True)
        return [v.astype(np.float32).tolist() for v in vecs]

    @property
    def dimension(self) -> int:
        return self._dimension


class OpenAIEmbedding(EmbeddingBackend):
    """Remote embeddings via OpenAI API. Requires OPENAI_API_KEY."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package required for OpenAI embeddings. "
                "Install with: pip install anamnesis-mcp[openai]"
            )
        self._model = model
        self._client = OpenAI(api_key=api_key)
        # text-embedding-3-small = 1536, text-embedding-3-large = 3072
        self._dimension = 1536 if "small" in model else 3072

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=self._model, input=text)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension


class EmbeddingPipeline:
    """High-level embedding + recall interface."""

    def __init__(self, backend: EmbeddingBackend | None = None):
        self._backend = backend or LocalEmbedding()

    def embed(self, text: str) -> list[float]:
        return self._backend.embed(text)

    async def embed_async(self, text: str) -> list[float]:
        """Non-blocking embed — runs in a thread to avoid stalling the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._backend.embed, text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._backend.embed_batch(texts)

    @property
    def dimension(self) -> int:
        return self._backend.dimension

    @staticmethod
    def cosine_similarity(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        a_arr = np.asarray(a, dtype=np.float32)
        b_arr = np.asarray(b, dtype=np.float32)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))

    @staticmethod
    def recall(
        query_vector: list[float] | np.ndarray,
        candidates: list[tuple[str, np.ndarray]],
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[tuple[str, float]]:
        """
        Brute-force cosine similarity search against candidate vectors.

        Returns list of (record_id, score) sorted by score descending.
        """
        if not candidates:
            return []

        query = np.asarray(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []

        ids = [c[0] for c in candidates]
        matrix = np.stack([c[1] for c in candidates])

        dots = matrix @ query
        norms = np.linalg.norm(matrix, axis=1)
        norms = np.where(norms == 0, 1.0, norms)
        scores = dots / (norms * query_norm)

        results = [
            (ids[i], float(scores[i]))
            for i in range(len(ids))
            if scores[i] >= threshold
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


def create_backend(
    backend: str = "local",
    model: str | None = None,
    api_key: str | None = None,
) -> EmbeddingBackend:
    """Factory to create the right embedding backend from config."""
    if backend == "openai":
        return OpenAIEmbedding(
            model=model or "text-embedding-3-small",
            api_key=api_key,
        )
    return LocalEmbedding(model_name=model or DEFAULT_LOCAL_MODEL)
