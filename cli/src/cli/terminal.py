import asyncio
import difflib
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console, Group
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

import storage
from cli.picker import by_number, choose_session
from runtime import (
    MetadataLookup,
    SessionRunner,
    TranscriptEvent,
    UserPrompt,
    replay,
)
from vaulty.agent import (
    ContextCompacted,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnEnded,
)

_CHECKBOX = re.compile(r"^(?P<number>\d+)\. \[(?P<mark>[ x~])\] (?P<label>.+)$")
_COMMANDS = {
    "/clear": "clear the terminal",
    "/compact": "compact the conversation now",
    "/resume": "switch to an earlier session",
    "/help": "show local commands",
    "/exit": "leave Vaulty",
}
_SESSION_LIMIT = 10


type SessionOpener = Callable[[storage.Session | None], Awaitable[SessionRunner]]
type Chooser = Callable[[Console, Sequence[storage.Session]], storage.Session | None]


def _no_metadata(name: str) -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    number: int
    mark: str
    label: str


def parse_checklist(value: str) -> tuple[ChecklistItem, ...] | None:
    items: list[ChecklistItem] = []
    for line in value.splitlines():
        match = _CHECKBOX.fullmatch(line)
        if match is None:
            return None
        items.append(
            ChecklistItem(
                number=int(match["number"]),
                mark=match["mark"],
                label=match["label"],
            )
        )
    return tuple(items) or None


def checklist_renderable(items: tuple[ChecklistItem, ...]) -> Padding:
    table = Table.grid(padding=(0, 1))
    table.add_column(width=3, justify="center")
    table.add_column(justify="right", style="dim")
    table.add_column()

    styles = {
        " ": ("[ ]", "dim", ""),
        "~": ("[~]", "yellow", "yellow"),
        "x": ("[x]", "green", "dim strike"),
    }
    for item in items:
        checkbox, checkbox_style, label_style = styles[item.mark]
        table.add_row(
            Text(checkbox, style=checkbox_style),
            str(item.number),
            Text(item.label, style=label_style),
        )
    content = Group(
        Text("Checklist", style="bold"),
        Padding(table, (0, 0, 0, 2)),
    )
    return Padding(content, (0, 0, 0, 4))


def _preview(value: object, limit: int = 160) -> str:
    single_line = " ".join(str(value).split())
    if len(single_line) <= limit:
        return single_line
    return f"{single_line[: limit - 1]}…"


def _format_arguments(arguments: dict) -> str:
    return ", ".join(
        f"{key}={_preview(repr(value), 60)}" for key, value in arguments.items()
    )


