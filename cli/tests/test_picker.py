from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from rich.console import Console

import storage
from cli.keys import Key
from cli.picker import choose_session, sessions_renderable


def session(minutes: int, title: str, **kwargs) -> storage.Session:
    return storage.Session(
        id=uuid4(),
        created_at=datetime.now(UTC) - timedelta(minutes=minutes),
        trigger=kwargs.get("trigger", storage.SessionTrigger.CLI),
        status=kwargs.get("status", storage.SessionStatus.FINISHED),
        title=title,
    )


def keys(*pressed: Key):
    stream: Iterator[Key] = iter(pressed)

    def read() -> Key:
        return next(stream)

    return read


@pytest.fixture
def interactive(monkeypatch: pytest.MonkeyPatch) -> Console:
    monkeypatch.setattr("cli.picker.supported", lambda: True)
    return Console(file=StringIO(), no_color=True, width=100, force_terminal=True)


def test_enter_opens_the_highlighted_session(interactive) -> None:
    sessions = [session(5, "first"), session(90, "second")]

    chosen = choose_session(interactive, sessions, read=keys(Key.DOWN, Key.ENTER))

    assert chosen is sessions[1]


def test_the_selection_wraps_around_both_ends(interactive) -> None:
    sessions = [session(5, "first"), session(90, "second"), session(200, "third")]

    chosen = choose_session(interactive, sessions, read=keys(Key.UP, Key.ENTER))

    assert chosen is sessions[2]


def test_escape_cancels_without_opening_anything(interactive) -> None:
    sessions = [session(5, "first")]

    assert choose_session(interactive, sessions, read=keys(Key.CANCEL)) is None


def test_unknown_keys_are_ignored(interactive) -> None:
    sessions = [session(5, "first"), session(90, "second")]

    chosen = choose_session(
        interactive, sessions, read=keys(Key.OTHER, Key.DOWN, Key.OTHER, Key.ENTER)
    )

    assert chosen is sessions[1]


def test_a_piped_stdin_falls_back_to_typing_a_number(monkeypatch) -> None:
    monkeypatch.setattr("cli.picker.supported", lambda: False)
    sessions = [session(5, "first"), session(90, "second")]

    class Typed(Console):
        def input(self, *args, **kwargs) -> str:
            return "2"

    chosen = choose_session(Typed(file=StringIO(), no_color=True, width=100), sessions)

    assert chosen is sessions[1]


def test_the_table_shows_when_trigger_and_state() -> None:
    output = StringIO()
    console = Console(file=output, no_color=True, width=100)
    console.print(
        sessions_renderable(
            [
                session(
                    8,
                    "nightly gardening",
                    trigger=storage.SessionTrigger.CRON,
                    status=storage.SessionStatus.RUNNING,
                )
            ]
        )
    )

    rendered = output.getvalue()
    assert "8m ago" in rendered
    assert "cron" in rendered
    assert "running" in rendered
    assert "nightly gardening" in rendered


def test_the_marker_follows_the_selection() -> None:
    output = StringIO()
    console = Console(file=output, no_color=True, width=100)
    console.print(
        sessions_renderable([session(5, "first"), session(90, "second")], selected=1)
    )

    lines = [line for line in output.getvalue().splitlines() if line.strip()]
    assert "›" in next(line for line in lines if "second" in line)
    assert "›" not in next(line for line in lines if "first" in line)
