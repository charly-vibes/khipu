"""Tests for khipu.redact."""

import sys
from datetime import datetime, timezone

import pytest

from khipu.model import Exchange, Outcome, Session, ToolCall
from khipu.redact import redact_sessions, redact_str


def _session(content: str) -> Session:
    return Session(
        source="test",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        exchanges=[Exchange(role="human", content=content)],
    )


class TestRedactStr:
    def test_api_key_sk(self):
        result = redact_str("my key is sk-abc123defghijklmnopqrstuvwxyz and done")
        assert "[REDACTED:api_key]" in result
        assert "sk-abc123" not in result

    def test_github_token(self):
        result = redact_str("token: ghp_" + "A" * 36)
        assert "[REDACTED:github_token]" in result

    def test_aws_access_key(self):
        result = redact_str("key AKIAIOSFODNN7EXAMPLE here")
        assert "[REDACTED:aws_access_key]" in result

    def test_bearer_token(self):
        result = redact_str("Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9abc")
        assert "[REDACTED:bearer_token]" in result

    def test_postgres_url(self):
        result = redact_str("db = postgres://user:pass@host:5432/mydb")
        assert "[REDACTED:postgres_url]" in result

    def test_mongodb_url(self):
        result = redact_str("conn = mongodb+srv://user:pass@cluster.mongodb.net/db")
        assert "[REDACTED:mongodb_url]" in result

    def test_redis_url(self):
        result = redact_str("cache = redis://localhost:6379/0")
        assert "[REDACTED:redis_url]" in result

    def test_mysql_url(self):
        result = redact_str("db = mysql://user:pass@host:3306/mydb")
        assert "[REDACTED:mysql_url]" in result

    def test_private_key_pem(self):
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
        result = redact_str(pem)
        assert "[REDACTED:private_key]" in result
        assert "MIIEowIBAAKCAQEA" not in result

    def test_env_secret_assignment(self):
        result = redact_str("API_KEY=supersecret123")
        assert "[REDACTED:env_secret]" in result

    def test_password_env(self):
        result = redact_str("PASSWORD=hunter2")
        assert "[REDACTED:env_secret]" in result

    def test_email(self):
        result = redact_str("contact me at user@example.com please")
        assert "[REDACTED:email]" in result
        assert "user@example.com" not in result

    def test_public_ip(self):
        result = redact_str("server at 203.0.113.42")
        assert "[REDACTED:ip_address]" in result

    def test_loopback_not_redacted(self):
        result = redact_str("listening on 127.0.0.1:8080")
        assert "[REDACTED:ip_address]" not in result

    def test_private_ip_not_redacted(self):
        result = redact_str("host 192.168.1.10")
        assert "[REDACTED:ip_address]" not in result

    def test_clean_text_unchanged(self):
        text = "just some normal text with no secrets"
        assert redact_str(text) == text


class TestRedactSessions:
    def test_redacts_exchange_content(self):
        sessions = [_session("my key sk-" + "x" * 30)]
        result = redact_sessions(sessions)
        assert "[REDACTED:api_key]" in result[0].exchanges[0].content

    def test_redacts_tool_call_input_output(self):
        tc = ToolCall(
            tool="Bash",
            input={"cmd": "export API_KEY=hunter2"},
            output="secret postgres://user:pass@db/prod returned",
            success=True,
        )
        sessions = [
            Session(
                source="test",
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                exchanges=[Exchange(role="agent", content="ok", tool_calls=[tc])],
            )
        ]
        result = redact_sessions(sessions)
        tc_out = result[0].exchanges[0].tool_calls[0]
        assert "[REDACTED:env_secret]" in tc_out.input["cmd"]
        assert "[REDACTED:postgres_url]" in tc_out.output

    def test_disabled_returns_unchanged_with_warning(self, capsys):
        sessions = [_session("sk-" + "a" * 30)]
        result = redact_sessions(sessions, enabled=False)
        assert result is sessions
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "redaction is disabled" in captured.err

    def test_enabled_by_default(self):
        sessions = [_session("sk-" + "a" * 30)]
        result = redact_sessions(sessions)
        assert "sk-" not in result[0].exchanges[0].content

    def test_returns_new_session_objects(self):
        sessions = [_session("clean text")]
        result = redact_sessions(sessions)
        assert result[0] is not sessions[0]
