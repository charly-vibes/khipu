"""Built-in ingestor for Claude Code JSONL session logs."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from khipu.model import Exchange, Session, ToolCall

_LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50 MB

EXTENSIONS = [".jsonl"]
CONTENT_PATTERN = r'"type"\s*:\s*"(tool_use|tool_result)"'
PRIORITY = 10


def can_handle(path: Path) -> bool:
    if path.suffix != ".jsonl":
        return False
    try:
        first_line = path.open().readline()
        return '"tool_use"' in first_line or '"tool_result"' in first_line
    except OSError:
        return False


def ingest(path: Path) -> list[Session]:
    stat = path.stat()
    if stat.st_size > _LARGE_FILE_THRESHOLD:
        mb = stat.st_size / (1024 * 1024)
        print(
            f"WARNING: {path.name} is large ({mb:.0f} MB > 50 MB); ingestion may be slow",
            file=sys.stderr,
        )

    exchanges: list[Exchange] = []
    # Pair up tool_use with subsequent tool_result by tool_use_id
    pending: dict[str, ToolCall] = {}

    for raw in path.open():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue

        msg_type = entry.get("type", "")
        role = entry.get("role", "")

        if msg_type == "message" or role in ("user", "assistant"):
            # Standard message
            content_field = entry.get("content", "")
            tool_calls: list[ToolCall] | None = None

            if isinstance(content_field, list):
                # Content blocks
                text_parts: list[str] = []
                tcs: list[ToolCall] = []
                for block in content_field:
                    btype = block.get("type", "")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        tc = ToolCall(
                            tool=block.get("name", ""),
                            input=block.get("input"),
                            output=None,
                            success=True,
                        )
                        pending[block.get("id", "")] = tc
                        tcs.append(tc)
                    elif btype == "tool_result":
                        tc_id = block.get("tool_use_id", "")
                        output = block.get("content", "")
                        if isinstance(output, list):
                            output = " ".join(
                                b.get("text", "") for b in output if b.get("type") == "text"
                            )
                        is_error = block.get("is_error", False)
                        if tc_id in pending:
                            orig = pending.pop(tc_id)
                            tcs.append(ToolCall(
                                tool=orig.tool,
                                input=orig.input,
                                output=output,
                                success=not is_error,
                            ))
                        else:
                            tcs.append(ToolCall(
                                tool="unknown",
                                input=None,
                                output=output,
                                success=not is_error,
                            ))
                content_str = " ".join(text_parts)
                tool_calls = tcs or None
            else:
                content_str = str(content_field)

            msg_role = "human" if role == "user" else "agent"
            exchanges.append(Exchange(role=msg_role, content=content_str, tool_calls=tool_calls))

        elif msg_type == "tool_use":
            # Top-level tool_use (older format)
            tc = ToolCall(
                tool=entry.get("name", entry.get("tool", "")),
                input=entry.get("input"),
                output=None,
                success=True,
            )
            pending[entry.get("id", "")] = tc
            exchanges.append(Exchange(role="agent", content="", tool_calls=[tc]))

        elif msg_type == "tool_result":
            # Top-level tool_result (older format)
            tc_id = entry.get("tool_use_id", "")
            output = entry.get("content", entry.get("output", ""))
            is_error = entry.get("is_error", False)
            if tc_id in pending:
                orig = pending.pop(tc_id)
                tc = ToolCall(tool=orig.tool, input=orig.input, output=output, success=not is_error)
            else:
                tc = ToolCall(tool="unknown", input=None, output=output, success=not is_error)
            exchanges.append(Exchange(role="tool", content="", tool_calls=[tc]))

    timestamp = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    return [Session(source="claude-code", timestamp=timestamp, exchanges=exchanges)]
