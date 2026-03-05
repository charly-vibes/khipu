"""Tests for the khipu CLI."""

from typer.testing import CliRunner

from khipu import __version__
from khipu.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_analyze_stub():
    result = runner.invoke(app, ["analyze", "some/path"])
    assert result.exit_code == 0
    assert "some/path" in result.output
