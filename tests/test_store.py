"""Tests for the SQLite memory store."""

import numpy as np

from anamnesis_mcp.models import MemoryRecord, SourceRecord
from anamnesis_mcp.store import MemoryStore


def make_memory(**kwargs) -> MemoryRecord:
    defaults = {
        "summary": "Test memory",
        "context_tags": ["python", "testing"],
        "project": "test-project",
        "cue_vector": list(np.random.rand(16).astype(np.float32)),
    }
    defaults.update(kwargs)
    return MemoryRecord(**defaults)


def make_source(**kwargs) -> SourceRecord:
    defaults = {
        "file_path": "/home/user/.claude/projects/test/session.jsonl",
        "file_type": "conversation",
        "project": "test-project",
        "chunk_start": 1,
        "chunk_end": 200,
    }
    defaults.update(kwargs)
    return SourceRecord(**defaults)


class TestMemoryStore:
    def setup_method(self):
        self.store = MemoryStore(":memory:")

    def teardown_method(self):
        self.store.close()

    # --- Memory tests ---

    def test_insert_and_get_memory(self):
        record = make_memory()
        rid = self.store.insert_memory(record)
        fetched = self.store.get_memory(rid)
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.summary == "Test memory"
        assert fetched.context_tags == ["python", "testing"]
        assert fetched.project == "test-project"

    def test_get_nonexistent_memory(self):
        assert self.store.get_memory("nonexistent-id") is None

    def test_search_keyword(self):
        r1 = make_memory(summary="Solved Lambda cold-start issue")
        r2 = make_memory(summary="Fixed React rendering bug")
        self.store.insert_memory(r1)
        self.store.insert_memory(r2)
        results = self.store.search_keyword("Lambda")
        assert len(results) == 1
        assert results[0].summary == "Solved Lambda cold-start issue"

    def test_search_by_tag(self):
        r1 = make_memory(summary="A", context_tags=["aws", "lambda"])
        r2 = make_memory(summary="B", context_tags=["react"])
        self.store.insert_memory(r1)
        self.store.insert_memory(r2)
        results = self.store.search_keyword(tags=["aws"])
        assert len(results) == 1
        assert results[0].summary == "A"

    def test_search_by_project(self):
        r1 = make_memory(summary="A", project="proj-a")
        r2 = make_memory(summary="B", project="proj-b")
        self.store.insert_memory(r1)
        self.store.insert_memory(r2)
        results = self.store.search_keyword(project="proj-a")
        assert len(results) == 1
        assert results[0].summary == "A"

    def test_vector_roundtrip(self):
        original_vec = list(np.random.rand(384).astype(np.float32))
        record = make_memory(cue_vector=original_vec)
        self.store.insert_memory(record)
        fetched = self.store.get_memory(record.id)
        assert fetched is not None
        np.testing.assert_array_almost_equal(fetched.cue_vector, original_vec, decimal=6)

    def test_get_all_vectors(self):
        r1 = make_memory()
        r2 = make_memory()
        self.store.insert_memory(r1)
        self.store.insert_memory(r2)
        vectors = self.store.get_all_vectors()
        assert len(vectors) == 2
        for rid, vec in vectors:
            assert isinstance(vec, np.ndarray)
            assert vec.dtype == np.float32

    def test_get_stats(self):
        r1 = make_memory(project="proj-a", outcome="solved", context_tags=["python"])
        r2 = make_memory(project="proj-a", outcome="eureka", context_tags=["python", "aws"])
        r3 = make_memory(project="proj-b", outcome="solved", context_tags=["go"])
        self.store.insert_memory(r1)
        self.store.insert_memory(r2)
        self.store.insert_memory(r3)
        stats = self.store.get_stats()
        assert stats["total_memories"] == 3
        assert stats["by_project"]["proj-a"] == 2
        assert stats["top_tags"]["python"] == 2

    # --- Source tests ---

    def test_insert_and_get_source(self):
        source = make_source()
        self.store.insert_source(source)
        unprocessed = self.store.get_unprocessed_sources()
        assert len(unprocessed) == 1
        assert unprocessed[0].file_path == source.file_path
        assert unprocessed[0].chunk_start == 1
        assert unprocessed[0].chunk_end == 200

    def test_mark_source_processed(self):
        source = make_source()
        self.store.insert_source(source)
        assert self.store.mark_source_processed(source.id) is True
        unprocessed = self.store.get_unprocessed_sources()
        assert len(unprocessed) == 0

    def test_mark_nonexistent_source(self):
        assert self.store.mark_source_processed("nonexistent") is False

    def test_has_source_file(self):
        source = make_source()
        self.store.insert_source(source)
        assert self.store.has_source_file(source.file_path) is True
        assert self.store.has_source_file("/other/path.jsonl") is False

    def test_delete_sources_for_file(self):
        s1 = make_source(chunk_start=1, chunk_end=100)
        s2 = make_source(chunk_start=101, chunk_end=200)
        s3 = make_source(file_path="/other/file.jsonl", chunk_start=1, chunk_end=50)
        self.store.insert_source(s1)
        self.store.insert_source(s2)
        self.store.insert_source(s3)
        deleted = self.store.delete_sources_for_file(s1.file_path)
        assert deleted == 2
        unprocessed = self.store.get_unprocessed_sources()
        assert len(unprocessed) == 1
        assert unprocessed[0].file_path == "/other/file.jsonl"

    def test_stats_includes_unprocessed_sources(self):
        s1 = make_source()
        s2 = make_source(file_path="/other.jsonl")
        self.store.insert_source(s1)
        self.store.insert_source(s2)
        self.store.mark_source_processed(s1.id)
        stats = self.store.get_stats()
        assert stats["unprocessed_sources"] == 1
