"""Claude Code session discovery — finds session and plan files."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def discover_sessions(claude_dir: Path) -> list[dict]:
    """
    Find all .jsonl conversation files under the Claude projects directory.

    Returns list of dicts with file_path, file_type, project, and line_count.
    """
    if not claude_dir.exists():
        logger.warning("Claude projects directory not found: %s", claude_dir)
        return []

    results = []
    for jsonl_path in sorted(claude_dir.rglob("*.jsonl")):
        line_count = _count_lines(jsonl_path)
        project = _extract_project_slug(jsonl_path)
        results.append({
            "file_path": str(jsonl_path),
            "file_type": "conversation",
            "project": project,
            "line_count": line_count,
        })

    return results


def discover_plans(claude_dir: Path) -> list[dict]:
    """
    Find plan files (.md) under Claude's plans directories.

    Returns list of dicts with file_path, file_type, project, and line_count.
    """
    if not claude_dir.exists():
        return []

    results = []
    # Plans are typically under ~/.claude/plans/ or project-level plan dirs
    plans_dir = claude_dir.parent / "plans"
    if plans_dir.exists():
        for md_path in sorted(plans_dir.rglob("*.md")):
            line_count = _count_lines(md_path)
            results.append({
                "file_path": str(md_path),
                "file_type": "plan",
                "project": "",
                "line_count": line_count,
            })

    return results


def read_file_lines(file_path: str, start: int, end: int) -> str:
    """
    Read lines from a file (1-indexed, inclusive).

    Returns the raw text of the specified line range.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    lines = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if i > end:
                    break
                if i >= start:
                    lines.append(line)
    except OSError as e:
        return f"Error reading file: {e}"

    return "".join(lines)


def _count_lines(path: Path) -> int:
    """Count lines in a file efficiently."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _extract_project_slug(jsonl_path: Path) -> str:
    """Extract the project slug from the file path."""
    parts = jsonl_path.parts
    try:
        projects_idx = parts.index("projects")
        if projects_idx + 1 < len(parts) - 1:
            return parts[projects_idx + 1]
    except ValueError:
        pass
    return jsonl_path.parent.name
