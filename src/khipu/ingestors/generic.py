"""Built-in generic ingestor: markdown/text conversation fallback."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from khipu.model import Exchange, Session

EXTENSIONS = [".md", ".txt"]
CONTENT_PATTERN = r"^(Human|User|Assistant|AI|Claude|GPT)\s*:"
PRIORITY = -100  # Always last

_ROLE_MAP = {
    "human": "human",
    "user": "human",
    "assistant": "agent",
    "ai": "agent",
    "claude": "agent",
    "gpt": "agent",
}

_HEADER_RE = re.compile(r"^(Human|User|Assistant|AI|Claude|GPT)\s*:\s*", re.IGNORECASE | re.MULTILINE)


def can_handle(path: Path) -> bool:
    if path.suffix not in (".md", ".txt"):
        return False
    try:
        text = path.read_text(errors="replace")[:2000]
    except OSError:
        return False
    return bool(re.search(CONTENT_PATTERN, text, re.MULTILINE))


def ingest(path: Path) -> list[Session]:
    text = path.read_text(errors="replace")
    # Split on role headers, keeping delimiters
    parts = _HEADER_RE.split(text)
    # parts: [pre, role1, content1, role2, content2, ...]
    exchanges: list[Exchange] = []
    # Skip leading non-matched text (parts[0])
    i = 1
    while i + 1 < len(parts):
        role_raw = parts[i].strip().lower()
        content = parts[i + 1].strip()
        role = _ROLE_MAP.get(role_raw, "agent")
        if content:
            exchanges.append(Exchange(role=role, content=content))
        i += 2

    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return [Session(source="generic", timestamp=ts, exchanges=exchanges)]