class TerminalChat:
    def __init__(
        self,
        console: Console,
        *,
        open_session: SessionOpener,
        repository: storage.SessionRepository,
        workspace: Path,
        model: str,
        metadata: MetadataLookup = _no_metadata,
        chooser: Chooser = choose_session,
    ) -> None:
        self._console = console
        self._open_session = open_session
        self._repository = repository
        self._metadata = metadata
        self._chooser = chooser
        self._workspace = workspace
        self._model = model
        self._streaming = False
        self._runner: SessionRunner | None = None

    @property
    def runner(self) -> SessionRunner:
        """The session being chatted with. Only valid while `run` is active."""
        if self._runner is None:
            raise RuntimeError("No session is open")
        return self._runner

    async def run(self) -> None:
        self._runner = await self._open_session(None)
        self._welcome()
        try:
            await self._loop()
        finally:
            await self._close_current()

    async def _loop(self) -> None:
        while True:
            try:
                task = (
                    await asyncio.to_thread(
                        self._console.input, "[bold cyan]you[/] [dim]›[/] "
                    )
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self._console.print()
                return

            if not task:
                continue
            if await self._handle_command(task):
                if task.casefold() in {"/exit", "exit", "quit"}:
                    return
                continue

            self._console.print()
            try:
                await self._turn(task)
            except KeyboardInterrupt:
                self._finish_stream()
                self._console.print("[yellow]Turn interrupted.[/yellow]")
            self._console.print()

    def _welcome(self) -> None:
        self._console.print(
            "[bold magenta]Vaulty[/bold magenta] [dim]interactive agent[/dim]"
        )
        self._console.print(f"[dim]Workspace[/dim]  {self._workspace}")
        self._console.print(f"[dim]Model[/dim]      {self._model}")
        session = self.runner.session
        label = session.title or "new session"
        self._console.print(
            f"[dim]Session[/dim]    {label} [dim]({session.trigger.value})[/dim]"
        )
        self._console.print(
            "[dim]Type /help for commands · Ctrl-C to interrupt[/dim]\n"
        )

    async def _handle_command(self, value: str) -> bool:
        head, _, argument = value.partition(" ")
        command = head.casefold()
        if command in {"/exit", "exit", "quit"}:
            return True
        if command == "/clear":
            self._console.clear()
            self._welcome()
            return True
        if command == "/compact":
            await self._compact_now()
            return True
        if command == "/resume":
            await self._resume(argument.strip())
            return True
        if command == "/help":
            table = Table.grid(padding=(0, 2))
            for name, description in _COMMANDS.items():
                table.add_row(Text(name, style="cyan"), description)
            self._console.print(table)
            return True
        return command.startswith("/") and self._unknown_command(value)

    async def _resume(self, argument: str) -> None:
        """Show earlier sessions and switch to the one the user picks."""
        sessions = [
            session
            for session in await self._repository.list(limit=_SESSION_LIMIT + 1)
            if session.id != self.runner.session.id
        ][:_SESSION_LIMIT]
        if not sessions:
            self._console.print("[dim]No earlier sessions yet.[/dim]")
            return

        chosen = await self._choose(sessions, argument)
        if chosen is None:
            return
        if chosen.status is storage.SessionStatus.RUNNING:
            self._console.print(
                "[yellow]That session is still running.[/yellow] "
                "[dim]Another agent is writing to it.[/dim]"
            )
            return

        await self._close_current()
        self._runner = await self._open_session(chosen)
        self._console.clear()
        self._welcome()
        self.show(chosen.messages)

    async def _choose(
        self, sessions: list[storage.Session], argument: str
    ) -> storage.Session | None:
        """`/resume 2` picks straight away; a bare `/resume` opens the picker."""
        if argument:
            return by_number(self._console, sessions, argument)
        try:
            return await asyncio.to_thread(self._chooser, self._console, sessions)
        except KeyboardInterrupt:
            self._console.print()
            return None

    async def _close_current(self) -> None:
        """Hand back the current session, discarding it if nothing was said."""
        session = self.runner.session
        if session.messages:
            await self.runner.finish()
        else:
            await self._repository.delete(session.id)
        self._runner = None

    async def _compact_now(self) -> None:
        with self._console.status("[dim]Compacting context…[/dim]", spinner="dots"):
            result = await self.runner.compact()
        if result is None:
            self._console.print("[dim]Nothing to compact.[/dim]")
            return
        self._console.print(
            "[dim]↻ Context compacted: "
            f"{result.before_tokens:,} → {result.after_tokens:,} estimated tokens[/dim]"
        )

    def _unknown_command(self, value: str) -> bool:
        line = Text("Unknown command: ", style="yellow")
        line.append(value)
        self._console.print(line)
        suggestion = difflib.get_close_matches(
            value.casefold(), _COMMANDS.keys(), n=1, cutoff=0.6
        )
        if suggestion:
            self._console.print(f"[dim]Did you mean {suggestion[0]}?[/dim]")
        else:
            self._console.print("[dim]Type /help to list local commands.[/dim]")
        return True

    def show(self, messages: Iterable[storage.ChatMessage]) -> None:
        """Print a stored conversation through the live renderer."""
        for event in replay(messages, metadata=self._metadata):
            self._render(event)
        self._finish_stream()

    async def _turn(self, task: str) -> None:
        async for event in self.runner.run(task):
            self._render(event)

    def _render(self, event: TranscriptEvent) -> None:
        match event:
            case UserPrompt(text):
                self._finish_stream()
                self._console.print(f"[bold cyan]you[/] [dim]›[/] {text}")
            case TextDelta(text):
                self._write_text(text)
            case ToolStarted(name, arguments):
                self._tool_started(name, arguments)
            case ToolFinished(name, result, metadata):
                self._tool_finished(name, result, metadata)
            case ContextCompacted(before_tokens, after_tokens):
                self._finish_stream()
                self._console.print(
                    "[dim]↻ Context compacted: "
                    f"{before_tokens:,} → {after_tokens:,} estimated tokens[/dim]"
                )
            case TurnEnded(_, _):
                self._finish_stream()

    def _write_text(self, text: str) -> None:
        if not self._streaming:
            self._console.print("[bold magenta]vaulty[/] [dim]›[/] ", end="")
            self._streaming = True
        self._console.print(Text(text), end="", soft_wrap=True)

    def _finish_stream(self) -> None:
        if self._streaming:
            self._console.print()
            self._streaming = False

    def _tool_started(self, name: str, arguments: dict) -> None:
        self._finish_stream()
        detail = _format_arguments(arguments)
        line = Text("  • ", style="cyan")
        line.append(name, style="bold cyan")
        if detail:
            line.append(f"  {detail}", style="dim")
        self._console.print(line)

    def _tool_finished(
        self, name: str, result: str, metadata: Mapping[str, Any]
    ) -> None:
        if (
            metadata.get("terminal_renderer") == "checklist"
            and (items := parse_checklist(result)) is not None
        ):
            self._console.print(checklist_renderable(items))
        else:
            self._console.print(Text(f"    ↳ {_preview(result)}", style="dim"))
        self._console.print()
