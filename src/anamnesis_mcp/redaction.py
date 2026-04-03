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
        "bearer_token",
        re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    ),
    (
        "jwt_token",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"),
    ),
    (
        "pem_private_key",
        re.compile(r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH)?\s*PRIVATE KEY-----"),
    ),
    (
        "connection_string",
        re.compile(
            r"(postgres(?:ql)?|mysql|mongodb|redis|amqp)(\+\w+)?://\S+",
            re.IGNORECASE,
        ),
    ),
    (
        "aws_credential",
        re.compile(r"aws_\w+\s*=\s*\S+", re.IGNORECASE),
    ),
    (
        "api_key_prefix",
        re.compile(r"(sk|pk|rk|ghp|gho|ghu|ghs|github_pat|xox[bpas])[-_][a-zA-Z0-9_-]{20,}"),
    ),
    (
        "google_api_key",
        re.compile(r"AIza[A-Za-z0-9_-]{35}"),
    ),
    (
        "base64_blob",
        re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
    ),
    (
        "hex_key",
        re.compile(r"[0-9a-f]{32,}", re.IGNORECASE),
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
