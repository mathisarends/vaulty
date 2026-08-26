"""Minimal lifecycle-hook example; it intentionally does not create a worktree."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from agenttoolkit import Tools
from llmify import ChatModel, StreamEnd, StreamTextDelta

from vaulty import Agent, AgentRunContext, AgentRunHook, AgentRuntime


class WorkspaceHook(AgentRunHook):
    def __init__(self, worktrees: Path) -> None:
        self._worktrees = worktrees

    async def before_run(self, context: AgentRunContext) -> None:
        # A future implementation can create a deterministic branch and worktree
        # here. The factory below will then bind the agent's tools to this path.
        context.workspace = self._worktrees / context.run_id
        print(f"starting {context.run_id} in {context.workspace}")

    async def after_run(
        self,
        context: AgentRunContext,
    ) -> None:
        print(f"finished {context.run_id}")

    async def on_error(
        self,
        context: AgentRunContext,
        error: BaseException,
    ) -> None:
        print(f"failed {context.run_id}: {error}")


def build_runtime(
    llm: ChatModel,
    tools_for_workspace: Callable[[Path], Tools],
    worktrees: Path,
) -> AgentRuntime:
    def create_agent(context: AgentRunContext) -> Agent:
        if context.workspace is None:
            raise RuntimeError("the run has no workspace")
        return Agent(llm, tools_for_workspace(context.workspace))

    return AgentRuntime(
        create_agent,
        hooks=[WorkspaceHook(worktrees)],
    )


async def run_example(runtime: AgentRuntime) -> None:
    async for event in runtime.run(
        "Inspect the repository",
        run_id="issue-42-attempt-1",
        metadata={"issue": 42},
    ):
        print(event)


class DemoLLM:
    """Local stand-in so this example runs without an API call."""

    model = "demo-model"

    async def stream(self, messages, tools=None, **kwargs):
        text = "The demo agent completed its run."
        yield StreamTextDelta(delta=text)
        yield StreamEnd(completion=text, tool_calls=[])


def main() -> None:
    runtime = build_runtime(
        DemoLLM(),  # type: ignore[arg-type]
        tools_for_workspace=lambda workspace: Tools(),
        worktrees=Path(".worktrees"),
    )
    asyncio.run(run_example(runtime))


if __name__ == "__main__":
    main()
