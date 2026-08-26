import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console, Group
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from vaulty.agent import (
    Agent,
    ContextCompacted,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnEnded,
)

_CHECKLIST_TOOLS = {"add_todos", "todos", "check_off"}
_CHECKBOX = re.compile(r"^(?P<number>\d+)\. \[(?P<mark>[ x~])\] (?P<label>.+)$")
_COMMANDS = {
    "/clear": "clear the terminal",
    "/help": "show local commands",
    "/exit": "leave Vaulty",
}


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
        agent: Agent,
        console: Console,
        *,
        workspace: Path,
        model: str,
    ) -> None:
        self._agent = agent
        self._console = console
        self._workspace = workspace
        self._model = model
        self._streaming = False

    async def run(self) -> None:
        self._welcome()
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
        self._console.print(
            "[dim]Type /help for commands · Ctrl-C to interrupt[/dim]\n"
        )

    async def _handle_command(self, value: str) -> bool:
        command = value.casefold()
        if command in {"/exit", "exit", "quit"}:
            return True
        if command == "/clear":
            self._console.clear()
            self._welcome()
            return True
        if command == "/help":
            table = Table.grid(padding=(0, 2))
            for name, description in _COMMANDS.items():
                table.add_row(Text(name, style="cyan"), description)
            self._console.print(table)
            return True
        return command.startswith("/") and self._unknown_command(value)

    def _unknown_command(self, value: str) -> bool:
        line = Text("Unknown command: ", style="yellow")
        line.append(value)
        self._console.print(line)
        self._console.print("[dim]Type /help to list local commands.[/dim]")
        return True

    async def _turn(self, task: str) -> None:
        async for event in self._agent.run(task):
            match event:
                case TextDelta(text):
                    self._write_text(text)
                case ToolStarted(name, arguments):
                    self._tool_started(name, arguments)
                case ToolFinished(name, result):
                    self._tool_finished(name, result)
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

    def _tool_finished(self, name: str, result: str) -> None:
        if name in _CHECKLIST_TOOLS and (items := parse_checklist(result)) is not None:
            self._console.print(checklist_renderable(items))
        else:
            self._console.print(Text(f"    ↳ {_preview(result)}", style="dim"))
        self._console.print()
