"""Tests for MemoryRecord and SourceRecord serialization."""

from datetime import datetime, timezone

import numpy as np

from anamnesis_mcp.models import MemoryRecord, SourceRecord


class TestMemoryRecord:
    def test_defaults(self):
        r = MemoryRecord(summary="test")
        assert r.summary == "test"
        assert r.context_tags == []
        assert r.project == ""
        assert r.artifact_type == "note"
        assert r.outcome == "solved"
        assert r.redacted is False
        assert r.cue_vector == []
        assert r.id  # UUID generated
        assert r.created_at.tzinfo is not None

    def test_to_dict_excludes_vector(self):
        r = MemoryRecord(summary="s", cue_vector=[1.0, 2.0])
        d = r.to_dict()
        assert "cue_vector" not in d
        assert d["summary"] == "s"
        assert d["id"] == r.id
        assert isinstance(d["created_at"], str)

    def test_to_dict_fields(self):
        r = MemoryRecord(
            summary="s",
            context_tags=["a", "b"],
            project="proj",
            project_path="/tmp/proj",
            artifact_type="conversation",
            artifact_ptr="/tmp/file.jsonl",
            outcome="eureka",
            redacted=True,
        )
        d = r.to_dict()
        assert d["context_tags"] == ["a", "b"]
        assert d["project"] == "proj"
        assert d["project_path"] == "/tmp/proj"
        assert d["artifact_type"] == "conversation"
        assert d["artifact_ptr"] == "/tmp/file.jsonl"
        assert d["outcome"] == "eureka"
        assert d["redacted"] is True

    def test_to_row_vector_encoding(self):
        vec = [1.0, 2.0, 3.0]
        r = MemoryRecord(summary="s", cue_vector=vec)
        row = r.to_row()
        assert isinstance(row["cue_vector"], bytes)
        decoded = np.frombuffer(row["cue_vector"], dtype=np.float32)
        np.testing.assert_array_almost_equal(decoded, vec)

    def test_to_row_empty_vector(self):
        r = MemoryRecord(summary="s", cue_vector=[])
        row = r.to_row()
        assert row["cue_vector"] is None

    def test_to_row_tags_as_json(self):
        r = MemoryRecord(summary="s", context_tags=["python", "mcp"])
        row = r.to_row()
        assert row["context_tags"] == '["python", "mcp"]'

    def test_to_row_redacted_as_int(self):
        r = MemoryRecord(summary="s", redacted=True)
        assert r.to_row()["redacted"] == 1
        r2 = MemoryRecord(summary="s", redacted=False)
        assert r2.to_row()["redacted"] == 0

    def test_from_row_roundtrip(self):
        original = MemoryRecord(
            summary="test summary",
            context_tags=["a", "b"],
            project="proj",
            cue_vector=[1.0, 2.0, 3.0],
            redacted=True,
        )
        row = original.to_row()
        restored = MemoryRecord.from_row(row)
        assert restored.id == original.id
        assert restored.summary == original.summary
        assert restored.context_tags == original.context_tags
        assert restored.project == original.project
        assert restored.redacted is True
        np.testing.assert_array_almost_equal(restored.cue_vector, original.cue_vector)

    def test_from_row_empty_vector(self):
        row = MemoryRecord(summary="s").to_row()
        restored = MemoryRecord.from_row(row)
        assert restored.cue_vector == []

    def test_from_row_missing_optional_fields(self):
        row = {
            "id": "test-id",
            "summary": "s",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        r = MemoryRecord.from_row(row)
        assert r.project == ""
        assert r.context_tags == []
        assert r.outcome == "solved"

    def test_datetime_roundtrip(self):
        original = MemoryRecord(summary="s")
        row = original.to_row()
        restored = MemoryRecord.from_row(row)
        assert abs((restored.created_at - original.created_at).total_seconds()) < 1


class TestSourceRecord:
    def test_defaults(self):
        r = SourceRecord(file_path="/tmp/test.jsonl")
        assert r.file_type == "conversation"
        assert r.project == ""
        assert r.chunk_start is None
        assert r.chunk_end is None
        assert r.processed is False

    def test_to_dict(self):
        r = SourceRecord(file_path="/tmp/f", chunk_start=10, chunk_end=50, processed=True)
        d = r.to_dict()
        assert d["file_path"] == "/tmp/f"
        assert d["chunk_start"] == 10
        assert d["chunk_end"] == 50
        assert d["processed"] is True

    def test_to_row_processed_as_int(self):
        r = SourceRecord(file_path="/tmp/f", processed=True)
        assert r.to_row()["processed"] == 1

    def test_from_row_roundtrip(self):
        original = SourceRecord(
            file_path="/tmp/test.jsonl",
            file_type="plan",
            project="myproj",
            chunk_start=1,
            chunk_end=100,
            processed=True,
        )
        row = original.to_row()
        restored = SourceRecord.from_row(row)
        assert restored.id == original.id
        assert restored.file_path == original.file_path
        assert restored.file_type == "plan"
        assert restored.project == "myproj"
        assert restored.chunk_start == 1
        assert restored.chunk_end == 100
        assert restored.processed is True

    def test_from_row_missing_optional_fields(self):
        row = {
            "id": "test-id",
            "file_path": "/tmp/f",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        r = SourceRecord.from_row(row)
        assert r.file_type == "conversation"
        assert r.project == ""
        assert r.processed is False
