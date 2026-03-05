"""Emit stage: render an AnalysisResult to markdown or JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from khipu.analyze import AnalysisResult

_jinja_env = Environment(
    loader=PackageLoader("khipu", "templates"),
    autoescape=select_autoescape([]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _result_to_dict(result: AnalysisResult) -> dict[str, Any]:
    d: dict[str, Any] = {
        "timestamp": result.timestamp.isoformat(),
        "session_count": result.session_count,
        "sessions_skipped": result.sessions_skipped,
        "workflows": result.workflows,
        "patterns": result.patterns,
        "crystallization": result.crystallization,
        "custom": result.custom,
        "metadata": asdict(result.metadata) if result.metadata else None,
    }
    return d


def emit(result: AnalysisResult, *, template: str = "markdown") -> str:
    """Render *result* using the named template.

    Parameters
    ----------
    result:
        The :class:`~khipu.analyze.AnalysisResult` to render.
    template:
        ``"markdown"`` (default) — human-readable Jinja2 report.
        ``"json"`` — machine-readable JSON; suitable for piping to ``jq``.

    Returns
    -------
    str
        Rendered output.
    """
    if template == "json":
        return json.dumps(_result_to_dict(result), indent=2)
    if template == "markdown":
        tmpl = _jinja_env.get_template("report.md")
        return tmpl.render(**_result_to_dict(result))
    raise ValueError(f"Unknown template '{template}'. Choose 'markdown' or 'json'.")
