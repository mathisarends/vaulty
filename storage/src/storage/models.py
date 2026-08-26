from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UserMessage:
    role: Literal["user"] = "user"
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantMessage:
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallMessage:
    role: Literal["tool"] = "tool"
    tool_call_id: str
    content: str
    created_at: datetime


type ChatMessage = UserMessage | AssistantMessage | ToolCallMessage


class SessionTrigger(StrEnum):
    CRON = "cron"
    CLI = "cli"


class SessionStatus(StrEnum):
    """Whether an agent currently owns this session.

    A `RUNNING` session is being written by a live agent, so a second
    frontend must not resume it - both would append to the same history.
    """

    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Session:
    id: UUID
    created_at: datetime
    trigger: SessionTrigger
    status: SessionStatus = SessionStatus.RUNNING
    title: str | None = None
    messages: tuple[ChatMessage, ...] = ()

    def append(self, message: ChatMessage) -> Self:
        return replace(self, messages=(*self.messages, message))

    def with_status(self, status: SessionStatus) -> Self:
        return replace(self, status=status)

    def with_title(self, title: str) -> Self:
        return replace(self, title=title)
