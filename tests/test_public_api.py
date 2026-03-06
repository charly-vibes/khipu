"""Tests for khipu public API exports."""
import inspect
import pytest
from khipu import ingest, analyze, analyze_sync, emit, __version__


def test_version_is_string():
    assert isinstance(__version__, str)


def test_ingest_is_callable():
    assert callable(ingest)


def test_analyze_sync_is_callable():
    assert callable(analyze_sync)


def test_emit_is_callable():
    assert callable(emit)


def test_analyze_is_async():
    assert inspect.iscoroutinefunction(analyze)
