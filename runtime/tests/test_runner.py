from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import llmify
import pytest

from runtime import SessionRunner, to_llm
from storage import MemorySessionRepository, SessionStatus, SessionTrigger
from vaulty.agent import Agent, AgentEvent, TurnEnded


class StubAgent:
    """An agent that answers with a canned reply instead of calling a model."""

    def __init__(
        self, reply: str = "done", *, messages: Iterable[llmify.Message] = ()
    ) -> None:
        self.messages: list[llmify.Message] = [
            llmify.SystemMessage(content="you are vaulty"),
            *messages,
        ]
        self._reply = reply
        self.failure: Exception | None = None

    async def run(self, task: str) -> AsyncIterator[AgentEvent]:
        self.messages.append(llmify.UserMessage(content=task))
        async for event in self._answer():
            yield event

    async def resume(self) -> AsyncIterator[AgentEvent]:
        async for event in self._answer():
            yield event

    async def _answer(self) -> AsyncIterator[AgentEvent]:
        if self.failure is not None:
            raise self.failure
        self.messages.append(llmify.AssistantMessage(content=self._reply))
        yield TurnEnded(text=self._reply, steps=1)


def as_agent(stub: StubAgent) -> Agent:
    return cast(Agent, stub)


async def drain(events: AsyncIterator[AgentEvent]) -> list[AgentEvent]:
    return [event async for event in events]


async def test_a_turn_is_persisted_without_the_system_prompt() -> None:
    repository = MemorySessionRepository()
    runner = await SessionRunner.start(
        as_agent(StubAgent()), repository, trigger=SessionTrigger.CLI
    )

    await drain(runner.run("tidy up the vault"))
    await runner.finish()

    stored = await repository.get(runner.session.id)
    assert stored is not None
    assert [message.role for message in stored.messages] == ["user", "assistant"]
    assert stored.status is SessionStatus.FINISHED
    assert stored.trigger is SessionTrigger.CLI


async def test_the_first_task_becomes_the_title() -> None:
    repository = MemorySessionRepository()
    runner = await SessionRunner.start(
        as_agent(StubAgent()), repository, trigger=SessionTrigger.CLI
    )

    await drain(runner.run("tidy up   the vault"))
    await drain(runner.run("and now the inbox"))

    assert runner.session.title == "tidy up the vault"


async def test_a_long_first_task_is_truncated() -> None:
    repository = MemorySessionRepository()
    runner = await SessionRunner.start(
        as_agent(StubAgent()), repository, trigger=SessionTrigger.CLI
    )

    await drain(runner.run("word " * 40))

    title = runner.session.title
    assert title is not None
    assert len(title) == 60
    assert title.endswith("…")


async def test_a_second_turn_only_appends_what_is_new() -> None:
    repository = MemorySessionRepository()
    runner = await SessionRunner.start(
        as_agent(StubAgent()), repository, trigger=SessionTrigger.CLI
    )

    await drain(runner.run("first"))
    first = (await repository.get(runner.session.id)).messages
    await drain(runner.run("second"))
    second = (await repository.get(runner.session.id)).messages

    assert second[: len(first)] == first
    assert len(second) == 4


async def test_a_failing_turn_marks_the_session_failed() -> None:
    repository = MemorySessionRepository()
    agent = StubAgent()
    agent.failure = RuntimeError("the model went away")
    runner = await SessionRunner.start(
        as_agent(agent), repository, trigger=SessionTrigger.CRON
    )

    with pytest.raises(RuntimeError, match="went away"):
        await drain(runner.run("tidy up"))

    stored = await repository.get(runner.session.id)
    assert stored is not None
    assert stored.status is SessionStatus.FAILED
    assert [message.role for message in stored.messages] == ["user"]


async def test_reopen_continues_the_stored_transcript() -> None:
    repository = MemorySessionRepository()
    runner = await SessionRunner.start(
        as_agent(StubAgent()), repository, trigger=SessionTrigger.CRON
    )
    await drain(runner.run("nightly gardening"))
    await runner.finish()

    stored = await repository.get(runner.session.id)
    assert stored is not None
    resumed = StubAgent("carrying on", messages=to_llm(stored.messages))
    reopened = await SessionRunner.reopen(as_agent(resumed), repository, stored)
    await drain(reopened.run("what did you change?"))
    await reopened.finish()

    final = await repository.get(stored.id)
    assert final is not None
    assert [message.role for message in final.messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert final.title == "nightly gardening"


async def test_reopen_refuses_a_running_session() -> None:
    repository = MemorySessionRepository()
    session = await repository.create(
        uuid4(), datetime.now(UTC), trigger=SessionTrigger.CRON
    )

    with pytest.raises(ValueError, match="still running"):
        await SessionRunner.reopen(as_agent(StubAgent()), repository, session)
