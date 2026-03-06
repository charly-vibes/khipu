"""Redaction: strip secrets before any content reaches an LLM."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, replace
from typing import Any

from khipu.model import Exchange, Session, ToolCall

# Each pattern: (name, compiled_regex)
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # API keys
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}", re.ASCII)),
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9]{36,}", re.ASCII)),
    ("aws_access_key", re.compile(r"\bAKIA[A-Z0-9]{16}\b", re.ASCII)),
    # Auth headers / bearer tokens
    ("bearer_token", re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-_.~+/]{20,}")),
    # Connection strings
    ("postgres_url", re.compile(r"postgres(?:ql)?://[^\s'\"]+")),
    ("mongodb_url", re.compile(r"mongodb(?:\+srv)?://[^\s'\"]+")),
    ("redis_url", re.compile(r"redis://[^\s'\"]+")),
    ("mysql_url", re.compile(r"mysql://[^\s'\"]+")),
    # Private keys (PEM blocks)
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.DOTALL)),
    # Env var assignments with secrets
    ("env_secret", re.compile(r"(?i)(?:API_KEY|SECRET|PASSWORD|TOKEN|PASSWD|CREDENTIAL)\s*=\s*\S+")),
    # AWS secret access key (typically paired with access key ID)
    ("aws_secret", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*\S+")),
    # Email addresses
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # IPv4 addresses (non-loopback, non-private); validates each octet 0-255
    ("ip_address", re.compile(
        r"\b(?!(?:127\.|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)\d)"
        r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
    )),
    # IPv6 addresses — full 8-group form (loopback ::1 excluded by requiring ≥2 groups)
    ("ipv6_address", re.compile(
        r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
        r"|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"
        r"|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}"
        r"|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}"
        r"|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}"
        r"|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}"
        r"|[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}"
    )),
]


def redact_str(text: str) -> str:
    """Replace all secret patterns in *text* with [REDACTED:<type>] tokens."""
    for name, pattern in _PATTERNS:
        text = pattern.sub(f"[REDACTED:{name}]", text)
    return text


def _redact_any(value: Any) -> Any:
    """Recursively redact strings inside any JSON-compatible value."""
    if isinstance(value, str):
        return redact_str(value)
    if isinstance(value, dict):
        return {k: _redact_any(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_any(item) for item in value]
    return value


def _redact_tool_call(tc: ToolCall) -> ToolCall:
    return ToolCall(
        tool=tc.tool,
        input=_redact_any(tc.input),
        output=_redact_any(tc.output),
        success=tc.success,
    )


def _redact_exchange(ex: Exchange) -> Exchange:
    tool_calls = None
    if ex.tool_calls:
        tool_calls = [_redact_tool_call(tc) for tc in ex.tool_calls]
    return Exchange(
        role=ex.role,
        content=redact_str(ex.content),
        tool_calls=tool_calls,
    )


def redact_session(session: Session) -> Session:
    """Return a new Session with all secrets replaced by [REDACTED:<type>] tokens."""
    return replace(
        session,
        exchanges=[_redact_exchange(ex) for ex in session.exchanges],
    )


def redact_sessions(
    sessions: list[Session],
    *,
    enabled: bool = True,
) -> list[Session]:
    """Redact a list of sessions.

    When *enabled* is False, emit a warning to stderr and return sessions unchanged.
    """
    if not enabled:
        print(
            "WARNING: redaction is disabled. Secrets in traces will be sent to the LLM.",
            file=sys.stderr,
        )
        return sessions
    return [redact_session(s) for s in sessions]
