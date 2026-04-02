"""Anamnesis MCP server — Claude-native persistent memory."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .config import (
    get_claude_dir,
    get_db_path,
    get_embedding_backend,
    get_embedding_model,
    get_openai_api_key,
)
from .embeddings import EmbeddingPipeline, create_backend
from .ingest.claude_code import discover_plans, discover_sessions, read_file_lines
from .models import MemoryRecord, SourceRecord
from .redaction import redact
from .store import MemoryStore

logger = logging.getLogger("anamnesis")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

SERVER_INSTRUCTIONS = """\
Anamnesis is your long-term memory across all projects and sessions.
It stores cue-pointer records — lightweight summaries with keyword tags
that link back to full original conversations and plans on the user's machine.
When similar context arises in a new session, you can recall these memories
and recover the full original context.

== ONBOARDING (first session or when memory is empty) ==

If the user asks you to import their history, or if you notice your memory
is empty (anamnesis_recall returns no results on a substantive query):

1. Call anamnesis_scan_sources to discover unprocessed Claude session files.
2. For each discovered file, call anamnesis_split_source with appropriate
   line ranges based on the file size (aim for chunks of 200-400 lines).
3. For each chunk, call anamnesis_fetch_source to read the raw text.
4. Read and understand what the conversation/plan is about.
5. Call anamnesis_create_memory with:
   - A focused summary (2-3 sentences) emphasizing keywords that would
     trigger recollection in a future session facing a similar problem.
   - Relevant context_tags (technologies, patterns, problem types).
   - The project name and artifact pointer.

Process sources iteratively. You do not need to process all sources in
one session — prioritize recent and large conversations.

== AFTER COMPLETING A TASK OR PLAN ==

When you finish a non-trivial task — implementing a feature, fixing a
hard bug, making an architectural decision, discovering a non-obvious
pattern — create a memory by calling anamnesis_create_memory. You already
know what happened in the conversation. Craft a summary focused on:
- What the problem was and what made it hard
- What the solution was and why it worked
- Keywords and technology names for future recollection

Do not create memories for routine, trivial, or obvious work.

== BEFORE STARTING WORK ==

At the start of any non-trivial problem, call anamnesis_recall with a
natural-language description of what you're about to work on. If relevant
memories surface, use the artifact_ptr to locate and read the full
original context before proceeding.

== WHEN THE USER ASKS ==

If the user says "remember this", "save this to memory", or similar,
call anamnesis_create_memory with a summary of the current context.

If the user asks "what do you remember about X" or "have we done
something like this before", call anamnesis_recall or anamnesis_search.

== SECURITY ==

