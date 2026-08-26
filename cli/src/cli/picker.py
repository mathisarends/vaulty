"""The `/resume` session picker: arrow keys over the recent sessions."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from rich.console import Console, Group
from rich.live import Live
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

import storage
from cli.keys import Key, read_key, supported

_TITLE_WIDTH = 56
_TRIGGER_STYLES = {
    storage.SessionTrigger.CLI: "cyan",
    storage.SessionTrigger.CRON: "magenta",
}
_STATUS_STYLES = {
    storage.SessionStatus.RUNNING: "yellow",
    storage.SessionStatus.FINISHED: "green",
    storage.SessionStatus.FAILED: "red",
}
_HINT = "↑↓ move · enter open · esc cancel"


def _age(created_at: datetime, now: datetime) -> str:
    seconds = (now - created_at).total_seconds()
    if seconds < 90:
        return "just now"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m ago"
    if minutes < 60 * 24:
        return f"{int(minutes // 60)}h ago"
    if minutes < 60 * 24 * 7:
        return f"{int(minutes // (60 * 24))}d ago"
    return created_at.astimezone().strftime("%d %b")


def _title(session: storage.Session) -> Text:
    text = Text(session.title or "untitled")
    text.truncate(_TITLE_WIDTH, overflow="ellipsis")
    return text


def sessions_renderable(
    sessions: Sequence[storage.Session], selected: int | None = None
) -> Padding:
    """The session list, with one row marked when a picker is driving it."""
    now = datetime.now(UTC)
    table = Table.grid(padding=(0, 2))
    for justify in ("left", "right", "left", "left", "left"):
        table.add_column(justify=justify)
    table.add_row(
        *(Text(header, style="dim") for header in ("", "#", "when", "start", "state"))
    )
    for number, session in enumerate(sessions, start=1):
        chosen = selected == number - 1
        table.add_row(
            Text("›" if chosen else " ", style="bold cyan"),
            Text(str(number), style="bold cyan" if chosen else "dim"),
            Text(_age(session.created_at, now), style="dim"),
            Text(session.trigger.value, style=_TRIGGER_STYLES[session.trigger]),
            Text(session.status.value, style=_STATUS_STYLES[session.status]),
            _title(session),
        )
    if selected is None:
        return Padding(table, (0, 0, 1, 2))
    return Padding(Group(table, Text(_HINT, style="dim")), (0, 0, 1, 2))


def choose_session(
    console: Console,
    sessions: Sequence[storage.Session],
    *,
    read: Callable[[], Key] = read_key,
) -> storage.Session | None:
    """Let the user walk the list and open one. `None` if they cancel.

    Falls back to typing a number when there is no terminal to read keys
    from - a piped stdin, or a test driving the console.
    """
    if not supported():
        return _by_number(console, sessions)

    index = 0
    with Live(
        sessions_renderable(sessions, index),
        console=console,
        transient=True,
        auto_refresh=False,
    ) as live:
        while True:
            match read():
                case Key.ENTER:
                    return sessions[index]
                case Key.CANCEL:
                    return None
                case Key.UP:
                    index = (index - 1) % len(sessions)
                case Key.DOWN:
                    index = (index + 1) % len(sessions)
                case Key.OTHER:
                    continue
            live.update(sessions_renderable(sessions, index), refresh=True)


def _by_number(
    console: Console, sessions: Sequence[storage.Session]
) -> storage.Session | None:
    console.print(sessions_renderable(sessions))
    try:
        answer = console.input(
            f"[dim]resume which? [1-{len(sessions)}, enter to cancel][/dim] [dim]›[/] "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return None
    return by_number(console, sessions, answer)


def by_number(
    console: Console, sessions: Sequence[storage.Session], answer: str
) -> storage.Session | None:
    """Resolve a typed row number, complaining about anything else."""
    if not answer:
        return None
    if not answer.isdigit() or not 1 <= int(answer) <= len(sessions):
        console.print(f"[yellow]No session {answer!r} in the list.[/yellow]")
        return None
    return sessions[int(answer) - 1]
