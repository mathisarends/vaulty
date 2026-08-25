import json
import logging
from collections.abc import AsyncIterator

from agenttoolkit import Tools, ToolSchemaFormat
from llmify import (
    AssistantMessage,
    ChatModel,
    Message,
    StreamEnd,
    StreamTextDelta,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

from vaulty.agent.compaction import ConversationCompactor
from vaulty.agent.prompt import SystemPrompt, read_base_prompt
from vaulty.agent.views import (
    AgentEvent,
    ContextCompacted,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnEnded,
)
from vaulty.config import CompactionSettings

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        llm: ChatModel,
        tools: Tools,
        *,
        system_prompt: SystemPrompt | None = None,
        compaction: CompactionSettings | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        prompt = system_prompt or SystemPrompt(read_base_prompt())
        self._messages: list[Message] = [SystemMessage(content=prompt.render())]
        self._compactor = ConversationCompactor(
            llm,
            compaction or CompactionSettings(),
            model=llm.model,
        )

    @property
    def messages(self) -> list[Message]:
        return self._messages

    async def run(self, task: str) -> AsyncIterator[AgentEvent]:
        self._messages.append(UserMessage(content=task))
        schemas = self._tools.get_schema(ToolSchemaFormat.OPENAI)

        step = 0
        while True:
            compacted = await self._compactor.compact_if_needed(self._messages, schemas)
            if compacted is not None:
                messages, before_tokens, after_tokens = compacted
                self._messages[:] = messages
                yield ContextCompacted(before_tokens, after_tokens)

            step += 1
            end: StreamEnd | None = None
            async for event in self._llm.stream(self._messages, tools=schemas):
                if isinstance(event, StreamTextDelta):
                    yield TextDelta(event.delta)
                elif isinstance(event, StreamEnd):
                    end = event
            if end is None:
                raise RuntimeError("stream ended without a final event")

            self._messages.append(
                AssistantMessage(
                    content=end.completion or None,
                    tool_calls=end.tool_calls,
                )
            )

            if not end.tool_calls:
                yield TurnEnded(text=end.completion, steps=step)
                return

            for call in end.tool_calls:
                name = call.function.name
                arguments, error = _parse_arguments(call)
                yield ToolStarted(name=name, arguments=arguments)
                result = error or await self._call_tool(name, arguments)
                yield ToolFinished(name=name, result=result)
                self._messages.append(
                    ToolResultMessage(tool_call_id=call.id, content=result)
                )

    async def _call_tool(self, name: str, arguments: dict) -> str:
        logger.info("[agent] %s(%s)", name, arguments)
        try:
            result = await self._tools.execute(name, arguments)
        except Exception as error:  # surfaced to the model, not the caller
            return f"Tool '{name}' failed: {error}"
        return result if isinstance(result, str) else json.dumps(result, default=str)


def _parse_arguments(call: ToolCall) -> tuple[dict, str | None]:
    try:
        return json.loads(call.function.arguments or "{}"), None
    except json.JSONDecodeError as error:
        return {}, f"Invalid JSON arguments for '{call.function.name}': {error}"
