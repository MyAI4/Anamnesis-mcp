"""SQLite memory store — persistence layer for Anamnesis."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .models import MemoryRecord, SourceRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id              TEXT PRIMARY KEY,
    cue_vector      BLOB,
    context_tags    TEXT NOT NULL DEFAULT '[]',
    project         TEXT NOT NULL DEFAULT '',
    project_path    TEXT NOT NULL DEFAULT '',
    artifact_type   TEXT NOT NULL DEFAULT 'note',
    artifact_ptr    TEXT NOT NULL DEFAULT '',
    summary         TEXT NOT NULL,
    outcome         TEXT NOT NULL DEFAULT 'solved',
    redacted        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    file_path   TEXT NOT NULL,
    file_type   TEXT NOT NULL DEFAULT 'conversation',
    project     TEXT NOT NULL DEFAULT '',
    chunk_start INTEGER,
    chunk_end   INTEGER,
    processed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_processed ON sources(processed);
CREATE INDEX IF NOT EXISTS idx_sources_file_path ON sources(file_path);
"""


class MemoryStore:
    def __init__(self, db_path: str | Path = ":memory:"):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- Memory CRUD ---

    def insert_memory(self, record: MemoryRecord) -> str:
        """Insert a MemoryRecord. Returns the record id."""
        row = record.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        self._conn.execute(
            f"INSERT INTO memories ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        self._conn.commit()
        return record.id

    def get_memory(self, record_id: str) -> MemoryRecord | None:
        """Fetch a single memory by id."""
        cur = self._conn.execute("SELECT * FROM memories WHERE id = ?", (record_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return MemoryRecord.from_row(dict(row))

    def search_keyword(
        self,
        query: str = "",
        tags: list[str] | None = None,
        project: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Search memories by keyword in summary + optional filters."""
        conditions: list[str] = []
        params: list[str | int] = []

        if query:
            conditions.append("summary LIKE ?")
            params.append(f"%{query}%")

        if project:
            conditions.append("project = ?")
            params.append(project)

        if tags:
            for tag in tags:
                conditions.append("context_tags LIKE ?")
                params.append(f'%"{tag}"%')

        where = " AND ".join(conditions) if conditions else "1=1"
        cur = self._conn.execute(
            f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC LIMIT ?",
            [*params, limit],
        )
        return [MemoryRecord.from_row(dict(r)) for r in cur.fetchall()]

    def get_all_vectors(self) -> list[tuple[str, np.ndarray]]:
        """Return (id, vector) pairs for all memories with vectors."""
        cur = self._conn.execute(
            "SELECT id, cue_vector FROM memories WHERE cue_vector IS NOT NULL"
        )
        results = []
        for row in cur.fetchall():
            vec = np.frombuffer(row["cue_vector"], dtype=np.float32)
            if len(vec) > 0:
                results.append((row["id"], vec))
        return results

    def get_stats(self) -> dict:
        """Return usage statistics."""
        stats: dict = {}

        cur = self._conn.execute(
            "SELECT project, COUNT(*) as cnt FROM memories WHERE project != '' "
            "GROUP BY project ORDER BY cnt DESC LIMIT 20"
        )
        stats["by_project"] = {r["project"]: r["cnt"] for r in cur.fetchall()}

        cur = self._conn.execute(
            "SELECT outcome, COUNT(*) as cnt FROM memories GROUP BY outcome"
        )
        stats["by_outcome"] = {r["outcome"]: r["cnt"] for r in cur.fetchall()}

        cur = self._conn.execute("SELECT context_tags FROM memories")
        tag_counter: Counter[str] = Counter()
        for row in cur.fetchall():
            tags = json.loads(row["context_tags"]) if row["context_tags"] else []
            tag_counter.update(tags)
        stats["top_tags"] = dict(tag_counter.most_common(20))

        cur = self._conn.execute("SELECT COUNT(*) as cnt FROM memories")
        stats["total_memories"] = cur.fetchone()["cnt"]

        cur = self._conn.execute("SELECT COUNT(*) as cnt FROM sources WHERE processed = 0")
        stats["unprocessed_sources"] = cur.fetchone()["cnt"]

        return stats

    # --- Source CRUD ---

    def insert_source(self, record: SourceRecord) -> str:
        """Insert a SourceRecord. Returns the record id."""
        row = record.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        self._conn.execute(
            f"INSERT INTO sources ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        self._conn.commit()
        return record.id

    def get_unprocessed_sources(self, limit: int = 50) -> list[SourceRecord]:
        """Return unprocessed source chunks."""
        cur = self._conn.execute(
            "SELECT * FROM sources WHERE processed = 0 ORDER BY created_at ASC LIMIT ?",
            (limit,),
        )
        return [SourceRecord.from_row(dict(r)) for r in cur.fetchall()]

    def mark_source_processed(self, source_id: str) -> bool:
        """Mark a source chunk as processed. Returns False if not found."""
        cur = self._conn.execute(
            "UPDATE sources SET processed = 1 WHERE id = ?",
            (source_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def has_source_file(self, file_path: str) -> bool:
        """Check if a source file has already been registered."""
        cur = self._conn.execute(
            "SELECT 1 FROM sources WHERE file_path = ? LIMIT 1",
            (file_path,),
        )
        return cur.fetchone() is not None

    def delete_sources_for_file(self, file_path: str) -> int:
        """Delete all source records for a file (used when re-splitting)."""
        cur = self._conn.execute(
            "DELETE FROM sources WHERE file_path = ?",
            (file_path,),
        )
        self._conn.commit()
        return cur.rowcount
