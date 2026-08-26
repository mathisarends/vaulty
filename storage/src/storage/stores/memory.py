from datetime import datetime
from uuid import UUID

from storage.models import Session, SessionTrigger
from storage.ports import SessionRepository


class MemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    async def create(
        self,
        id: UUID,
        created_at: datetime,
        *,
        trigger: SessionTrigger,
        title: str | None = None,
    ) -> Session:
        if id in self._sessions:
            raise ValueError(f"Session {id!r} already exists")
        session = Session(id=id, created_at=created_at, trigger=trigger, title=title)
        self._sessions[id] = session
        return session

    async def save(self, session: Session) -> None:
        if session.id not in self._sessions:
            raise KeyError(f"Session {session.id!r} does not exist")
        self._sessions[session.id] = session

    async def get(self, id: UUID) -> Session | None:
        return self._sessions.get(id)

    async def list(self, *, limit: int | None = None) -> tuple[Session, ...]:
        ordered = sorted(
            self._sessions.values(), key=lambda s: s.created_at, reverse=True
        )
        if limit is not None:
            ordered = ordered[:limit]
        return tuple(ordered)

    async def delete(self, id: UUID) -> bool:
        return self._sessions.pop(id, None) is not None
