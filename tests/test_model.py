"""Tests for khipu.model dataclasses."""

from datetime import datetime, timezone

import pytest

from khipu.model import Exchange, Outcome, Session, ToolCall


def make_session(**kwargs) -> Session:
    defaults = dict(
        source="claude-code",
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        exchanges=[Exchange(role="human", content="hello")],
    )
    defaults.update(kwargs)
    return Session(**defaults)


class TestToolCall:
    def test_roundtrip(self):
        tc = ToolCall(tool="Bash", input={"cmd": "ls"}, output="file.txt", success=True)
        assert ToolCall.from_dict(tc.to_dict()) == tc

    def test_failed_tool_call(self):
        tc = ToolCall(tool="Read", input="/missing", output=None, success=False)
        assert not tc.success
        assert ToolCall.from_dict(tc.to_dict()) == tc


class TestExchange:
    def test_roundtrip_no_tool_calls(self):
        ex = Exchange(role="human", content="what files exist?")
        assert Exchange.from_dict(ex.to_dict()) == ex

    def test_roundtrip_with_tool_calls(self):
        tc = ToolCall(tool="Bash", input="ls", output="a.py\nb.py", success=True)
        ex = Exchange(role="agent", content="Let me check.", tool_calls=[tc])
        restored = Exchange.from_dict(ex.to_dict())
        assert restored == ex
        assert restored.tool_calls[0].tool == "Bash"

    def test_null_tool_calls_roundtrip(self):
        ex = Exchange(role="system", content="You are helpful.", tool_calls=None)
        d = ex.to_dict()
        assert d["tool_calls"] is None
        assert Exchange.from_dict(d).tool_calls is None


class TestOutcome:
    def test_roundtrip(self):
        o = Outcome(success=True, artifacts_produced=["out.txt"], errors=[])
        assert Outcome.from_dict(o.to_dict()) == o

    def test_defaults(self):
        o = Outcome.from_dict({"success": False})
        assert o.artifacts_produced == []
        assert o.errors == []


class TestSession:
    def test_roundtrip_minimal(self):
        s = make_session()
        assert Session.from_dict(s.to_dict()) == s

    def test_roundtrip_with_outcome(self):
        s = make_session(
            outcome=Outcome(success=True, artifacts_produced=["x.py"], errors=[])
        )
        assert Session.from_dict(s.to_dict()) == s

    def test_timestamp_isoformat(self):
        s = make_session()
        d = s.to_dict()
        assert isinstance(d["timestamp"], str)
        assert "2026" in d["timestamp"]

    def test_naive_timestamp_gets_utc(self):
        naive_ts = datetime(2026, 1, 1, 12, 0)
        s = Session(source="aider", timestamp=naive_ts, exchanges=[])
        d = s.to_dict()
        restored = Session.from_dict(d)
        assert restored.timestamp.tzinfo is not None

    def test_no_outcome(self):
        s = make_session()
        assert s.outcome is None
        d = s.to_dict()
        assert d["outcome"] is None
        assert Session.from_dict(d).outcome is None
