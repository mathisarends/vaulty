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
class TurnEnded:
    text: str
    steps: int
    stopped_early: bool = False


type AgentEvent = TextDelta | ToolStarted | ToolFinished | TurnEnded
