"""Core trace data model for khipu."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ToolCall:
    tool: str
    input: Any
    output: Any
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        return cls(
            tool=data["tool"],
            input=data["input"],
            output=data["output"],
            success=data["success"],
        )


@dataclass
class Exchange:
    role: str  # "human" | "agent" | "system" | "tool"
    content: str
    tool_calls: list[ToolCall] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls] if self.tool_calls else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Exchange:
        tool_calls = None
        if data.get("tool_calls"):
            tool_calls = [ToolCall.from_dict(tc) for tc in data["tool_calls"]]
        return cls(
            role=data["role"],
            content=data["content"],
            tool_calls=tool_calls,
        )


@dataclass
class Outcome:
    success: bool
    artifacts_produced: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Outcome:
        return cls(
            success=data["success"],
            artifacts_produced=data.get("artifacts_produced", []),
            errors=data.get("errors", []),
        )


@dataclass
class Session:
    source: str  # "claude-code" | "cursor" | "aider" | ...
    timestamp: datetime
    exchanges: list[Exchange]
    outcome: Outcome | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "exchanges": [e.to_dict() for e in self.exchanges],
            "outcome": self.outcome.to_dict() if self.outcome else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        ts = data["timestamp"]
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = ts
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        return cls(
            source=data["source"],
            timestamp=timestamp,
            exchanges=[Exchange.from_dict(e) for e in data["exchanges"]],
            outcome=Outcome.from_dict(data["outcome"]) if data.get("outcome") else None,
        )
