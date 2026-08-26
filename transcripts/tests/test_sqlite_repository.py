import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from transcripts import (
    AssistantMessage,
    SqliteTranscriptRepository,
    ToolCall,
    ToolCallMessage,
    UserMessage,
)


def test_sqlite_repository_persists_transcript_across_reopen(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = tmp_path / "transcripts.db"
        now = datetime.now(UTC)
        id = uuid4()
        other_id = uuid4()

        repository = SqliteTranscriptRepository(database)
        transcript = await repository.create(id, now, title="Tend the vault")
        transcript = transcript.append(UserMessage(content="hi", created_at=now))
        transcript = transcript.append(
            AssistantMessage(
                tool_calls=(ToolCall(id="1", name="list_notes", arguments="{}"),),
                created_at=now + timedelta(seconds=1),
            )
        )
        transcript = transcript.append(
            ToolCallMessage(
                tool_call_id="1",
                content="12 notes",
                created_at=now + timedelta(seconds=2),
            )
        )
        await repository.save(transcript)

        await repository.create(other_id, now + timedelta(seconds=3))

        reopened = SqliteTranscriptRepository(database)
        stored = await reopened.get(id)
        assert stored is not None
        assert stored.title == "Tend the vault"
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

        assert [t.id for t in await reopened.list()] == [other_id, id]
        assert [t.id for t in await reopened.list(limit=1)] == [other_id]

        assert await reopened.delete(id)
        assert await reopened.get(id) is None
        assert not await reopened.delete(id)

    asyncio.run(scenario())


def test_save_without_create_raises(tmp_path: Path) -> None:
    async def scenario() -> None:
        repository = SqliteTranscriptRepository(tmp_path / "transcripts.db")
        id = uuid4()
        transcript = await repository.create(id, datetime.now(UTC))
        await repository.delete(id)

        with pytest.raises(KeyError, match="does not exist"):
            await repository.save(transcript)

    asyncio.run(scenario())
