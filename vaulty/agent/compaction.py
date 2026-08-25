import json
import logging
from typing import Any

from llmify import (
    AssistantMessage,
    ChatModel,
    Message,
    SystemMessage,
    ToolResultMessage,
    UserMessage,
)

from vaulty.config import CompactionSettings
from vaulty.llm import resolve_context_window_tokens

logger = logging.getLogger(__name__)

_SUMMARY_MARKER = "<conversation-summary>"
_SUMMARY_PROMPT = """You compact the working memory of a long-running tool-using agent.
Create a dense, loss-aware checkpoint from the transcript. Preserve:
- the user's active goal and all still-applicable requirements;
- decisions, constraints, assumptions, and rejected approaches with their reasons;
- completed work, exact file paths, symbols, commands, and important tool results;
- errors, unresolved questions, current state, and concrete next steps;
- facts that would be expensive or impossible to rediscover.

Distinguish facts from inferences. Do not invent details. Omit chatter, repeated text,
and obsolete intermediate output. Write for another instance of the same agent that
must continue the task without access to the original transcript.
"""
_CONTINUE_PROMPT = (
    "Continue the active task from the conversation summary. Do not repeat work that "
    "the summary marks as complete."
)


class ConversationCompactor:
    def __init__(
        self,
        llm: ChatModel,
        config: CompactionSettings,
        *,
        model: str,
    ) -> None:
        self._llm = llm
        self._config = config
        self.context_window_tokens = resolve_context_window_tokens(
            model, config.context_window_tokens
        )

    async def compact_if_needed(
        self,
        messages: list[Message],
        tools: list[dict],
    ) -> tuple[list[Message], int, int] | None:
        if not self._config.enabled or len(messages) <= 2:
            return None

        before = _estimate_input_tokens(messages, tools)
        trigger = int(self.context_window_tokens * self._config.trigger_fraction)
        if before < trigger:
            return None

        compacted = await self._compact(messages)
        after = _estimate_input_tokens(compacted, tools)
        if after >= before:
            logger.warning(
                "Compaction did not reduce context (%s -> %s estimated tokens)",
                before,
                after,
            )
            return None
        return compacted, before, after

    async def _compact(self, messages: list[Message]) -> list[Message]:
        system_message = messages[0]
        history = messages[1:]
        split = _recent_turn_start(history, self._config.retain_tokens)
        prefix = history[:split]
        suffix = history[split:]

        # A single tool-heavy turn can fill the window by itself. In that case the
        # whole turn becomes the checkpoint, yielding a clean continuation request.
        if not prefix:
            prefix = history
            suffix = []

        transcript = _render_transcript(prefix)
        completion = await self._llm.invoke(
            [
                SystemMessage(content=_SUMMARY_PROMPT),
                UserMessage(content=transcript),
            ],
            max_tokens=self._config.summary_max_tokens,
        )
        summary = completion.content
        if not isinstance(summary, str):
            raise RuntimeError("compaction model returned non-text content")
        summary = summary.strip()
        if not summary:
            raise RuntimeError("compaction model returned an empty summary")

        compacted: list[Message] = [
            system_message,
            SystemMessage(content=f"{_SUMMARY_MARKER}\n{summary}"),
        ]
        if suffix:
            compacted.extend(suffix)
        else:
            compacted.append(UserMessage(content=_CONTINUE_PROMPT))
        return compacted


def _estimate_input_tokens(messages: list[Message], tools: list[dict]) -> int:
    """Conservatively estimate serialized input when provider usage is unavailable."""
    message_chars = sum(len(message.model_dump_json()) + 24 for message in messages)
    tool_chars = len(json.dumps(tools, default=_json_default, ensure_ascii=False))
    return (message_chars + tool_chars + 2) // 3


def _recent_turn_start(history: list[Message], retain_tokens: int) -> int:
    user_starts = [
        index
        for index, message in enumerate(history)
        if isinstance(message, UserMessage)
    ]
    for index in user_starts:
        if index == 0:
            continue
        if _estimate_input_tokens(history[index:], []) <= retain_tokens:
            return index
    return 0


def _render_transcript(messages: list[Message]) -> str:
    rendered: list[str] = []
    for message in messages:
        if isinstance(message, AssistantMessage):
            calls = [
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                }
                for call in message.tool_calls
            ]
            rendered.append(
                f"ASSISTANT:\n{message.text}\nTOOL_CALLS: "
                f"{json.dumps(calls, ensure_ascii=False)}"
            )
        elif isinstance(message, ToolResultMessage):
            rendered.append(f"TOOL_RESULT ({message.tool_call_id}):\n{message.content}")
        else:
            rendered.append(f"{message.role.value.upper()}:\n{message.text}")
    return "\n\n".join(rendered)


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)
