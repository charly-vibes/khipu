"""Tests for the analysis engine."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from khipu.analyze import (
    AnalysisResult,
    BackendConfig,
    PromptSpec,
    ResultMetadata,
    analyze,
    call_backend,
    discover_prompts,
    extract_json,
    load_prompt,
    topo_sort,
)
from khipu.model import Exchange, Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session(content: str = "hello") -> Session:
    return Session(
        source="test",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        exchanges=[Exchange(role="human", content=content)],
    )


def _make_prompt(tmp_path: Path, aid: str, depends_on: list[str] | None = None) -> Path:
    deps = depends_on or []
    deps_str = f"[{', '.join(deps)}]"
    text = f"""---
id: {aid}
version: "1.0"
description: Test analyzer
depends_on: {deps_str}
---

Analyze this: {{sessions}}

Respond with JSON: []
"""
    p = tmp_path / f"{aid}.md"
    p.write_text(text)
    return p


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

class TestLoadPrompt:
    def test_parses_frontmatter(self, tmp_path):
        p = _make_prompt(tmp_path, "mytest", depends_on=[])
        spec = load_prompt(p)
        assert spec.id == "mytest"
        assert spec.version == "1.0"
        assert spec.depends_on == []

    def test_parses_depends_on_list(self, tmp_path):
        p = _make_prompt(tmp_path, "child", depends_on=["parent"])
        spec = load_prompt(p)
        assert spec.depends_on == ["parent"]

    def test_missing_frontmatter_raises(self, tmp_path):
        p = tmp_path / "bad.md"
        p.write_text("no frontmatter here")
        with pytest.raises(ValueError, match="missing YAML frontmatter"):
            load_prompt(p)

    def test_body_does_not_include_frontmatter(self, tmp_path):
        p = _make_prompt(tmp_path, "x")
        spec = load_prompt(p)
        assert "---" not in spec.body
        assert "Analyze this" in spec.body


class TestDiscoverPrompts:
    def test_builtin_prompts_available(self):
        prompts = discover_prompts(["workflows"])
        assert "workflows" in prompts

    def test_builtin_crystallize_includes_dep(self):
        prompts = discover_prompts(["crystallize"])
        assert "patterns" in prompts  # transitive dep

    def test_unknown_analyzer_raises(self):
        with pytest.raises(ValueError, match="Unknown analyzer"):
            discover_prompts(["nonexistent"])


# ---------------------------------------------------------------------------
# DAG / topo sort
# ---------------------------------------------------------------------------

class TestTopoSort:
    def _spec(self, aid: str, depends_on: list[str]) -> PromptSpec:
        return PromptSpec(id=aid, version="1.0", description="", depends_on=depends_on, body="")

    def test_independent_analyzers(self):
        prompts = {
            "a": self._spec("a", []),
            "b": self._spec("b", []),
        }
        order = topo_sort(prompts)
        assert set(order) == {"a", "b"}

    def test_dep_comes_before_dependent(self):
        prompts = {
            "parent": self._spec("parent", []),
            "child": self._spec("child", ["parent"]),
        }
        order = topo_sort(prompts)
        assert order.index("parent") < order.index("child")

    def test_cycle_raises(self):
        prompts = {
            "a": self._spec("a", ["b"]),
            "b": self._spec("b", ["a"]),
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            topo_sort(prompts)

    def test_missing_dep_raises(self):
        prompts = {
            "child": self._spec("child", ["missing_parent"]),
        }
        with pytest.raises(ValueError, match="missing_parent"):
            topo_sort(prompts)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_clean_array(self):
        assert extract_json('[{"a": 1}]') == [{"a": 1}]

    def test_strips_markdown_fences(self):
        text = '```json\n[{"x": 1}]\n```'
        assert extract_json(text) == [{"x": 1}]

    def test_strips_preamble(self):
        text = 'Here is the result:\n[{"a": 1}]'
        assert extract_json(text) == [{"a": 1}]

    def test_strips_postamble(self):
        text = '[{"a": 1}]\n\nHope that helps!'
        assert extract_json(text) == [{"a": 1}]

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            extract_json("no json here at all")

    def test_invalid_json_raises(self):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            extract_json("[not valid json")

    def test_multiple_json_blocks_returns_first(self):
        text = '[{"a": 1}] some text [{"b": 2}]'
        assert extract_json(text) == [{"a": 1}]


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class TestCallBackend:
    def _cli_backend(self, input_mode: str = "stdin") -> BackendConfig:
        return BackendConfig(
            id="test",
            mode="cli",
            context_limit=10000,
            cli_command="cat" if input_mode == "stdin" else "cat $prompt_file",
            cli_input=input_mode,
        )

    def test_cli_stdin_mode(self):
        backend = self._cli_backend("stdin")
        result = call_backend(backend, "hello prompt")
        assert "hello prompt" in result

    def test_cli_file_mode(self):
        backend = self._cli_backend("file")
        result = call_backend(backend, "file content")
        assert "file content" in result

    def test_unsupported_mode_raises(self):
        backend = BackendConfig(id="x", mode="api", context_limit=1000)
        with pytest.raises(ValueError, match="Unsupported backend mode"):
            call_backend(backend, "prompt")


# ---------------------------------------------------------------------------
# analyze() — integration (mocked backend)
# ---------------------------------------------------------------------------

_WORKFLOWS_JSON = '[{"name": "TDD", "goal": "test first", "steps": ["write test", "run"], "variants": [], "session_count": 2, "session_ids": [0, 1]}]'
_PATTERNS_JSON = '[{"type": "convention", "description": "always runs tests", "session_ids": [0], "confidence": 0.9}]'
_CRYSTALLIZE_JSON = '[{"pattern_index": 0, "convergence": 0.8, "stability": 0.9, "score": 0.85, "recommendation": "crystallize", "suggested_implementation": "Add to CLAUDE.md"}]'


class TestAnalyze:
    def _mock_backend(self, responses: dict[str, str]):
        """Return a call_backend mock that returns different JSON per analyzer."""
        call_count = {"n": 0}
        response_list = list(responses.values())

        def _fake_call(backend, prompt, model=None):
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(response_list):
                return response_list[idx]
            return "[]"

        return _fake_call

    def test_analyze_returns_result(self):
        sessions = [_session("hello")]
        with patch("khipu.analyze.call_backend") as mock_call, \
             patch("khipu.analyze.load_backend") as mock_lb:
            mock_lb.return_value = BackendConfig(
                id="test", mode="cli", context_limit=200_000, cli_input="stdin"
            )
            mock_call.side_effect = [_WORKFLOWS_JSON, _PATTERNS_JSON, _CRYSTALLIZE_JSON]
            result = analyze(sessions)

        assert isinstance(result, AnalysisResult)
        assert result.workflows is not None
        assert result.patterns is not None
        assert result.crystallization is not None

    def test_analyze_metadata(self):
        sessions = [_session()]
        with patch("khipu.analyze.call_backend") as mock_call, \
             patch("khipu.analyze.load_backend") as mock_lb:
            mock_lb.return_value = BackendConfig(
                id="test-backend", mode="cli", context_limit=200_000, cli_input="stdin"
            )
            mock_call.return_value = "[]"
            result = analyze(sessions, analyzers=["workflows"])

        assert result.metadata is not None
        assert result.metadata.backend == "test-backend"
        assert "workflows" in result.metadata.prompt_versions

    def test_analyze_session_count(self):
        sessions = [_session("a"), _session("b")]
        with patch("khipu.analyze.call_backend", return_value="[]"), \
             patch("khipu.analyze.load_backend") as mock_lb:
            mock_lb.return_value = BackendConfig(
                id="t", mode="cli", context_limit=200_000, cli_input="stdin"
            )
            result = analyze(sessions, analyzers=["workflows"])
        assert result.session_count == 2

    def test_analyze_invalid_json_retries(self):
        sessions = [_session()]
        call_count = {"n": 0}

        def _flaky(backend, prompt, model=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "not json"
            return "[]"

        with patch("khipu.analyze.call_backend", side_effect=_flaky), \
             patch("khipu.analyze.load_backend") as mock_lb:
            mock_lb.return_value = BackendConfig(
                id="t", mode="cli", context_limit=200_000, cli_input="stdin"
            )
            result = analyze(sessions, analyzers=["workflows"])
        assert call_count["n"] == 2  # original + retry
        assert result.workflows == []

    def test_analyze_custom_analyzer(self, tmp_path):
        custom_prompt = tmp_path / "custom.md"
        custom_prompt.write_text(
            "---\nid: custom\nversion: \"1.0\"\ndescription: custom\ndepends_on: []\n---\n{sessions}\n"
        )
        sessions = [_session()]
        with patch("khipu.analyze.call_backend", return_value='[{"x": 1}]'), \
             patch("khipu.analyze.load_backend") as mock_lb, \
             patch("khipu.analyze._USER_PROMPT_DIRS", [tmp_path]):
            mock_lb.return_value = BackendConfig(
                id="t", mode="cli", context_limit=200_000, cli_input="stdin"
            )
            result = analyze(sessions, analyzers=["custom"])
        assert result.custom is not None
        assert result.custom["custom"] == [{"x": 1}]

    def test_builtin_prompts_load(self):
        prompts = discover_prompts(["workflows", "patterns", "crystallize"])
        assert len(prompts) == 3
        for aid in ["workflows", "patterns", "crystallize"]:
            assert aid in prompts
            assert "{sessions}" in prompts[aid].body
