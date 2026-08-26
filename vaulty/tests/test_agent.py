import asyncio
import json
from types import SimpleNamespace

from agenttoolkit.builtins.fs import LocalWorkspace
from llmify import (
    AssistantMessage,
    Function,
    StreamEnd,
    StreamTextDelta,
    ToolCall,
    UserMessage,
)

from tests.test_tools import FakeRunner
from vaulty import (
    Agent,
    ContextCompacted,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnEnded,
)
from vaulty.config import CompactionSettings
from vaulty.tools import Dependencies, build_tools


class ScriptedLLM:
    """Replays prepared stream rounds instead of calling a provider."""

    model = "test-model"

    def __init__(self, rounds, summaries=None):
        self.rounds = list(rounds)
        self.summaries = list(summaries or [])
        self.seen_messages = []
        self.compaction_messages = []

    async def stream(self, messages, tools=None, **kwargs):
        self.seen_messages.append(list(messages))
        text, tool_calls = self.rounds.pop(0)
        for chunk in text:
            yield StreamTextDelta(delta=chunk)
        yield StreamEnd(completion="".join(text), tool_calls=tool_calls)

    async def invoke(self, messages, **kwargs):
        self.compaction_messages.append(list(messages))
        return SimpleNamespace(content=self.summaries.pop(0))


def tool_call(name, **arguments):
    return ToolCall(
        id=f"call_{name}",
        function=Function(name=name, arguments=json.dumps(arguments)),
    )


def collect(agent, task):
    async def drain():
        return [event async for event in agent.run(task)]

    return asyncio.run(drain())


def build_agent(rounds, tmp_path, *, compaction=None, summaries=None, messages=()):
    workspace = LocalWorkspace(tmp_path)
    tools = build_tools(Dependencies(workspace, FakeRunner(commands=[])))
    llm = ScriptedLLM(rounds, summaries)
    return Agent(llm, tools, compaction=compaction, messages=messages), workspace, llm


def test_text_only_turn_streams_deltas_and_ends(tmp_path):
    agent, _, _ = build_agent([(["Hel", "lo"], [])], tmp_path)

    events = collect(agent, "hi")

    assert events == [TextDelta("Hel"), TextDelta("lo"), TurnEnded("Hello", 1)]


def test_tool_round_emits_start_and_finish_then_final_text(tmp_path):
    rounds = [
        (["let me look"], [tool_call("write_file", path="a.txt", content="x")]),
        (["done"], []),
    ]
    agent, workspace, _ = build_agent(rounds, tmp_path)

    events = collect(agent, "write a file")

    assert ToolStarted("write_file", {"path": "a.txt", "content": "x"}) in events
    assert ToolFinished("write_file", "wrote a.txt (1 chars)") in events
    assert events[-1] == TurnEnded("done", 2)
    assert (workspace.root / "a.txt").read_text(encoding="utf-8") == "x"


def test_tool_result_is_fed_back_to_the_model(tmp_path):
    rounds = [(["..."], [tool_call("bash", command="echo hello")]), (["ok"], [])]
    agent, _, llm = build_agent(rounds, tmp_path)

    collect(agent, "run it")

    second_round = llm.seen_messages[1]
    assert second_round[-1].content.startswith("exit code: 0")
    assert second_round[-2].tool_calls[0].function.name == "bash"


def test_history_survives_across_turns(tmp_path):
    agent, _, _ = build_agent([(["one"], []), (["two"], [])], tmp_path)

    collect(agent, "first")
    collect(agent, "second")

    roles = [message.role for message in agent.messages]
    assert roles == ["system", "user", "assistant", "user", "assistant"]


def test_initial_messages_restore_conversation_before_new_task(tmp_path):
    history = [
        UserMessage(content="remember this"),
        AssistantMessage(content="remembered"),
    ]
    agent, _, llm = build_agent([(["continued"], [])], tmp_path, messages=history)

    collect(agent, "continue")

    assert [message.role for message in llm.seen_messages[0]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert llm.seen_messages[0][-1].content == "continue"


def test_run_injects_messages_before_new_task(tmp_path):
    agent, _, llm = build_agent([(["done"], [])], tmp_path)

    async def drain():
        context = [
            UserMessage(content="external question"),
            AssistantMessage(content="external answer"),
        ]
        return [event async for event in agent.run("next", messages=context)]

    asyncio.run(drain())

    assert [message.content for message in llm.seen_messages[0][1:]] == [
        "external question",
        "external answer",
        "next",
    ]


def test_run_can_continue_from_injected_messages_without_new_task(tmp_path):
    agent, _, llm = build_agent([(["continued"], [])], tmp_path)

    async def drain():
        return [
            event
            async for event in agent.run(
                messages=[UserMessage(content="injected request")]
            )
        ]

    events = asyncio.run(drain())

    assert llm.seen_messages[0][-1].content == "injected request"
    assert events[-1] == TurnEnded("continued", 1)


def test_tool_loop_runs_until_the_model_finishes(tmp_path):
    rounds = [(["..."], [tool_call("list_dir")])] * 3 + [(["done"], [])]
    agent, _, llm = build_agent(rounds, tmp_path)

    events = collect(agent, "keep going")

    assert events[-1] == TurnEnded("done", 4)
    assert len(llm.seen_messages) == 4


def test_old_turns_are_compacted_but_recent_turn_is_preserved(tmp_path):
    settings = CompactionSettings(
        context_window_tokens=600,
        trigger_fraction=0.5,
        retain_tokens=100,
        summary_max_tokens=64,
    )
    rounds = [(["old answer " * 30], []), (["new answer"], [])]
    agent, _, llm = build_agent(
        rounds,
        tmp_path,
        compaction=settings,
        summaries=["Goal and completed work from the old turn."],
    )

    collect(agent, "old request " * 30)
    events = collect(agent, "new request")

    compacted = next(event for event in events if isinstance(event, ContextCompacted))
    assert compacted.after_tokens < compacted.before_tokens
    assert "old request" in llm.compaction_messages[0][-1].content
    assert agent.messages[1].content.startswith("<conversation-summary>")
    assert agent.messages[2].content == "new request"
