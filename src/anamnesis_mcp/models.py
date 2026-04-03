"""Data models for Anamnesis — MemoryRecord and SourceRecord."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np


@dataclass
class MemoryRecord:
    summary: str
    context_tags: list[str] = field(default_factory=list)
    project: str = ""
    project_path: str = ""
    artifact_type: str = "note"  # conversation | diff | trace | decision | note
    artifact_ptr: str = ""  # file path + optional line range
    outcome: str = "solved"  # solved | eureka | abandoned | partial
    redacted: bool = False
    cue_vector: list[float] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Serialize to dict for JSON responses. Excludes cue_vector."""
        return {
            "id": self.id,
            "summary": self.summary,
            "context_tags": self.context_tags,
            "project": self.project,
            "project_path": self.project_path,
            "artifact_type": self.artifact_type,
            "artifact_ptr": self.artifact_ptr,
            "outcome": self.outcome,
            "redacted": self.redacted,
            "created_at": self.created_at.isoformat(),
        }

    def to_row(self) -> dict:
        """Serialize to a dict suitable for SQLite insertion."""
        return {
            "id": self.id,
            "cue_vector": np.array(self.cue_vector, dtype=np.float32).tobytes() if self.cue_vector else None,
            "context_tags": json.dumps(self.context_tags),
            "project": self.project,
            "project_path": self.project_path,
            "artifact_type": self.artifact_type,
            "artifact_ptr": self.artifact_ptr,
            "summary": self.summary,
            "outcome": self.outcome,
            "redacted": int(self.redacted),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> MemoryRecord:
        """Reconstruct a MemoryRecord from a SQLite row dict."""
        cue_vector = []
        if row.get("cue_vector"):
            cue_vector = np.frombuffer(row["cue_vector"], dtype=np.float32).tolist()

        return cls(
            id=row["id"],
            cue_vector=cue_vector,
            context_tags=json.loads(row["context_tags"]) if row.get("context_tags") else [],
            project=row.get("project", ""),
            project_path=row.get("project_path", ""),
            artifact_type=row.get("artifact_type", "note"),
            artifact_ptr=row.get("artifact_ptr", ""),
            summary=row["summary"],
            outcome=row.get("outcome", "solved"),
            redacted=bool(row.get("redacted", 0)),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


@dataclass
class SourceRecord:
    file_path: str
    file_type: str = "conversation"  # conversation | plan
    project: str = ""
    chunk_start: int | None = None  # line start (None = whole file, unprocessed)
    chunk_end: int | None = None  # line end
    processed: bool = False  # True = memory created from this chunk
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "project": self.project,
            "chunk_start": self.chunk_start,
            "chunk_end": self.chunk_end,
            "processed": self.processed,
            "created_at": self.created_at.isoformat(),
        }

    def to_row(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "project": self.project,
            "chunk_start": self.chunk_start,
            "chunk_end": self.chunk_end,
            "processed": int(self.processed),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> SourceRecord:
        return cls(
            id=row["id"],
            file_path=row["file_path"],
            file_type=row.get("file_type", "conversation"),
            project=row.get("project", ""),
            chunk_start=row.get("chunk_start"),
            chunk_end=row.get("chunk_end"),
            processed=bool(row.get("processed", 0)),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
