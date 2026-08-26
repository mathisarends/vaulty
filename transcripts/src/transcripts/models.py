from dataclasses import dataclass, replace
from datetime import datetime
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


@dataclass(frozen=True, slots=True)
class Transcript:
    id: UUID
    created_at: datetime
    title: str | None = None
    messages: tuple[ChatMessage, ...] = ()

    def append(self, message: ChatMessage) -> Self:
        return replace(self, messages=(*self.messages, message))
