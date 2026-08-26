from datetime import datetime
from uuid import UUID

from transcripts.models import Transcript
from transcripts.ports import TranscriptRepository


class MemoryTranscriptRepository(TranscriptRepository):
    def __init__(self) -> None:
        self._transcripts: dict[UUID, Transcript] = {}

    async def create(
        self,
        id: UUID,
        created_at: datetime,
        *,
        title: str | None = None,
    ) -> Transcript:
        if id in self._transcripts:
            raise ValueError(f"Transcript {id!r} already exists")
        transcript = Transcript(id=id, created_at=created_at, title=title)
        self._transcripts[id] = transcript
        return transcript

    async def save(self, transcript: Transcript) -> None:
        if transcript.id not in self._transcripts:
            raise KeyError(f"Transcript {transcript.id!r} does not exist")
        self._transcripts[transcript.id] = transcript

    async def get(self, id: UUID) -> Transcript | None:
        return self._transcripts.get(id)

    async def list(self, *, limit: int | None = None) -> tuple[Transcript, ...]:
        ordered = sorted(
            self._transcripts.values(), key=lambda t: t.created_at, reverse=True
        )
        if limit is not None:
            ordered = ordered[:limit]
        return tuple(ordered)

    async def delete(self, id: UUID) -> bool:
        return self._transcripts.pop(id, None) is not None
