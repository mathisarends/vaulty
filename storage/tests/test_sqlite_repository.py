import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from storage import (
    AssistantMessage,
    SessionStatus,
    SessionTrigger,
    SqliteSessionRepository,
    ToolCall,
    ToolCallMessage,
    UserMessage,
)


def test_sqlite_repository_persists_session_across_reopen(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = tmp_path / "sessions.db"
        now = datetime.now(UTC)
        id = uuid4()
        other_id = uuid4()

        repository = SqliteSessionRepository(database)
        session = await repository.create(
            id, now, trigger=SessionTrigger.CLI, title="Tend the vault"
        )
        session = session.append(UserMessage(content="hi", created_at=now))
        session = session.append(
            AssistantMessage(
                tool_calls=(ToolCall(id="1", name="list_notes", arguments="{}"),),
                created_at=now + timedelta(seconds=1),
            )
        )
        session = session.append(
            ToolCallMessage(
                tool_call_id="1",
                content="12 notes",
                created_at=now + timedelta(seconds=2),
            )
        )
        await repository.save(session)

        await repository.create(
            other_id, now + timedelta(seconds=3), trigger=SessionTrigger.CRON
        )

        reopened = SqliteSessionRepository(database)
        stored = await reopened.get(id)
        assert stored is not None
        assert stored.title == "Tend the vault"
        assert stored.trigger == SessionTrigger.CLI
        assert stored.created_at == now

        user, assistant, tool = stored.messages
        assert isinstance(user, UserMessage) and user.content == "hi"
        assert isinstance(assistant, AssistantMessage)
        assert assistant.tool_calls == (
            ToolCall(id="1", name="list_notes", arguments="{}"),
        )
        assert isinstance(tool, ToolCallMessage)
        assert tool.tool_call_id == "1"
        assert tool.content == "12 notes"

        assert [s.id for s in await reopened.list()] == [other_id, id]
        assert [s.id for s in await reopened.list(limit=1)] == [other_id]

        assert await reopened.delete(id)
        assert await reopened.get(id) is None
        assert not await reopened.delete(id)

    asyncio.run(scenario())


def test_save_without_create_raises(tmp_path: Path) -> None:
    async def scenario() -> None:
        repository = SqliteSessionRepository(tmp_path / "sessions.db")
        id = uuid4()
        session = await repository.create(
            id, datetime.now(UTC), trigger=SessionTrigger.CLI
        )
        await repository.delete(id)

        with pytest.raises(KeyError, match="does not exist"):
            await repository.save(session)

    asyncio.run(scenario())


def test_status_starts_running_and_survives_save(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = tmp_path / "sessions.db"
        id = uuid4()

        repository = SqliteSessionRepository(database)
        session = await repository.create(
            id, datetime.now(UTC), trigger=SessionTrigger.CRON
        )
        assert session.status is SessionStatus.RUNNING

        await repository.save(session.with_status(SessionStatus.FINISHED))

        reopened = await SqliteSessionRepository(database).get(id)
        assert reopened is not None
        assert reopened.status is SessionStatus.FINISHED

    asyncio.run(scenario())
