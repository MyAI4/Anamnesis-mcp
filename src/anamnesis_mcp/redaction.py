"""Secret redaction — regex-based stripping at write time."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

REDACT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "api_key_assignment",
        re.compile(
            r"(api_key|secret|password|token|credential)\s*[=:]\s*\S+",
            re.IGNORECASE,
        ),
    ),
    (
        "base64_blob",
        re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
    ),
    (
        "hex_key",
        re.compile(r"[0-9a-f]{32,}", re.IGNORECASE),
    ),
    (
        "aws_credential",
        re.compile(r"aws_\w+\s*=\s*\S+", re.IGNORECASE),
    ),
    (
        "api_key_prefix",
        re.compile(r"(sk|pk|rk)[-_][a-zA-Z0-9_-]{20,}"),
    ),
]


@dataclass
class RedactionResult:
    text: str
    was_redacted: bool = False
    patterns_fired: list[str] = field(default_factory=list)


def redact(text: str) -> RedactionResult:
    """Apply all redaction patterns. Returns redacted text and metadata."""
    result_text = text
    patterns_fired: list[str] = []

    for name, pattern in REDACT_PATTERNS:
        if pattern.search(result_text):
            result_text = pattern.sub(f"[REDACTED:{name}]", result_text)
            patterns_fired.append(name)

    return RedactionResult(
        text=result_text,
        was_redacted=len(patterns_fired) > 0,
        patterns_fired=patterns_fired,
    )
