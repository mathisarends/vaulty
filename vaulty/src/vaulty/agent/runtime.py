import inspect
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from llmify import Message

from vaulty.agent.agent import Agent
from vaulty.agent.views import AgentEvent, TurnEnded

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentRunContext:
    """Mutable setup shared by hooks and the agent factory for one run."""

    run_id: str
    task: str | None
    messages: list[Message]
    workspace: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRunHook:
    """Lifecycle hook with optional setup, success, and error callbacks."""

    async def before_run(self, context: AgentRunContext) -> None:
        pass

    async def after_run(
        self,
        context: AgentRunContext,
    ) -> None:
        pass

    async def on_error(
        self,
        context: AgentRunContext,
        error: BaseException,
    ) -> None:
        pass


AgentFactory = Callable[[AgentRunContext], Agent | Awaitable[Agent]]


class AgentRuntime:
    """Runs lifecycle hooks around a freshly constructed agent."""

    def __init__(
        self,
        agent_factory: AgentFactory,
        *,
        hooks: Iterable[AgentRunHook] = (),
    ) -> None:
        self._agent_factory = agent_factory
        self._hooks = tuple(hooks)

    async def run(
        self,
        task: str | None = None,
        *,
        messages: Iterable[Message] = (),
        run_id: str | None = None,
        workspace: Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        context = AgentRunContext(
            run_id=run_id or uuid4().hex,
            task=task,
            messages=list(messages),
            workspace=workspace,
            metadata=dict(metadata or {}),
        )
        started_hooks: list[AgentRunHook] = []

        try:
            for hook in self._hooks:
                started_hooks.append(hook)
                await _maybe_await(hook.before_run(context))

            agent = await _maybe_await(self._agent_factory(context))
            final_event: TurnEnded | None = None
            async for event in agent.run(context.task, messages=context.messages):
                if isinstance(event, TurnEnded):
                    final_event = event
                yield event

            if final_event is None:
                raise RuntimeError("agent run ended without a TurnEnded event")

        except BaseException as error:
            await _notify_error(started_hooks, context, error)
            raise
        else:
            await _notify_success(started_hooks, context)


async def _maybe_await[ResultT](value: ResultT | Awaitable[ResultT]) -> ResultT:
    if inspect.isawaitable(value):
        return await value
    return value


async def _notify_success(
    hooks: list[AgentRunHook],
    context: AgentRunContext,
) -> None:
    first_error: BaseException | None = None
    for hook in reversed(hooks):
        try:
            await _maybe_await(hook.after_run(context))
        except BaseException as error:
            if first_error is None:
                first_error = error
            else:
                logger.exception("Agent after_run hook failed", exc_info=error)
    if first_error is not None:
        raise first_error


async def _notify_error(
    hooks: list[AgentRunHook],
    context: AgentRunContext,
    run_error: BaseException,
) -> None:
    for hook in reversed(hooks):
        try:
            await _maybe_await(hook.on_error(context, run_error))
        except BaseException as hook_error:
            logger.exception("Agent on_error hook failed", exc_info=hook_error)
