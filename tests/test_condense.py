"""Tests for khipu.condense."""

import json
import pytest
from datetime import datetime, timezone

from khipu.model import Exchange, Session, ToolCall
from khipu.condense import condense_session, condense_sessions, _token_estimate


def _session(content: str = "hello", *, source: str = "test") -> Session:
    return Session(
        source=source,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        exchanges=[Exchange(role="human", content=content)],
    )


def _fat_session(human: str = "h" * 200, agent: str = "a" * 200) -> Session:
    return Session(
        source="test",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        exchanges=[
            Exchange(role="human", content=human),
            Exchange(role="agent", content=agent),
        ],
    )


class TestTokenEstimate:
    def test_returns_positive_int(self):
        assert _token_estimate([_session("hello")]) > 0

    def test_more_accurate_than_chars_over_4(self):
        # Claude tokenizer averages ~3.5 chars/token; estimate should exceed chars//4
        s = _session("word " * 200)
        text = json.dumps([s.to_dict()])
        assert _token_estimate([s]) > len(text) // 4


class TestCondenseSession:
    def test_human_truncated_at_100(self):
        s = condense_session(_fat_session(human="h" * 200))
        assert len(s.exchanges[0].content) <= 101  # 100 + "…"
        assert s.exchanges[0].content.endswith("…")

    def test_agent_truncated_at_80(self):
        s = condense_session(_fat_session(agent="a" * 200))
        assert len(s.exchanges[1].content) <= 81
        assert s.exchanges[1].content.endswith("…")

    def test_short_content_not_truncated(self):
        s = condense_session(_session("hi"))
        assert s.exchanges[0].content == "hi"

    def test_tool_call_output_condensed(self):
        tc = ToolCall(tool="Read", input={"path": "/foo.py"}, output="x" * 1000, success=True)
        session = Session(
            source="test",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            exchanges=[Exchange(role="agent", content="ok", tool_calls=[tc])],
        )
        result = condense_session(session)
        tc_out = result.exchanges[0].tool_calls[0]
        assert tc_out.output == "<condensed>"
        assert tc_out.input == {"path": "/foo.py"}  # path preserved
        assert tc_out.tool == "Read"
        assert tc_out.success is True

    def test_tool_call_non_path_input_condensed(self):
        tc = ToolCall(tool="Bash", input={"cmd": "echo hi"}, output="hi", success=True)
        session = Session(
            source="test",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            exchanges=[Exchange(role="agent", content="ok", tool_calls=[tc])],
        )
        result = condense_session(session)
        tc_out = result.exchanges[0].tool_calls[0]
        assert tc_out.input == "<condensed>"


class TestCondenseSessions:
    def test_auto_no_condense_when_small(self):
        sessions = [_session("short")]
        result = condense_sessions(sessions, mode="auto", context_limit=200_000)
        assert result[0].exchanges[0].content == "short"

    def test_auto_condenses_when_large(self):
        # Create enough sessions to exceed 70% of a tiny context limit
        sessions = [_fat_session("h" * 200, "a" * 200) for _ in range(5)]
        result = condense_sessions(sessions, mode="auto", context_limit=100)
        # Content should be truncated
        assert any(ex.content.endswith("…") for s in result for ex in s.exchanges)

    def test_always_condenses(self):
        sessions = [_fat_session()]
        result = condense_sessions(sessions, mode="always")
        assert result[0].exchanges[0].content.endswith("…")

    def test_never_passes_when_small(self):
        sessions = [_session("hi")]
        result = condense_sessions(sessions, mode="never", context_limit=200_000)
        assert result[0].exchanges[0].content == "hi"

    def test_never_errors_when_too_large(self):
        sessions = [_fat_session("x" * 500, "y" * 500) for _ in range(10)]
        with pytest.raises(ValueError, match="context limit"):
            condense_sessions(sessions, mode="never", context_limit=10)

    def test_max_sessions_cap(self):
        sessions = [_session(f"msg{i}") for i in range(10)]
        result = condense_sessions(sessions, mode="never", max_sessions=3)
        assert len(result) == 3
        # most recent 3
        assert result[0].exchanges[0].content == "msg7"

    def test_overflow_trims_oldest_with_warning(self, capsys):
        # Build sessions large enough that even condensed they overflow a tiny limit
        sessions = [_fat_session("h" * 500, "a" * 500) for _ in range(10)]
        result = condense_sessions(sessions, mode="always", context_limit=50)
        assert len(result) < 10
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "skipped" in captured.err
