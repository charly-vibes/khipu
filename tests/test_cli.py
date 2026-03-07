"""Tests for the khipu CLI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from khipu import __version__
from khipu.analyze import AnalysisResult, ResultMetadata
from khipu.cli import app
from khipu.model import Exchange, Session

runner = CliRunner()


def _session() -> Session:
    return Session(
        source="test",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        exchanges=[Exchange(role="human", content="do a thing")],
    )


def _result() -> AnalysisResult:
    return AnalysisResult(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        session_count=1,
        sessions_skipped=0,
        workflows=[{
            "name": "TDD", "goal": "test first", "steps": [],
            "variants": [], "session_count": 1, "session_ids": [],
        }],
        patterns=[],
        crystallization=[],
        metadata=ResultMetadata(
            backend="test",
            model="claude-sonnet-4-5",
            condensation_mode="auto",
            prompt_versions={},
            duration_ms=100,
        ),
    )


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


class TestAnalyzeCommand:
    def test_missing_path_shows_help(self):
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code != 0

    def test_markdown_output_default(self, tmp_path: Path):
        sessions = [_session()]
        analysis = _result()
        with patch("khipu.cli.ingest", return_value=sessions), \
             patch("khipu.cli.analyze_sessions", return_value=analysis):
            result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 0
        assert "TDD" in result.output

    def test_json_output(self, tmp_path: Path):
        sessions = [_session()]
        analysis = _result()
        with patch("khipu.cli.ingest", return_value=sessions), \
             patch("khipu.cli.analyze_sessions", return_value=analysis):
            result = runner.invoke(app, ["analyze", str(tmp_path), "--emit", "json"])
        assert result.exit_code == 0
        # Progress lines go to stderr but CliRunner mixes them; find the JSON block
        json_start = result.output.find("{")
        assert json_start != -1, f"No JSON in output: {result.output!r}"
        parsed = json.loads(result.output[json_start:])
        assert "session_count" in parsed

    def test_no_sessions_exits_nonzero(self, tmp_path: Path):
        with patch("khipu.cli.ingest", return_value=[]):
            result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code != 0

    def test_ingestor_flag_passed_through(self, tmp_path: Path):
        sessions = [_session()]
        analysis = _result()
        with patch("khipu.cli.ingest", return_value=sessions) as mock_ingest, \
             patch("khipu.cli.analyze_sessions", return_value=analysis):
            runner.invoke(app, ["analyze", str(tmp_path), "--ingestor", "claude_code"])
            mock_ingest.assert_called_once()
            _, kwargs = mock_ingest.call_args
            assert kwargs.get("ingestor") == "claude_code"

    def test_no_redact_flag(self, tmp_path: Path):
        sessions = [_session()]
        analysis = _result()
        with patch("khipu.cli.ingest", return_value=sessions), \
             patch("khipu.cli.analyze_sessions", return_value=analysis) as mock_analyze:
            runner.invoke(app, ["analyze", str(tmp_path), "--no-redact"])
            _, kwargs = mock_analyze.call_args
            assert kwargs.get("redact") is False

    def test_unknown_emit_exits_nonzero(self, tmp_path: Path):
        sessions = [_session()]
        with patch("khipu.cli.ingest", return_value=sessions), \
             patch("khipu.cli.analyze_sessions", return_value=_result()):
            result = runner.invoke(app, ["analyze", str(tmp_path), "--emit", "xml"])
        assert result.exit_code != 0

    def test_ingest_error_exits_nonzero(self, tmp_path: Path):
        with patch("khipu.cli.ingest", side_effect=ValueError("no ingestor")):
            result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code != 0

    def test_multi_path_ingests_all(self, tmp_path: Path):
        dir1 = tmp_path / "a"
        dir2 = tmp_path / "b"
        dir1.mkdir()
        dir2.mkdir()
        sessions = [_session()]
        analysis = _result()
        with patch("khipu.cli.ingest", return_value=sessions) as mock_ingest, \
             patch("khipu.cli.analyze_sessions", return_value=analysis):
            result = runner.invoke(app, ["analyze", str(dir1), str(dir2)])
        assert result.exit_code == 0
        assert mock_ingest.call_count == 2

    def test_only_flag_filters_analyzers(self, tmp_path: Path):
        sessions = [_session()]
        analysis = _result()
        with patch("khipu.cli.ingest", return_value=sessions), \
             patch("khipu.cli.analyze_sessions", return_value=analysis) as mock_analyze:
            result = runner.invoke(app, ["analyze", str(tmp_path), "--only", "workflows"])
        assert result.exit_code == 0
        _, kwargs = mock_analyze.call_args
        assert kwargs.get("analyzers") == ["workflows"]
