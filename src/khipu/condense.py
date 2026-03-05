"""Condensation: deterministic session compression (no LLM)."""

from __future__ import annotations

import json
import sys
from dataclasses import replace

from khipu.model import Exchange, Session, ToolCall

_HUMAN_PREVIEW = 100
_AGENT_PREVIEW = 80


def _condense_tool_call(tc: ToolCall) -> ToolCall:
    """Keep tool name/success; drop full I/O bodies, preserve file paths."""
    input_summary: object
    if isinstance(tc.input, dict):
        input_summary = {k: v for k, v in tc.input.items() if k in ("path", "file_path", "command", "pattern")}
        if not input_summary:
            input_summary = "<condensed>"
    elif isinstance(tc.input, str) and len(tc.input) > 60:
        input_summary = tc.input[:60] + "…"
    else:
        input_summary = tc.input

    return ToolCall(
        tool=tc.tool,
        input=input_summary,
        output="<condensed>",
        success=tc.success,
    )


def _condense_exchange(ex: Exchange) -> Exchange:
    if ex.role == "human":
        content = ex.content[:_HUMAN_PREVIEW] + ("…" if len(ex.content) > _HUMAN_PREVIEW else "")
    elif ex.role == "agent":
        content = ex.content[:_AGENT_PREVIEW] + ("…" if len(ex.content) > _AGENT_PREVIEW else "")
    else:
        content = ex.content  # system/tool: keep as-is

    tool_calls = None
    if ex.tool_calls:
        tool_calls = [_condense_tool_call(tc) for tc in ex.tool_calls]

    return Exchange(role=ex.role, content=content, tool_calls=tool_calls)


def condense_session(session: Session) -> Session:
    """Return a condensed copy of *session* with truncated content."""
    return replace(session, exchanges=[_condense_exchange(ex) for ex in session.exchanges])


def _token_estimate(sessions: list[Session]) -> int:
    """Rough token estimate: len(json_text) / 4."""
    text = json.dumps([s.to_dict() for s in sessions])
    return len(text) // 4


def condense_sessions(
    sessions: list[Session],
    *,
    mode: str = "auto",
    context_limit: int = 200_000,
    max_sessions: int | None = None,
) -> list[Session]:
    """Apply condensation according to *mode*.

    mode:
      "auto"   — condense if token estimate exceeds 70% of context_limit
      "always" — always condense
      "never"  — never condense; error if sessions exceed context_limit

    After condensation (or not), trim to the most recent sessions that fit
    within context_limit, warning on stderr if any are skipped.
    Raises ValueError if mode is "never" and sessions exceed context_limit.
    """
    if max_sessions is not None:
        sessions = sessions[-max_sessions:]

    threshold = int(context_limit * 0.70)
    tokens = _token_estimate(sessions)

    if mode == "never":
        if tokens > context_limit:
            raise ValueError(
                f"Sessions exceed context limit ({tokens} estimated tokens > {context_limit}). "
                "Remove --no-condense or reduce the number of sessions."
            )
        return sessions

    if mode == "always" or (mode == "auto" and tokens > threshold):
        sessions = [condense_session(s) for s in sessions]

    # Overflow: trim to most recent sessions that fit
    if _token_estimate(sessions) > context_limit:
        original_count = len(sessions)
        while len(sessions) > 1 and _token_estimate(sessions) > context_limit:
            sessions = sessions[1:]
        skipped = original_count - len(sessions)
        print(
            f"WARNING: {skipped} session(s) skipped — exceeded context limit after condensation.",
            file=sys.stderr,
        )

    return sessions
