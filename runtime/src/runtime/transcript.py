"""Replays a stored transcript as the events a live turn would have emitted.

A frontend that can render `AgentEvent`s can then render history with the
same code, instead of growing a second renderer that drifts from the
first. Only one event is added: the agent never emits the user's own
prompts, but a transcript has to show them.
"""

import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import storage
from vaulty.agent import AgentEvent, TextDelta, ToolFinished, ToolStarted


@dataclass(slots=True)
class UserPrompt:
    text: str


type TranscriptEvent = AgentEvent | UserPrompt

type MetadataLookup = Callable[[str], Mapping[str, Any]]


def _no_metadata(name: str) -> Mapping[str, Any]:
    return {}


def replay(
    messages: Iterable[storage.ChatMessage],
    *,
    metadata: MetadataLookup = _no_metadata,
) -> Iterator[TranscriptEvent]:
    """Turn a stored conversation back into renderable events.

    `metadata` supplies the tool metadata a live `ToolFinished` carries -
    pass a lookup into the tool registry to get the same rendering the
    tool had while it ran.
    """
    names: dict[str, str] = {}
    for message in messages:
        match message:
            case storage.UserMessage(content=content):
                yield UserPrompt(content)
            case storage.AssistantMessage(content=content, tool_calls=tool_calls):
                if content:
                    yield TextDelta(content)
                for call in tool_calls:
                    names[call.id] = call.name
                    yield ToolStarted(
                        name=call.name, arguments=_arguments(call.arguments)
                    )
            case storage.ToolCallMessage(tool_call_id=tool_call_id, content=content):
                name = names.get(tool_call_id, "unknown")
                yield ToolFinished(name=name, result=content, metadata=metadata(name))


def _arguments(value: str) -> dict:
    """Tolerate malformed arguments - a transcript is shown, not executed."""
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
