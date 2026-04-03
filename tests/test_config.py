"""Tests for configuration helpers."""

import os
from pathlib import Path
from unittest.mock import patch

from anamnesis_mcp.config import (
    get_claude_dir,
    get_db_path,
    get_embedding_backend,
    get_embedding_model,
    get_openai_api_key,
    get_store_dir,
)


class TestConfig:
    def test_get_store_dir_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANAMNESIS_STORE", None)
            d = get_store_dir()
            assert d == Path.home() / ".anamnesis"

    def test_get_store_dir_custom(self, tmp_path):
        with patch.dict(os.environ, {"ANAMNESIS_STORE": str(tmp_path / "custom")}):
            d = get_store_dir()
            assert d == tmp_path / "custom"
            assert d.exists()

    def test_get_db_path(self):
        with patch.dict(os.environ, {"ANAMNESIS_STORE": "/tmp/test-anamnesis"}):
            p = get_db_path()
            assert p == Path("/tmp/test-anamnesis/memories.db")

    def test_get_claude_dir_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PROJECTS_DIR", None)
            d = get_claude_dir()
            assert d == Path.home() / ".claude" / "projects"

    def test_get_claude_dir_custom(self):
        with patch.dict(os.environ, {"CLAUDE_PROJECTS_DIR": "/custom/claude"}):
            d = get_claude_dir()
            assert d == Path("/custom/claude")

    def test_get_embedding_backend_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANAMNESIS_EMBEDDING_BACKEND", None)
            assert get_embedding_backend() == "local"

    def test_get_embedding_backend_openai(self):
        with patch.dict(os.environ, {"ANAMNESIS_EMBEDDING_BACKEND": "openai"}):
            assert get_embedding_backend() == "openai"

    def test_get_embedding_model_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANAMNESIS_EMBEDDING_MODEL", None)
            assert get_embedding_model() is None

    def test_get_embedding_model_custom(self):
        with patch.dict(os.environ, {"ANAMNESIS_EMBEDDING_MODEL": "custom-model"}):
            assert get_embedding_model() == "custom-model"

    def test_get_openai_api_key_absent(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            assert get_openai_api_key() is None

    def test_get_openai_api_key_present(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            assert get_openai_api_key() == "test-key"
