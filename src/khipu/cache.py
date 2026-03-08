"""Two-layer cache for khipu: session ingest results and analyzer LLM results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "khipu"


def _cache_root() -> Path:
    return _DEFAULT_CACHE_DIR


# ---------------------------------------------------------------------------
# Session ingest cache
# ---------------------------------------------------------------------------


def _session_key(path: Path) -> str:
    stat = path.stat()
    raw = f"{path.resolve()}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_sessions(path: Path) -> list[dict[str, Any]] | None:
    """Return cached session dicts for *path*, or None on miss."""
    key = _session_key(path)
    cache_file = _cache_root() / "sessions" / f"{key}.json"
    try:
        return json.loads(cache_file.read_text())  # type: ignore[return-value]
    except (OSError, json.JSONDecodeError):
        return None


def put_sessions(path: Path, sessions: list[dict[str, Any]]) -> None:
    """Persist session dicts for *path* to the cache."""
    d = _cache_root() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    key = _session_key(path)
    (d / f"{key}.json").write_text(json.dumps(sessions))


# ---------------------------------------------------------------------------
# Analyzer result cache
# ---------------------------------------------------------------------------
# Key = sha256 of the fully-rendered prompt text, which encodes both the
# session data and the prompt template version (any change in either
# invalidates the entry).


def _analysis_key(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.encode()).hexdigest()


def get_analysis(prompt_text: str) -> Any | None:
    """Return cached parsed result for this exact prompt, or None on miss."""
    key = _analysis_key(prompt_text)
    cache_file = _cache_root() / "analysis" / f"{key}.json"
    try:
        return json.loads(cache_file.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def put_analysis(prompt_text: str, result: Any) -> None:
    """Persist LLM result for this exact prompt to the cache."""
    d = _cache_root() / "analysis"
    d.mkdir(parents=True, exist_ok=True)
    key = _analysis_key(prompt_text)
    (d / f"{key}.json").write_text(json.dumps(result))
