from io import StringIO
from typing import cast

import llmify
from rich.console import Console

from cli.app import build_parser
from cli.terminal import TerminalChat, checklist_renderable, parse_checklist
from runtime import SessionRunner
from storage import MemorySessionRepository, SessionStatus, SessionTrigger
from vaulty.agent import Agent, TurnEnded


def test_cli_accepts_workspace_and_display_overrides(tmp_path):
    args = build_parser().parse_args(["--root", str(tmp_path), "--no-color"])

    assert args.root == tmp_path
    assert args.no_color is True


def test_checklist_renderer_shows_pending_and_completed_items():
    items = parse_checklist("1. [x] Inspect files\n2. [ ] Run tests")

    assert items is not None
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    console.print(checklist_renderable(items))

    rendered = output.getvalue()
    assert "Checklist" in rendered
    assert "[x]" in rendered and "Inspect files" in rendered
    assert "[ ]" in rendered and "Run tests" in rendered


def test_checklist_parser_rejects_regular_tool_output():
    assert parse_checklist("wrote notes.md (12 chars)") is None


def test_tool_metadata_selects_checklist_renderer(tmp_path):
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    terminal = TerminalChat(
        cast(SessionRunner, object()), console, workspace=tmp_path, model="test"
    )

    terminal._tool_finished(
        "arbitrarily_named_tool",
        "1. [ ] Run tests",
        {"terminal_renderer": "checklist"},
    )

    rendered = output.getvalue()
    assert "Checklist" in rendered
    assert "Run tests" in rendered


class ScriptedConsole(Console):
    """A console whose `input` replays a script instead of blocking on stdin."""

    def __init__(self, lines: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._lines = iter(lines)

    def input(self, *args, **kwargs) -> str:  # type: ignore[override]
        try:
            return next(self._lines)
        except StopIteration:
            raise EOFError from None


class StubAgent:
    def __init__(self) -> None:
        self.messages: list[llmify.Message] = [
            llmify.SystemMessage(content="you are vaulty")
        ]

    async def run(self, task: str):
        self.messages.append(llmify.UserMessage(content=task))
        self.messages.append(llmify.AssistantMessage(content="done"))
        yield TurnEnded(text="done", steps=1)


async def test_the_terminal_records_its_turns_and_closes_the_session(tmp_path):
    repository = MemorySessionRepository()
    runner = await SessionRunner.start(
        cast(Agent, StubAgent()), repository, trigger=SessionTrigger.CLI
    )
    console = ScriptedConsole(
        ["tidy up the vault", "/exit"],
        file=StringIO(),
        no_color=True,
        width=80,
    )

    await TerminalChat(runner, console, workspace=tmp_path, model="test").run()

    stored = await repository.get(runner.session.id)
    assert stored is not None
    assert [message.role for message in stored.messages] == ["user", "assistant"]
    assert stored.title == "tidy up the vault"
    assert stored.status is SessionStatus.FINISHED
