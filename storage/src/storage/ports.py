from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from storage.models import Session, SessionTrigger


class SessionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        id: UUID,
        created_at: datetime,
        *,
        trigger: SessionTrigger,
        title: str | None = None,
    ) -> Session: ...

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Persists the session's current title and messages in full."""
        ...

    @abstractmethod
    async def get(self, id: UUID) -> Session | None: ...

    @abstractmethod
    async def list(self, *, limit: int | None = None) -> tuple[Session, ...]:
        """Most recently created first, optionally capped to `limit`."""
        ...

    @abstractmethod
    async def delete(self, id: UUID) -> bool: ...
