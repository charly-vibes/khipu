"""Tests for the ingestor engine and built-in ingestors."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from khipu.ingest import ingest
from khipu.ingestors import claude_code, generic


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def _jsonl_session(exchanges: list[dict]) -> str:
    return "\n".join(json.dumps(e) for e in exchanges) + "\n"


# ---------------------------------------------------------------------------
# claude_code ingestor
# ---------------------------------------------------------------------------

class TestClaudeCodeIngestor:
    def test_can_handle_valid_jsonl(self, tmp_path):
        f = _write(tmp_path, "trace.jsonl", json.dumps({"type": "tool_use"}) + "\n")
        assert claude_code.can_handle(f)

    def test_cannot_handle_no_tool_use(self, tmp_path):
        f = _write(tmp_path, "trace.jsonl", json.dumps({"type": "message"}) + "\n")
        assert not claude_code.can_handle(f)

    def test_cannot_handle_wrong_extension(self, tmp_path):
        f = _write(tmp_path, "trace.txt", json.dumps({"type": "tool_use"}) + "\n")
        assert not claude_code.can_handle(f)

    def test_ingest_content_blocks(self, tmp_path):
        lines = [
            {"role": "user", "type": "message", "content": [{"type": "text", "text": "hello"}]},
            {
                "role": "assistant",
                "type": "message",
                "content": [
                    {"type": "text", "text": "let me check"},
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"cmd": "ls"}},
                ],
            },
            {
                "role": "user",
                "type": "message",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "file.py", "is_error": False}
                ],
            },
        ]
        f = _write(tmp_path, "trace.jsonl", _jsonl_session(lines))
        sessions = claude_code.ingest(f)
        assert len(sessions) == 1
        s = sessions[0]
        assert s.source == "claude-code"
        # human exchange
        assert s.exchanges[0].role == "human"
        assert s.exchanges[0].content == "hello"
        # agent exchange with tool_use
        agent_ex = s.exchanges[1]
        assert agent_ex.role == "agent"
        assert agent_ex.tool_calls is not None
        assert agent_ex.tool_calls[0].tool == "Bash"
        # tool_result exchange
        result_ex = s.exchanges[2]
        assert result_ex.tool_calls[0].output == "file.py"
        assert result_ex.tool_calls[0].success is True

    def test_ingest_toplevel_tool_use_result(self, tmp_path):
        lines = [
            {"type": "tool_use", "id": "x1", "name": "Read", "input": {"path": "/foo"}},
            {"type": "tool_result", "tool_use_id": "x1", "content": "content", "is_error": False},
        ]
        f = _write(tmp_path, "trace.jsonl", _jsonl_session(lines))
        sessions = claude_code.ingest(f)
        assert sessions[0].exchanges[0].tool_calls[0].tool == "Read"
        assert sessions[0].exchanges[1].tool_calls[0].output == "content"

    def test_ingest_skips_invalid_json(self, tmp_path):
        content = 'not-json\n' + json.dumps({"role": "user", "type": "message", "content": "hi"}) + "\n"
        f = _write(tmp_path, "trace.jsonl", content)
        sessions = claude_code.ingest(f)
        assert len(sessions) == 1


# ---------------------------------------------------------------------------
# generic ingestor
# ---------------------------------------------------------------------------

class TestGenericIngestor:
    def test_can_handle_md_with_role_markers(self, tmp_path):
        f = _write(tmp_path, "chat.md", "Human: hello\nAssistant: hi\n")
        assert generic.can_handle(f)

    def test_cannot_handle_md_without_markers(self, tmp_path):
        f = _write(tmp_path, "notes.md", "# Just some notes\nno roles here\n")
        assert not generic.can_handle(f)

    def test_cannot_handle_wrong_extension(self, tmp_path):
        f = _write(tmp_path, "trace.jsonl", "Human: hello\n")
        assert not generic.can_handle(f)

    def test_ingest_basic_conversation(self, tmp_path):
        text = textwrap.dedent("""\
            Human: what time is it?
            Assistant: I don't know the time.
            User: thanks
            AI: you're welcome
        """)
        f = _write(tmp_path, "chat.md", text)
        sessions = generic.ingest(f)
        assert len(sessions) == 1
        exchanges = sessions[0].exchanges
        assert exchanges[0].role == "human"
        assert exchanges[0].content == "what time is it?"
        assert exchanges[1].role == "agent"
        assert exchanges[2].role == "human"
        assert exchanges[3].role == "agent"

    def test_ingest_source_is_generic(self, tmp_path):
        f = _write(tmp_path, "chat.txt", "Human: hi\nAssistant: hello\n")
        sessions = generic.ingest(f)
        assert sessions[0].source == "generic"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TestIngestEngine:
    def test_auto_detect_claude_code(self, tmp_path):
        lines = [{"type": "tool_use", "id": "a", "name": "Bash", "input": {}}]
        f = _write(tmp_path, "session.jsonl", _jsonl_session(lines))
        sessions = ingest(f)
        assert sessions[0].source == "claude-code"

    def test_auto_detect_generic_md(self, tmp_path):
        f = _write(tmp_path, "chat.md", "Human: hello\nAssistant: hi\n")
        sessions = ingest(f)
        assert sessions[0].source == "generic"

    def test_force_ingestor(self, tmp_path):
        f = _write(tmp_path, "chat.md", "Human: hi\nAssistant: hello\n")
        sessions = ingest(f, ingestor="generic")
        assert sessions[0].source == "generic"

    def test_unknown_ingestor_raises(self, tmp_path):
        f = _write(tmp_path, "f.jsonl", "{}\n")
        with pytest.raises(ValueError, match="Unknown ingestor"):
            ingest(f, ingestor="nonexistent")

    def test_no_ingestor_found_raises(self, tmp_path):
        f = _write(tmp_path, "file.xyz", "binary stuff")
        with pytest.raises(ValueError, match="No ingestor found"):
            ingest(f)

    def test_directory_recursion(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        _write(tmp_path, "a.md", "Human: hi\nAssistant: hello\n")
        _write(sub, "b.md", "User: hey\nClaude: sup\n")
        sessions = ingest(tmp_path)
        assert len(sessions) == 2

    def test_hidden_directories_skipped(self, tmp_path):
        hidden = tmp_path / ".git"
        hidden.mkdir()
        _write(hidden, "chat.md", "Human: hi\nAssistant: hello\n")
        _write(tmp_path, "real.md", "Human: hey\nAssistant: sup\n")
        sessions = ingest(tmp_path)
        assert len(sessions) == 1

    def test_stdin_without_ingestor_raises(self, monkeypatch):
        import io
        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"")))
        with pytest.raises(ValueError, match="Stdin input requires --ingestor"):
            ingest("-")

    def test_stdin_as_path_object_without_ingestor_raises(self, monkeypatch):
        import io
        from pathlib import Path
        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"")))
        with pytest.raises(ValueError, match="Stdin input requires --ingestor"):
            ingest(Path("-"))

    def test_stdin_unknown_ingestor_raises(self, monkeypatch):
        import io
        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"")))
        with pytest.raises(ValueError, match="Unknown ingestor"):
            ingest("-", ingestor="bogus")

    def test_safe_mode_uses_only_builtins(self, tmp_path):
        # Create a drop-in ingestor in .khipu/ingestors
        drop_in_dir = tmp_path / ".khipu" / "ingestors"
        drop_in_dir.mkdir(parents=True)
        (drop_in_dir / "custom.py").write_text(
            "EXTENSIONS=['.xyz']\nPRIORITY=999\n"
            "def can_handle(p): return True\n"
            "def ingest(p): from khipu.model import Session,Exchange; "
            "from datetime import datetime,timezone; "
            "return [Session('custom',datetime.now(timezone.utc),[Exchange('human','x')])]\n"
        )
        f = tmp_path / "trace.xyz"
        f.write_text("data")
        # With safe=True, custom ingestor is ignored → no ingestor found
        with pytest.raises(ValueError, match="No ingestor found"):
            ingest(f, safe=True)
