from dataclasses import dataclass


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


@dataclass(slots=True)
class ContextCompacted:
    before_tokens: int
    after_tokens: int


@dataclass(slots=True)
class TurnEnded:
    text: str
    steps: int


type AgentEvent = TextDelta | ToolStarted | ToolFinished | ContextCompacted | TurnEnded
