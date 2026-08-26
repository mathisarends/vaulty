import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from storage import AssistantMessage, MemorySessionRepository, UserMessage


def test_create_append_save_round_trips() -> None:
    async def scenario() -> None:
        repository = MemorySessionRepository()
        id = uuid4()
        now = datetime.now(UTC)

        assert await repository.get(id) is None

        session = await repository.create(
            id, now, trigger="cli", title="Tend the vault"
        )
        session = session.append(UserMessage(content="hi", created_at=now))
        session = session.append(
            AssistantMessage(content="hello", created_at=now + timedelta(seconds=1))
        )
        await repository.save(session)

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
        repository = MemorySessionRepository()
        id = uuid4()
        session = await repository.create(id, datetime.now(UTC), trigger="cli")
        await repository.delete(id)

        with pytest.raises(KeyError, match="does not exist"):
            await repository.save(session)

    asyncio.run(scenario())


def test_create_twice_raises() -> None:
    async def scenario() -> None:
        repository = MemorySessionRepository()
        id = uuid4()
        now = datetime.now(UTC)

        await repository.create(id, now, trigger="cli")
        with pytest.raises(ValueError, match="already exists"):
            await repository.create(id, now, trigger="cli")

    asyncio.run(scenario())


def test_list_orders_by_created_at_desc_and_respects_limit() -> None:
    async def scenario() -> None:
        repository = MemorySessionRepository()
        now = datetime.now(UTC)

        older = await repository.create(uuid4(), now, trigger="cli")
        newer = await repository.create(
            uuid4(), now + timedelta(seconds=1), trigger="cron"
        )

        assert await repository.list() == (newer, older)
        assert await repository.list(limit=1) == (newer,)

    asyncio.run(scenario())
