from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TextDelta:
    text: str


@dataclass(slots=True)
class ToolStarted:
    name: str
    arguments: dict


@dataclass(slots=True)
class ToolFinished:
    name: str
    result: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ContextCompacted:
    before_tokens: int
    after_tokens: int


@dataclass(slots=True)
class TurnEnded:
    text: str
    steps: int


type AgentEvent = TextDelta | ToolStarted | ToolFinished | ContextCompacted | TurnEnded
