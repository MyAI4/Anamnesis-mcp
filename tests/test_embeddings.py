"""Tests for the embedding pipeline — cosine similarity and recall logic."""

import numpy as np

from anamnesis_mcp.embeddings import EmbeddingPipeline


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert EmbeddingPipeline.cosine_similarity(v, v) > 0.999

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(EmbeddingPipeline.cosine_similarity(a, b)) < 0.001

    def test_opposite_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [-1.0, -2.0, -3.0]
        assert EmbeddingPipeline.cosine_similarity(a, b) < -0.999

    def test_zero_vector(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert EmbeddingPipeline.cosine_similarity(a, b) == 0.0

    def test_numpy_arrays(self):
        a = np.array([1.0, 0.5, 0.0], dtype=np.float32)
        b = np.array([0.5, 1.0, 0.0], dtype=np.float32)
        sim = EmbeddingPipeline.cosine_similarity(a, b)
        assert 0.0 < sim < 1.0


class TestRecall:
    def _make_candidates(self, n: int, dim: int = 16) -> list[tuple[str, np.ndarray]]:
        return [
            (f"id-{i}", np.random.rand(dim).astype(np.float32))
            for i in range(n)
        ]

    def test_empty_candidates(self):
        query = [1.0] * 16
        results = EmbeddingPipeline.recall(query, [], top_k=5)
        assert results == []

    def test_returns_top_k(self):
        dim = 16
        # Create a query and candidates where one is very similar
        query = np.ones(dim, dtype=np.float32)
        candidates = self._make_candidates(20, dim)
        # Make one candidate identical to query
        candidates[7] = ("best-match", query.copy())

        results = EmbeddingPipeline.recall(query, candidates, top_k=3, threshold=0.0)
        assert len(results) <= 3
        assert results[0][0] == "best-match"
        assert results[0][1] > 0.999

    def test_threshold_filters(self):
        dim = 16
        query = np.ones(dim, dtype=np.float32)
        # Create candidates that are very different from query
        candidates = [
            ("low-sim", -1 * np.ones(dim, dtype=np.float32)),
        ]
        results = EmbeddingPipeline.recall(query, candidates, threshold=0.5)
        assert len(results) == 0

    def test_sorted_by_score(self):
        dim = 16
        query = np.ones(dim, dtype=np.float32)
        candidates = [
            ("low", np.array([0.1] * dim, dtype=np.float32)),
            ("high", query.copy()),
            ("mid", np.array([0.5] * dim + [0.1] * (dim - dim), dtype=np.float32)),
        ]
        results = EmbeddingPipeline.recall(query, candidates, top_k=10, threshold=0.0)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_zero_query_vector(self):
        candidates = self._make_candidates(5)
        results = EmbeddingPipeline.recall([0.0] * 16, candidates)
        assert results == []
