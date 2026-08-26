"""Runs an agent and mirrors its conversation into a session store.

The `Agent` itself stays unaware of persistence: it takes messages in and
yields events out. `SessionRunner` wraps one agent plus the `Session` it is
writing to, so the CLI and the daemon get identical persistence behaviour
from the same object.
"""

import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Self
from uuid import UUID, uuid4

from runtime.messages import to_storage
from storage import Session, SessionRepository, SessionStatus, SessionTrigger
from vaulty.agent import Agent, AgentEvent, ContextCompacted

logger = logging.getLogger(__name__)

_TITLE_LENGTH = 60


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SessionRunner:
    def __init__(
        self,
        agent: Agent,
        repository: SessionRepository,
        session: Session,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._agent = agent
        self._repository = repository
        self._session = session
        self._clock = clock
        self._failed = False
        # Everything the agent already holds came out of `session`, so only
        # messages appended from here on still need to be written.
        self._persisted = len(agent.messages)

    @classmethod
    async def start(
        cls,
        agent: Agent,
        repository: SessionRepository,
        *,
        trigger: SessionTrigger,
        title: str | None = None,
        id: UUID | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> Self:
        """Open a fresh session for an agent with no restored history."""
        session = await repository.create(
            id or uuid4(), clock(), trigger=trigger, title=title
        )
        return cls(agent, repository, session, clock=clock)

    @classmethod
    async def reopen(
        cls,
        agent: Agent,
        repository: SessionRepository,
        session: Session,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> Self:
        """Continue a stored session whose history the agent already holds.

        Refuses a session another agent still owns - both would append to the
        same transcript.
        """
        if session.status is SessionStatus.RUNNING:
            raise ValueError(f"Session {session.id} is still running")
        session = session.with_status(SessionStatus.RUNNING)
        await repository.save(session)
        return cls(agent, repository, session, clock=clock)

    @property
    def session(self) -> Session:
        return self._session

    async def run(self, task: str) -> AsyncIterator[AgentEvent]:
        """Run a new task, persisting the conversation once it settles."""
        self._title_from(task)
        async for event in self._guard(self._agent.run(task)):
            yield event

    async def resume(self) -> AsyncIterator[AgentEvent]:
        """Continue from the restored history without adding a new task."""
        async for event in self._guard(self._agent.resume()):
            yield event

    async def compact(self) -> ContextCompacted | None:
        """Compact the agent's context now. See the known issue in `_save`."""
        return await self._agent.compact()

    async def finish(self) -> None:
        """Hand the session back, keeping the outcome of the last turn."""
        await self._save(
            SessionStatus.FAILED if self._failed else SessionStatus.FINISHED
        )

    async def _guard(
        self, events: AsyncIterator[AgentEvent]
    ) -> AsyncIterator[AgentEvent]:
        try:
            async for event in events:
                yield event
        except Exception:
            self._failed = True
            await self._save(SessionStatus.FAILED)
            raise
        self._failed = False
        await self._save(SessionStatus.RUNNING)

    async def _save(self, status: SessionStatus) -> None:
        # KNOWN ISSUE: compaction rewrites `agent.messages` in place, so the
        # messages it collapsed were already written and the ones replacing
        # them are appended alongside. The stored transcript then holds both
        # the original turns and their summary. Fixing this properly means an
        # append-only journal in `storage` (the DB as history, the agent's
        # list as the model's working window) - deliberately deferred.
        appended = to_storage(self._agent.messages[self._persisted :], self._clock())
        self._persisted = len(self._agent.messages)
        for message in appended:
            self._session = self._session.append(message)
        self._session = self._session.with_status(status)
        await self._repository.save(self._session)

    def _title_from(self, task: str) -> None:
        if self._session.title is not None:
            return
        single_line = " ".join(task.split())
        if len(single_line) > _TITLE_LENGTH:
            single_line = f"{single_line[: _TITLE_LENGTH - 1]}…"
        self._session = self._session.with_title(single_line)
