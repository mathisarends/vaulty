import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from transcripts import AssistantMessage, MemoryTranscriptRepository, UserMessage


def test_create_append_save_round_trips() -> None:
    async def scenario() -> None:
        repository = MemoryTranscriptRepository()
        id = uuid4()
        now = datetime.now(UTC)

        assert await repository.get(id) is None

        transcript = await repository.create(id, now, title="Tend the vault")
        transcript = transcript.append(UserMessage(content="hi", created_at=now))
        transcript = transcript.append(
            AssistantMessage(content="hello", created_at=now + timedelta(seconds=1))
        )
        await repository.save(transcript)

        stored = await repository.get(id)
        assert stored is not None
        assert stored.title == "Tend the vault"
        assert stored.created_at == now
        assert [message.content for message in stored.messages] == ["hi", "hello"]
        assert await repository.list() == (stored,)

        assert await repository.delete(id)
        assert not await repository.delete(id)
        assert await repository.get(id) is None

    asyncio.run(scenario())


def test_save_without_create_raises() -> None:
    async def scenario() -> None:
        repository = MemoryTranscriptRepository()
        id = uuid4()
        transcript = await repository.create(id, datetime.now(UTC))
        await repository.delete(id)

        with pytest.raises(KeyError, match="does not exist"):
            await repository.save(transcript)

    asyncio.run(scenario())


def test_create_twice_raises() -> None:
    async def scenario() -> None:
        repository = MemoryTranscriptRepository()
        id = uuid4()
        now = datetime.now(UTC)

        await repository.create(id, now)
        with pytest.raises(ValueError, match="already exists"):
            await repository.create(id, now)

    asyncio.run(scenario())


def test_list_orders_by_created_at_desc_and_respects_limit() -> None:
    async def scenario() -> None:
        repository = MemoryTranscriptRepository()
        now = datetime.now(UTC)

        older = await repository.create(uuid4(), now)
        newer = await repository.create(uuid4(), now + timedelta(seconds=1))

        assert await repository.list() == (newer, older)
        assert await repository.list(limit=1) == (newer,)

    asyncio.run(scenario())
