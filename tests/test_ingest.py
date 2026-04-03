"""Tests for Claude session discovery, file reading, and path validation."""

from pathlib import Path

from anamnesis_mcp.ingest.claude_code import (
    _count_lines,
    _extract_project_slug,
    discover_plans,
    discover_sessions,
    read_file_lines,
    validate_source_path,
)


class TestDiscoverSessions:
    def test_finds_jsonl_files(self, tmp_path):
        proj = tmp_path / "projects" / "my-project"
        proj.mkdir(parents=True)
        (proj / "session1.jsonl").write_text("line1\nline2\n")
        (proj / "session2.jsonl").write_text("line1\n")
        (proj / "notes.txt").write_text("not a session")

        results = discover_sessions(tmp_path / "projects")
        assert len(results) == 2
        assert all(r["file_type"] == "conversation" for r in results)

    def test_returns_line_counts(self, tmp_path):
        proj = tmp_path / "projects" / "p1"
        proj.mkdir(parents=True)
        (proj / "s.jsonl").write_text("a\nb\nc\n")

        results = discover_sessions(tmp_path / "projects")
        assert results[0]["line_count"] == 3

    def test_extracts_project_slug(self, tmp_path):
        proj = tmp_path / "projects" / "c--my-cool-project"
        proj.mkdir(parents=True)
        (proj / "s.jsonl").write_text("line\n")

        results = discover_sessions(tmp_path / "projects")
        assert results[0]["project"] == "c--my-cool-project"

    def test_nonexistent_dir(self, tmp_path):
        results = discover_sessions(tmp_path / "nope")
        assert results == []

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "projects"
        d.mkdir()
        results = discover_sessions(d)
        assert results == []


class TestDiscoverPlans:
    def test_finds_md_files(self, tmp_path):
        proj = tmp_path / "projects"
        proj.mkdir()
        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "plan1.md").write_text("# Plan\n")
        (plans / "plan2.md").write_text("# Other\nDetails\n")

        results = discover_plans(proj)
        assert len(results) == 2
        assert all(r["file_type"] == "plan" for r in results)
        assert all(r["project"] == "" for r in results)

    def test_nonexistent_plans_dir(self, tmp_path):
        proj = tmp_path / "projects"
        proj.mkdir()
        # No plans/ sibling
        results = discover_plans(proj)
        assert results == []

    def test_nonexistent_claude_dir(self, tmp_path):
        results = discover_plans(tmp_path / "nope")
        assert results == []


class TestReadFileLines:
    def test_reads_range(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\nline4\nline5\n")
        text = read_file_lines(str(f), 2, 4)
        assert text == "line2\nline3\nline4\n"

    def test_reads_single_line(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("a\nb\nc\n")
        text = read_file_lines(str(f), 2, 2)
        assert text == "b\n"

    def test_end_beyond_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("a\nb\n")
        text = read_file_lines(str(f), 1, 999)
        assert text == "a\nb\n"

    def test_missing_file(self):
        text = read_file_lines("/nonexistent/file.txt", 1, 10)
        assert "Error" in text

    def test_no_path_leak_on_missing_file(self):
        text = read_file_lines("/secret/path/file.txt", 1, 10)
        assert "/secret/path" not in text


class TestValidateSourcePath:
    def test_valid_path_in_projects(self, tmp_path):
        claude_dir = tmp_path / "projects"
        claude_dir.mkdir()
        f = claude_dir / "session.jsonl"
        f.write_text("")
        assert validate_source_path(str(f), claude_dir) is None

    def test_valid_path_in_plans(self, tmp_path):
        claude_dir = tmp_path / "projects"
        claude_dir.mkdir()
        plans = tmp_path / "plans"
        plans.mkdir()
        f = plans / "plan.md"
        f.write_text("")
        assert validate_source_path(str(f), claude_dir) is None

    def test_rejects_outside_path(self, tmp_path):
        claude_dir = tmp_path / "projects"
        claude_dir.mkdir()
        err = validate_source_path("/etc/passwd", claude_dir)
        assert err is not None
        assert "outside" in err.lower()

    def test_rejects_traversal(self, tmp_path):
        claude_dir = tmp_path / "projects"
        claude_dir.mkdir()
        evil = str(claude_dir / ".." / ".." / "etc" / "passwd")
        err = validate_source_path(evil, claude_dir)
        assert err is not None

    def test_nested_subdir_valid(self, tmp_path):
        claude_dir = tmp_path / "projects"
        sub = claude_dir / "proj" / "subagents"
        sub.mkdir(parents=True)
        f = sub / "agent.jsonl"
        f.write_text("")
        assert validate_source_path(str(f), claude_dir) is None


class TestCountLines:
    def test_counts_lines(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("a\nb\nc\n")
        assert _count_lines(f) == 3

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert _count_lines(f) == 0

    def test_nonexistent_file(self, tmp_path):
        assert _count_lines(tmp_path / "nope.txt") == 0


class TestExtractProjectSlug:
    def test_extracts_slug(self):
        p = Path("/home/user/.claude/projects/my-project/session.jsonl")
        assert _extract_project_slug(p) == "my-project"

    def test_nested_path(self):
        p = Path("/home/user/.claude/projects/my-project/subagents/agent.jsonl")
        assert _extract_project_slug(p) == "my-project"

    def test_no_projects_in_path(self):
        p = Path("/tmp/random/session.jsonl")
        slug = _extract_project_slug(p)
        assert slug == "random"  # falls back to parent dir name