NEVER store secrets, credentials, API keys, passwords, or proprietary
business logic in memory summaries. Store the shape of what happened,
never the values. The server applies automatic redaction, but you should
also avoid including sensitive content in the summary you craft.
"""

@asynccontextmanager
async def _lifespan(app: FastMCP) -> AsyncIterator[None]:
    """Eagerly warm up the store and embedding model at server start."""
    logger.info("Anamnesis MCP server starting up...")
    _get_store()  # open DB immediately
    asyncio.create_task(_warmup_embeddings())  # load model in background
    yield
    logger.info("Anamnesis MCP server shutting down.")


mcp = FastMCP("anamnesis", instructions=SERVER_INSTRUCTIONS, lifespan=_lifespan)

# Lazy singletons
_store: MemoryStore | None = None
_embeddings: EmbeddingPipeline | None = None
_embeddings_ready = asyncio.Event()
_embeddings_error: str | None = None

_executor = ThreadPoolExecutor(max_workers=1)


def _get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore(get_db_path())
        logger.info("SQLite store opened at %s", get_db_path())
    return _store


def _load_backend_sync() -> EmbeddingPipeline:
    """Blocking model load — meant to run in a thread."""
    t0 = time.perf_counter()
    logger.info("Loading embedding model (this may take a moment on first run)...")
    backend = create_backend(
        backend=get_embedding_backend(),
        model=get_embedding_model(),
        api_key=get_openai_api_key(),
    )
    pipeline = EmbeddingPipeline(backend)
    elapsed = time.perf_counter() - t0
    logger.info("Embedding model ready (%.1fs)", elapsed)
    return pipeline


async def _warmup_embeddings() -> None:
    """Pre-load embeddings in background so first tool call is fast."""
    global _embeddings, _embeddings_error
    try:
        loop = asyncio.get_event_loop()
        _embeddings = await loop.run_in_executor(_executor, _load_backend_sync)
    except Exception as e:
        _embeddings_error = str(e)
        logger.error("Failed to load embedding model: %s", e)
    finally:
        _embeddings_ready.set()


async def _get_embeddings() -> EmbeddingPipeline:
    """Wait for warmup to finish, then return the pipeline."""
    if not _embeddings_ready.is_set():
        logger.info("Waiting for embedding model to finish loading...")
        await asyncio.wait_for(_embeddings_ready.wait(), timeout=120)
    if _embeddings_error:
        raise RuntimeError(f"Embedding model failed to load: {_embeddings_error}")
    assert _embeddings is not None
    return _embeddings


# --- Health ---


@mcp.tool(
    description=(
        "Quick health check — returns server status and whether the embedding "
        "model is loaded. Use this to verify the MCP server is running before "
        "calling heavier tools like anamnesis_recall."
    )
)
async def anamnesis_ping() -> dict:
    """Check server health without loading the embedding model."""
    store = _get_store()
    stats = store.get_stats()
    return {
        "status": "ok",
        "embeddings_ready": _embeddings_ready.is_set(),
        "embeddings_error": _embeddings_error,
        "total_memories": stats["total_memories"],
        "unprocessed_sources": stats["unprocessed_sources"],
    }


# --- Onboarding Tools ---


@mcp.tool(
    description=(
        "Discover Claude session and plan files that have not yet been imported "
        "into Anamnesis. Returns a paginated list of files with their paths, types, "
        "projects, and line counts. Use this as the first step when importing the "
        "user's conversation history into memory. Call again with offset to get more."
    )
)
async def anamnesis_scan_sources(limit: int = 20, offset: int = 0) -> dict:
    """Scan for unprocessed Claude session and plan files."""
    store = _get_store()
    claude_dir = get_claude_dir()

    sessions = discover_sessions(claude_dir)
    plans = discover_plans(claude_dir)
    all_sources = sessions + plans

    # Filter out already-registered files
    new_sources = [s for s in all_sources if not store.has_source_file(s["file_path"])]

    page = new_sources[offset:offset + limit]

    return {
        "total_found": len(all_sources),
        "new_sources": len(new_sources),
        "showing": len(page),
        "offset": offset,
        "has_more": offset + limit < len(new_sources),
        "sources": page,
    }


@mcp.tool(
    description=(
        "Register a source file in the Anamnesis database, split into chunks by "
        "line range. Call this after anamnesis_scan_sources to break a large file "
        "into manageable pieces for reading and memory creation. Each chunk becomes "
        "a source record that can be fetched and processed into a memory."
    )
)
async def anamnesis_split_source(
    file_path: str,
    file_type: str,
    project: str,
    chunks: list[dict],
) -> dict:
    """
    Register source chunks in the database.

    Args:
        file_path: Absolute path to the source file.
        file_type: 'conversation' or 'plan'.
        project: Project name/slug.
        chunks: List of {"start": int, "end": int} line ranges (1-indexed, inclusive).
    """
    store = _get_store()

    # Clear any existing chunks for this file (allows re-splitting)
    store.delete_sources_for_file(file_path)

    created_ids = []
    for chunk in chunks:
        record = SourceRecord(
            file_path=file_path,
            file_type=file_type,
            project=project,
            chunk_start=chunk["start"],
            chunk_end=chunk["end"],
        )
        store.insert_source(record)
        created_ids.append(record.id)

    return {
        "file_path": file_path,
        "chunks_created": len(created_ids),
        "source_ids": created_ids,
    }


@mcp.tool(
    description=(
        "Read the raw text of a source chunk by its ID. Returns the actual "
        "conversation or plan text from the file at the registered line range. "
        "After reading and understanding the content, call anamnesis_create_memory "
        "to store a summary as a memory."
    )
)
async def anamnesis_fetch_source(source_id: str) -> dict:
    """Fetch the raw text of a source chunk."""
    store = _get_store()
    sources = store.get_unprocessed_sources(limit=1000)
    source = None
    for s in sources:
        if s.id == source_id:
            source = s
            break

    if source is None:
        # Try to find it even if processed
        # Fall back to direct query
        cur = store._conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
        row = cur.fetchone()
        if row is None:
            return {"error": f"Source not found: {source_id}"}
        source = SourceRecord.from_row(dict(row))

    start = source.chunk_start or 1
    end = source.chunk_end or 999999
    text = read_file_lines(source.file_path, start, end)

    return {
        "source_id": source.id,
        "file_path": source.file_path,
        "file_type": source.file_type,
        "project": source.project,
        "line_range": {"start": start, "end": end},
        "text": text,
        "processed": source.processed,
    }


# --- Memory Tools ---


@mcp.tool(
    description=(
        "Store a new memory that you have crafted from reading a source or from "
        "the current conversation. The summary should be 2-3 focused sentences "
        "emphasizing keywords for future recollection. Include relevant technology "
        "names, pattern types, and problem descriptions. If source_id is provided, "
        "the source chunk will be marked as processed."
    )
)
async def anamnesis_create_memory(
    summary: str,
    context_tags: list[str],
    project: str,
    project_path: str = "",
    artifact_type: str = "note",
    artifact_ptr: str = "",
    outcome: str = "solved",
    source_id: str | None = None,
) -> dict:
    """Create a memory record with embedding and redaction."""
    store = _get_store()
    embeddings = await _get_embeddings()

    # Redact secrets from the summary
    redaction_result = redact(summary)

    # Generate cue vector from the redacted summary
    cue_vector = await embeddings.embed_async(redaction_result.text)

    record = MemoryRecord(
        summary=redaction_result.text,
        context_tags=context_tags,
        project=project,
        project_path=project_path,
        artifact_type=artifact_type,
        artifact_ptr=artifact_ptr,
        outcome=outcome,
        redacted=redaction_result.was_redacted,
        cue_vector=cue_vector,
    )

    store.insert_memory(record)

    # Mark the source chunk as processed if provided
    if source_id:
        store.mark_source_processed(source_id)

    return {
        "id": record.id,
        "redacted": redaction_result.was_redacted,
        "redaction_warnings": redaction_result.patterns_fired,
    }


@mcp.tool(
    description=(
        "Search your long-term memory by semantic similarity. Use this at the start "
        "of any non-trivial problem, when the current context feels familiar, or when "
        "the user asks what you remember about a topic. Pass a natural-language "
        "description of what you're working on or looking for."
    )
)
async def anamnesis_recall(
    cue: str,
    top_k: int = 5,
    threshold: float = 0.3,
    project: str | None = None,
) -> list[dict]:
    """Search memories by semantic similarity to the cue text."""
    store = _get_store()
    embeddings = await _get_embeddings()

    query_vector = await embeddings.embed_async(cue)
    candidates = store.get_all_vectors()

    if not candidates:
        return []

    # Optional project filter
    if project:
        project_memories = {r.id for r in store.search_keyword(project=project, limit=10000)}
        candidates = [(rid, vec) for rid, vec in candidates if rid in project_memories]

    matches = EmbeddingPipeline.recall(
        query_vector, candidates, top_k=top_k, threshold=threshold
    )

    results = []
    for record_id, score in matches:
        record = store.get_memory(record_id)
        if record:
            d = record.to_dict()
            d["score"] = round(score, 4)
            results.append(d)

    return results


@mcp.tool(
    description=(
        "Keyword and tag search across memories. Faster than recall when you know "
        "specific terms to search for. Supports filtering by tags and project."
    )
)
async def anamnesis_search(
    query: str = "",
    tags: list[str] | None = None,
    project: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search memories by keyword and filters."""
    store = _get_store()
    records = store.search_keyword(query=query, tags=tags, project=project, limit=limit)
    return [r.to_dict() for r in records]


def main():
    """Entry point for the MCP server."""
    logger.info("Starting Anamnesis MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
