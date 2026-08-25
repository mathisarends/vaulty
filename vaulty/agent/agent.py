import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

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

from vaulty.agent.models import (
    AgentEvent,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnEnded,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


class Agent:
    def __init__(
        self,
        llm: ChatModel,
        tools: Tools,
        *,
        system_prompt: str = SYSTEM_PROMPT,
        max_steps: int = 20,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self._llm = llm
        self._tools = tools
        self._max_steps = max_steps
        self._messages: list[Message] = [SystemMessage(content=system_prompt)]

    @property
    def messages(self) -> list[Message]:
        return self._messages

    async def run(self, task: str) -> AsyncIterator[AgentEvent]:
        self._messages.append(UserMessage(content=task))
        schemas = self._tools.get_schema(ToolSchemaFormat.OPENAI)

        for step in range(1, self._max_steps + 1):
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

        yield TurnEnded(text="", steps=self._max_steps, stopped_early=True)

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
