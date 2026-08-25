import json
import logging
from dataclasses import dataclass, field

from agenttoolkit import Tools, ToolSchemaFormat
from llmify import (
    AssistantMessage,
    ChatModel,
    Message,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Vaulty, a coding agent working in a single workspace.

You can read, write and search files with the file tools, and run shell commands
with `bash`. `bash` executes inside a Docker sandbox where the workspace is
mounted at /workspace and there is no network access, so prefer it for anything
that must actually run (tests, scripts, interpreters).

Work in small steps: inspect before you change, verify changes by running them,
and stop as soon as the task is done. Answer the user directly once you are
finished -- do not narrate what you are about to do.
"""


@dataclass(slots=True)
class AgentResult:
    text: str
    steps: int
    messages: list[Message] = field(default_factory=list)
    stopped_early: bool = False


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
        self._system_prompt = system_prompt
        self._max_steps = max_steps

    async def run(self, task: str) -> AgentResult:
        messages: list[Message] = [
            SystemMessage(content=self._system_prompt),
            UserMessage(content=task),
        ]
        schemas = self._tools.get_schema(ToolSchemaFormat.OPENAI)

        for step in range(1, self._max_steps + 1):
            response = await self._llm.invoke(messages, tools=schemas)
            messages.append(
                AssistantMessage(
                    content=response.completion or None,
                    tool_calls=response.tool_calls,
                )
            )

            if not response.tool_calls:
                return AgentResult(
                    text=response.completion,
                    steps=step,
                    messages=messages,
                )

            for call in response.tool_calls:
                messages.append(
                    ToolResultMessage(
                        tool_call_id=call.id,
                        content=await self._call_tool(call),
                    )
                )

        return AgentResult(
            text=f"Stopped after {self._max_steps} steps without a final answer.",
            steps=self._max_steps,
            messages=messages,
            stopped_early=True,
        )

    async def _call_tool(self, call: ToolCall) -> str:
        name = call.function.name
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError as error:
            return f"Invalid JSON arguments for '{name}': {error}"

        logger.info("[agent] %s(%s)", name, arguments)
        try:
            result = await self._tools.execute(name, arguments)
        except Exception as error:  # surfaced to the model, not the caller
            return f"Tool '{name}' failed: {error}"
        return result if isinstance(result, str) else json.dumps(result, default=str)
