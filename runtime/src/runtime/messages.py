"""Translation between the agent's live history and the stored transcript.

`llmify` messages are what the model sees; `storage` messages are what we
keep. The two are deliberately separate types: the stored transcript holds
no `SystemMessage`, so resuming a session renders today's system prompt
instead of restoring a stale one.
"""

from collections.abc import Iterable
from datetime import datetime

import llmify

import storage


def to_storage(
    messages: Iterable[llmify.Message], created_at: datetime
) -> tuple[storage.ChatMessage, ...]:
    """Map live messages onto their stored form, dropping the system prompt."""
    stored: list[storage.ChatMessage] = []
    for message in messages:
        match message:
            case llmify.SystemMessage():
                continue
            case llmify.UserMessage():
                stored.append(
                    storage.UserMessage(content=message.text, created_at=created_at)
                )
            case llmify.AssistantMessage():
                stored.append(
                    storage.AssistantMessage(
                        content=message.text or None,
                        tool_calls=tuple(
                            storage.ToolCall(
                                id=call.id,
                                name=call.function.name,
                                arguments=call.function.arguments,
                            )
                            for call in message.tool_calls
                        ),
                        created_at=created_at,
                    )
                )
            case llmify.ToolResultMessage():
                stored.append(
                    storage.ToolCallMessage(
                        tool_call_id=message.tool_call_id,
                        content=message.content,
                        created_at=created_at,
                    )
                )
    return tuple(stored)


def to_llm(messages: Iterable[storage.ChatMessage]) -> list[llmify.Message]:
    """Rebuild the model-facing history from a stored transcript."""
    restored: list[llmify.Message] = []
    for message in messages:
        match message:
            case storage.UserMessage(content=content):
                restored.append(llmify.UserMessage(content=content))
            case storage.AssistantMessage(content=content, tool_calls=tool_calls):
                restored.append(
                    llmify.AssistantMessage(
                        content=content,
                        tool_calls=[
                            llmify.ToolCall(
                                id=call.id,
                                function=llmify.Function(
                                    name=call.name, arguments=call.arguments
                                ),
                            )
                            for call in tool_calls
                        ],
                    )
                )
            case storage.ToolCallMessage(tool_call_id=tool_call_id, content=content):
                restored.append(
                    llmify.ToolResultMessage(tool_call_id=tool_call_id, content=content)
                )
    return restored
