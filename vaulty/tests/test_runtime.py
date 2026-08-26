import asyncio
from pathlib import Path

from llmify import AssistantMessage, UserMessage

from vaulty import AgentRunHook, AgentRuntime, TurnEnded


class FakeAgent:
    def __init__(self, calls, *, error=None):
        self.calls = calls
        self.error = error
        self.messages = []

    async def run(self, task=None, *, messages=()):
        self.calls.append(("agent", task, list(messages)))
        if self.error is not None:
            raise self.error
        self.messages.extend(messages)
        if task is not None:
            self.messages.append(UserMessage(content=task))
        self.messages.append(AssistantMessage(content="done"))
        yield TurnEnded("done", 1)


class RecordingHook(AgentRunHook):
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    async def before_run(self, context):
        self.calls.append(("before", self.name, context.run_id))
        context.metadata[self.name] = True

    async def after_run(self, context):
        self.calls.append(("after", self.name, context.run_id))

    async def on_error(self, context, error):
        self.calls.append(("error", self.name, str(error)))


def drain(runtime, *args, **kwargs):
    async def collect():
        return [event async for event in runtime.run(*args, **kwargs)]

    return asyncio.run(collect())


def test_hooks_wrap_agent_factory_and_run_in_resource_order():
    calls = []
    first = RecordingHook("first", calls)
    second = RecordingHook("second", calls)

    def factory(context):
        calls.append(("factory", dict(context.metadata)))
        return FakeAgent(calls)

    runtime = AgentRuntime(factory, hooks=[first, second])

    events = drain(runtime, "task", run_id="run-1")

    assert events == [TurnEnded("done", 1)]
    assert calls == [
        ("before", "first", "run-1"),
        ("before", "second", "run-1"),
        ("factory", {"first": True, "second": True}),
        ("agent", "task", []),
        ("after", "second", "run-1"),
        ("after", "first", "run-1"),
    ]


def test_hook_can_select_workspace_and_factory_sees_it(tmp_path):
    selected = tmp_path / "worktrees" / "deterministic-branch"

    class WorkspaceHook(AgentRunHook):
        async def before_run(self, context):
            context.workspace = selected

    seen_workspaces = []

    def factory(context):
        seen_workspaces.append(context.workspace)
        return FakeAgent([])

    runtime = AgentRuntime(factory, hooks=[WorkspaceHook()])

    drain(runtime, "task")

    assert seen_workspaces == [selected]


def test_messages_and_metadata_are_copied_into_the_run_context():
    source_messages = [UserMessage(content="restored")]
    source_metadata = {"job_id": "daily"}
    seen = []

    def factory(context):
        seen.append(context)
        return FakeAgent([])

    runtime = AgentRuntime(factory)
    drain(
        runtime,
        "continue",
        messages=source_messages,
        metadata=source_metadata,
        workspace=Path("run-workspace"),
    )

    assert seen[0].messages == source_messages
    assert seen[0].messages is not source_messages
    assert seen[0].metadata == source_metadata
    assert seen[0].metadata is not source_metadata
    assert seen[0].workspace == Path("run-workspace")


def test_error_hooks_run_in_reverse_order_and_original_error_is_raised():
    calls = []
    failure = RuntimeError("agent failed")
    runtime = AgentRuntime(
        lambda context: FakeAgent(calls, error=failure),
        hooks=[RecordingHook("first", calls), RecordingHook("second", calls)],
    )

    try:
        drain(runtime, "task", run_id="run-2")
    except RuntimeError as error:
        assert error is failure
    else:
        raise AssertionError("expected the agent error")

    assert calls[-2:] == [
        ("error", "second", "agent failed"),
        ("error", "first", "agent failed"),
    ]
