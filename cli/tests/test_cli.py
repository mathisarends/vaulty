from collections.abc import Iterable
from datetime import UTC, datetime
from io import StringIO
from typing import cast
from uuid import uuid4

import llmify
from rich.console import Console

import storage
from cli.app import build_parser
from cli.terminal import TerminalChat, checklist_renderable, parse_checklist
from runtime import SessionRunner, to_llm
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


def build_terminal(console, tmp_path, *, opener=None, repository=None, metadata=None):
    return TerminalChat(
        console,
        open_session=opener or (lambda session: never_opened()),
        repository=repository or MemorySessionRepository(),
        workspace=tmp_path,
        model="test",
        **({"metadata": metadata} if metadata else {}),
    )


async def never_opened() -> SessionRunner:
    raise AssertionError("this test does not open a session")


def test_tool_metadata_selects_checklist_renderer(tmp_path):
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    terminal = build_terminal(console, tmp_path)

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
    def __init__(self, messages: Iterable[llmify.Message] = ()) -> None:
        self.messages: list[llmify.Message] = [
            llmify.SystemMessage(content="you are vaulty"),
            *messages,
        ]

    async def run(self, task: str):
        self.messages.append(llmify.UserMessage(content=task))
        self.messages.append(llmify.AssistantMessage(content="done"))
        yield TurnEnded(text="done", steps=1)


def opener(repository: MemorySessionRepository):
    """Opens sessions the way app.py does, minus the model and the sandbox."""

    async def open_session(session: storage.Session | None) -> SessionRunner:
        if session is None:
            return await SessionRunner.start(
                cast(Agent, StubAgent()), repository, trigger=SessionTrigger.CLI
            )
        return await SessionRunner.reopen(
            cast(Agent, StubAgent(to_llm(session.messages))), repository, session
        )

    return open_session


def scripted(lines: list[str]) -> tuple[ScriptedConsole, StringIO]:
    output = StringIO()
    return (
        ScriptedConsole(lines, file=output, no_color=True, width=100),
        output,
    )


async def test_the_terminal_records_its_turns_and_closes_the_session(tmp_path):
    repository = MemorySessionRepository()
    console, _ = scripted(["tidy up the vault", "/exit"])
    terminal = build_terminal(
        console, tmp_path, opener=opener(repository), repository=repository
    )

    await terminal.run()

    stored = (await repository.list())[0]
    assert [message.role for message in stored.messages] == ["user", "assistant"]
    assert stored.title == "tidy up the vault"
    assert stored.status is SessionStatus.FINISHED


async def test_resume_switches_to_the_chosen_session(tmp_path):
    repository = MemorySessionRepository()
    earlier = await repository.create(
        uuid4(), datetime.now(UTC), trigger=SessionTrigger.CRON, title="nightly run"
    )
    await repository.save(
        earlier.append(
            storage.UserMessage(
                content="garden the vault", created_at=datetime.now(UTC)
            )
        ).with_status(SessionStatus.FINISHED)
    )

    console, output = scripted(["/resume", "1", "and now the inbox", "/exit"])
    terminal = build_terminal(
        console, tmp_path, opener=opener(repository), repository=repository
    )

    await terminal.run()

    rendered = output.getvalue()
    assert "nightly run" in rendered
    assert "cron" in rendered
    assert "you › garden the vault" in rendered  # the transcript was replayed

    resumed = await repository.get(earlier.id)
    assert resumed is not None
    assert [message.role for message in resumed.messages] == [
        "user",
        "user",
        "assistant",
    ]
    assert resumed.status is SessionStatus.FINISHED
    assert len(await repository.list()) == 1  # the empty session was discarded


async def test_resume_refuses_a_session_another_agent_still_owns(tmp_path):
    repository = MemorySessionRepository()
    await repository.create(
        uuid4(), datetime.now(UTC), trigger=SessionTrigger.CRON, title="nightly run"
    )

    console, output = scripted(["/resume", "1", "/exit"])
    terminal = build_terminal(
        console, tmp_path, opener=opener(repository), repository=repository
    )

    await terminal.run()

    assert "still running" in output.getvalue()


async def test_resume_without_earlier_sessions_says_so(tmp_path):
    repository = MemorySessionRepository()
    console, output = scripted(["/resume", "/exit"])
    terminal = build_terminal(
        console, tmp_path, opener=opener(repository), repository=repository
    )

    await terminal.run()

    assert "No earlier sessions yet." in output.getvalue()


async def test_resume_rejects_a_number_that_is_not_in_the_list(tmp_path):
    repository = MemorySessionRepository()
    earlier = await repository.create(
        uuid4(), datetime.now(UTC), trigger=SessionTrigger.CLI, title="earlier"
    )
    await repository.save(earlier.with_status(SessionStatus.FINISHED))

    console, output = scripted(["/resume 7", "/exit"])
    terminal = build_terminal(
        console, tmp_path, opener=opener(repository), repository=repository
    )

    await terminal.run()

    assert "No session '7' in the list." in output.getvalue()


def test_a_stored_transcript_renders_like_a_live_turn(tmp_path):
    now = datetime.now(UTC)
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    terminal = build_terminal(
        console,
        tmp_path,
        metadata=lambda name: {"terminal_renderer": "checklist"},
    )

    terminal.show(
        (
            storage.UserMessage(content="plan two steps", created_at=now),
            storage.AssistantMessage(
                content="on it",
                tool_calls=(
                    storage.ToolCall(id="1", name="add_todos", arguments="{}"),
                ),
                created_at=now,
            ),
            storage.ToolCallMessage(
                tool_call_id="1",
                content="1. [ ] Notiz anlegen",
                created_at=now,
            ),
        )
    )

    rendered = output.getvalue()
    assert "you › plan two steps" in rendered
    assert "on it" in rendered
    assert "add_todos" in rendered
    assert "Checklist" in rendered and "Notiz anlegen" in rendered
