"""Tests for the cache module and cache integration in ingest/analyze."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from khipu import cache
from khipu.ingest import ingest
from khipu.model import Exchange, Session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> Session:
    return Session(
        source="claude-code",
        timestamp=datetime.now(tz=UTC),
        exchanges=[Exchange(role="human", content="hello")],
    )


def _write_jsonl(tmp_path: Path, name: str = "trace.jsonl") -> Path:
    p = tmp_path / name
    line1 = json.dumps(
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}},
    )
    line2 = json.dumps(
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok", "is_error": False},
    )
    p.write_text(line1 + "\n" + line2 + "\n")
    return p


# ---------------------------------------------------------------------------
# cache.py unit tests
# ---------------------------------------------------------------------------


class TestSessionCache:
    def test_miss_returns_none(self, tmp_path):
        p = tmp_path / "missing.jsonl"
        p.write_text("{}\n")
        with patch("khipu.cache._cache_root", return_value=tmp_path / "cache"):
            assert cache.get_sessions(p) is None

    def test_roundtrip(self, tmp_path):
        p = tmp_path / "trace.jsonl"
        p.write_text("{}\n")
        sessions = [_make_session().to_dict()]
        with patch("khipu.cache._cache_root", return_value=tmp_path / "cache"):
            cache.put_sessions(p, sessions)
            result = cache.get_sessions(p)
        assert result == sessions

    def test_stale_after_mtime_change(self, tmp_path):
        p = tmp_path / "trace.jsonl"
        p.write_text("{}\n")
        sessions = [_make_session().to_dict()]
        cache_root = tmp_path / "cache"
        with patch("khipu.cache._cache_root", return_value=cache_root):
            cache.put_sessions(p, sessions)
        # Simulate file change by updating mtime
        import os
        import time

        time.sleep(0.01)
        os.utime(p, None)
        with patch("khipu.cache._cache_root", return_value=cache_root):
            assert cache.get_sessions(p) is None


class TestAnalysisCache:
    def test_miss_returns_none(self, tmp_path):
        with patch("khipu.cache._cache_root", return_value=tmp_path / "cache"):
            assert cache.get_analysis("some prompt") is None

    def test_roundtrip(self, tmp_path):
        result = [{"tool": "Bash", "count": 5}]
        with patch("khipu.cache._cache_root", return_value=tmp_path / "cache"):
            cache.put_analysis("my prompt", result)
            assert cache.get_analysis("my prompt") == result

    def test_different_prompts_isolated(self, tmp_path):
        with patch("khipu.cache._cache_root", return_value=tmp_path / "cache"):
            cache.put_analysis("prompt A", [1])
            cache.put_analysis("prompt B", [2])
            assert cache.get_analysis("prompt A") == [1]
            assert cache.get_analysis("prompt B") == [2]


# ---------------------------------------------------------------------------
# Ingest cache integration
# ---------------------------------------------------------------------------


class TestIngestCache:
    def test_cache_miss_calls_ingestor(self, tmp_path):
        p = _write_jsonl(tmp_path)
        cache_root = tmp_path / "cache"
        with patch("khipu.cache._cache_root", return_value=cache_root):
            sessions = ingest(p, use_cache=True)
        assert len(sessions) == 1
        # Cache entry was written
        assert any(cache_root.rglob("*.json"))

    def test_cache_hit_skips_ingestor(self, tmp_path):
        p = _write_jsonl(tmp_path)
        cache_root = tmp_path / "cache"
        # Prime the cache
        with patch("khipu.cache._cache_root", return_value=cache_root):
            ingest(p, use_cache=True)

        # Second call: ingestor should NOT be invoked
        import khipu.ingestors.claude_code as cc

        with (
            patch("khipu.cache._cache_root", return_value=cache_root),
            patch.object(cc, "ingest", wraps=cc.ingest) as mock_ingest,
        ):
            sessions2 = ingest(p, use_cache=True)
            mock_ingest.assert_not_called()
        assert len(sessions2) == 1

    def test_no_cache_flag_bypasses_cache(self, tmp_path):
        p = _write_jsonl(tmp_path)
        cache_root = tmp_path / "cache"
        # Prime the cache
        with patch("khipu.cache._cache_root", return_value=cache_root):
            ingest(p, use_cache=True)

        import khipu.ingestors.claude_code as cc

        with (
            patch("khipu.cache._cache_root", return_value=cache_root),
            patch.object(cc, "ingest", wraps=cc.ingest) as mock_ingest,
        ):
            ingest(p, use_cache=False)
            mock_ingest.assert_called_once()


# ---------------------------------------------------------------------------
# Analyze cache integration
# ---------------------------------------------------------------------------


_FIXED_SESSION = Session(
    source="claude-code",
    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    exchanges=[Exchange(role="human", content="hello")],
)


class TestAnalyzeCache:
    def _sessions(self):
        return [_FIXED_SESSION]

    def test_cache_hit_skips_backend(self, tmp_path):
        from khipu.analyze import BackendConfig, analyze_sync

        backend_mock = MagicMock(return_value='[{"tool": "Bash"}]')
        backend_cfg = BackendConfig(id="t", mode="cli", context_limit=200_000, cli_input="stdin")

        cache_root = tmp_path / "cache"
        with (
            patch("khipu.analyze.call_backend", backend_mock),
            patch("khipu.analyze.load_backend", return_value=backend_cfg),
            patch("khipu.cache._cache_root", return_value=cache_root),
        ):
            # First run — populates cache
            analyze_sync(self._sessions(), analyzers=["workflows"], use_cache=True)
            assert backend_mock.call_count == 1

            # Second run — cache hit, no backend call
            analyze_sync(self._sessions(), analyzers=["workflows"], use_cache=True)
            assert backend_mock.call_count == 1  # still 1

    def test_no_cache_always_calls_backend(self, tmp_path):
        from khipu.analyze import BackendConfig, analyze_sync

        backend_mock = MagicMock(return_value='[{"tool": "Bash"}]')
        backend_cfg = BackendConfig(id="t", mode="cli", context_limit=200_000, cli_input="stdin")

        cache_root = tmp_path / "cache"
        with (
            patch("khipu.analyze.call_backend", backend_mock),
            patch("khipu.analyze.load_backend", return_value=backend_cfg),
            patch("khipu.cache._cache_root", return_value=cache_root),
        ):
            analyze_sync(self._sessions(), analyzers=["workflows"], use_cache=False)
            analyze_sync(self._sessions(), analyzers=["workflows"], use_cache=False)
            assert backend_mock.call_count == 2
