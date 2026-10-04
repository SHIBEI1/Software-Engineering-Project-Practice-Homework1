"""Domain models used by the agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ChatMessage:
    """One remembered conversation turn."""

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ToolResult:
    """A structured result returned by a local tool."""

    name: str
    ok: bool
    content: str


@dataclass
class AgentResponse:
    """Visible answer plus execution trace suitable for a demo."""

    answer: str
    steps: list[str] = field(default_factory=list)
