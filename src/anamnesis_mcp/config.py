"""Configuration helpers — env vars and store paths."""

from __future__ import annotations

import os
from pathlib import Path


def get_store_dir() -> Path:
    """Return the Anamnesis store directory, creating it if needed."""
    store_dir = Path(os.environ.get("ANAMNESIS_STORE", Path.home() / ".anamnesis"))
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


def get_db_path() -> Path:
    """Return path to the SQLite database."""
    return get_store_dir() / "memories.db"


def get_claude_dir() -> Path:
    """Return the Claude projects directory."""
    return Path(os.environ.get("CLAUDE_PROJECTS_DIR", Path.home() / ".claude" / "projects"))


def get_embedding_backend() -> str:
    """Return the embedding backend: 'local' (default) or 'openai'."""
    return os.environ.get("ANAMNESIS_EMBEDDING_BACKEND", "local")


def get_embedding_model() -> str | None:
    """Return the embedding model name override, or None for backend default."""
    return os.environ.get("ANAMNESIS_EMBEDDING_MODEL")


def get_openai_api_key() -> str | None:
    """Return the OpenAI API key from environment (only needed for openai backend)."""
    return os.environ.get("OPENAI_API_KEY")
