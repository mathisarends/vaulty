from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from transcripts.models import Transcript


class TranscriptRepository(ABC):
    @abstractmethod
    async def create(
        self,
        id: UUID,
        created_at: datetime,
        *,
        title: str | None = None,
    ) -> Transcript: ...

    @abstractmethod
    async def save(self, transcript: Transcript) -> None:
        """Persists the transcript's current title and messages in full."""
        ...

    @abstractmethod
    async def get(self, id: UUID) -> Transcript | None: ...

    @abstractmethod
    async def list(self, *, limit: int | None = None) -> tuple[Transcript, ...]:
        """Most recently created first, optionally capped to `limit`."""
        ...

    @abstractmethod
    async def delete(self, id: UUID) -> bool: ...
