"""Tests for the emit stage."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from khipu.analyze import AnalysisResult, ResultMetadata
from khipu.emit import emit


def _result(
    workflows=None,
    patterns=None,
    crystallization=None,
    custom=None,
) -> AnalysisResult:
    return AnalysisResult(
        timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        session_count=3,
        sessions_skipped=1,
        workflows=workflows,
        patterns=patterns,
        crystallization=crystallization,
        custom=custom,
        metadata=ResultMetadata(
            backend="claude_cli",
            model="claude-sonnet-4-5",
            condensation_mode="auto",
            prompt_versions={"workflows": "1.0", "patterns": "1.0", "crystallize": "1.0"},
            duration_ms=4200,
        ),
    )


class TestEmitJson:
    def test_returns_valid_json(self):
        result = _result(workflows=[{"name": "TDD"}])
        output = emit(result, template="json")
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_session_count_present(self):
        result = _result()
        parsed = json.loads(emit(result, template="json"))
        assert parsed["session_count"] == 3

    def test_sessions_skipped_present(self):
        result = _result()
        parsed = json.loads(emit(result, template="json"))
        assert parsed["sessions_skipped"] == 1

    def test_timestamp_present(self):
        result = _result()
        parsed = json.loads(emit(result, template="json"))
        assert "timestamp" in parsed

    def test_workflows_serialized(self):
        result = _result(workflows=[{"name": "TDD", "goal": "test first"}])
        parsed = json.loads(emit(result, template="json"))
        assert parsed["workflows"] == [{"name": "TDD", "goal": "test first"}]

    def test_none_fields_included(self):
        result = _result()
        parsed = json.loads(emit(result, template="json"))
        assert "workflows" in parsed

    def test_metadata_serialized(self):
        result = _result()
        parsed = json.loads(emit(result, template="json"))
        assert parsed["metadata"]["backend"] == "claude_cli"
        assert parsed["metadata"]["duration_ms"] == 4200


class TestEmitMarkdown:
    def test_returns_string(self):
        result = _result()
        output = emit(result, template="markdown")
        assert isinstance(output, str)

    def test_contains_session_count(self):
        result = _result()
        output = emit(result, template="markdown")
        assert "3" in output

    def test_contains_workflows_section(self):
        result = _result(workflows=[{"name": "TDD", "goal": "test first", "steps": [], "variants": [], "session_count": 2, "session_ids": []}])
        output = emit(result, template="markdown")
        assert "TDD" in output

    def test_contains_patterns_section(self):
        result = _result(patterns=[{"type": "convention", "description": "runs tests", "session_ids": [], "confidence": 0.9}])
        output = emit(result, template="markdown")
        assert "runs tests" in output

    def test_contains_crystallization_section(self):
        result = _result(crystallization=[{"pattern_index": 0, "score": 0.85, "recommendation": "crystallize", "suggested_implementation": "Add to CLAUDE.md", "convergence": 0.8, "stability": 0.9}])
        output = emit(result, template="markdown")
        assert "crystallize" in output.lower() or "0.85" in output

    def test_no_workflows_graceful(self):
        result = _result(workflows=None)
        output = emit(result, template="markdown")
        assert isinstance(output, str)

    def test_default_template_is_markdown(self):
        result = _result()
        assert emit(result) == emit(result, template="markdown")


class TestEmitInvalidTemplate:
    def test_unknown_template_raises(self):
        result = _result()
        with pytest.raises(ValueError, match="Unknown template"):
            emit(result, template="xml")
