import asyncio
import json

from agenttoolkit.builtins.fs import LocalWorkspace
from llmify import Function, StreamEnd, StreamTextDelta, ToolCall

from tests.test_tools import FakeRunner
from vaulty import Agent, TextDelta, ToolFinished, ToolStarted, TurnEnded
from vaulty.tools import Dependencies, build_tools


class ScriptedLLM:
    """Replays prepared stream rounds instead of calling a provider."""

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.seen_messages = []

    async def stream(self, messages, tools=None, **kwargs):
        self.seen_messages.append(list(messages))
        text, tool_calls = self.rounds.pop(0)
        for chunk in text:
            yield StreamTextDelta(delta=chunk)
        yield StreamEnd(completion="".join(text), tool_calls=tool_calls)


def tool_call(name, **arguments):
    return ToolCall(
        id=f"call_{name}",
        function=Function(name=name, arguments=json.dumps(arguments)),
    )


def collect(agent, task):
    async def drain():
        return [event async for event in agent.run(task)]

    return asyncio.run(drain())


def build_agent(rounds, tmp_path, *, max_steps=20):
    workspace = LocalWorkspace(tmp_path)
    tools = build_tools(Dependencies(workspace, FakeRunner(commands=[])))
    llm = ScriptedLLM(rounds)
    return Agent(llm, tools, max_steps=max_steps), workspace, llm


def test_text_only_turn_streams_deltas_and_ends(tmp_path):
    agent, _, llm = build_agent([(["Hel", "lo"], [])], tmp_path)

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
    rounds = [(["…"], [tool_call("bash", command="echo hello")]), (["ok"], [])]
    agent, _, llm = build_agent(rounds, tmp_path)

    collect(agent, "run it")

    second_round = llm.seen_messages[1]
    assert second_round[-1].content.startswith("exit code: 0")
    assert second_round[-2].tool_calls[0].function.name == "bash"


def test_history_survives_across_turns(tmp_path):
    agent, _, llm = build_agent([(["one"], []), (["two"], [])], tmp_path)

    collect(agent, "first")
    collect(agent, "second")

    roles = [message.role for message in agent.messages]
    assert roles == ["system", "user", "assistant", "user", "assistant"]


def test_max_steps_stops_the_loop(tmp_path):
    rounds = [(["…"], [tool_call("list_dir")])] * 3
    agent, _, llm = build_agent(rounds, tmp_path, max_steps=2)

    events = collect(agent, "loop forever")

    assert events[-1] == TurnEnded("", 2, stopped_early=True)
