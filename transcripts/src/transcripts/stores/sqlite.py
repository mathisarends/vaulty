import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import aiosqlite

from transcripts.models import (
    AssistantMessage,
    ChatMessage,
    ToolCall,
    ToolCallMessage,
    Transcript,
    UserMessage,
)
from transcripts.ports import TranscriptRepository

_CREATE_TRANSCRIPTS_TABLE = """
CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL
)
"""
_CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS transcript_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id TEXT NOT NULL,
    role TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""
_CREATE_MESSAGES_INDEX = """
CREATE INDEX IF NOT EXISTS transcript_messages_transcript_id_idx
ON transcript_messages (transcript_id)
"""


class SqliteTranscriptRepository(TranscriptRepository):
    def __init__(self, database: str | Path) -> None:
        self._database = database

    async def create(
        self,
        id: UUID,
        created_at: datetime,
        *,
        title: str | None = None,
    ) -> Transcript:
        query = "INSERT INTO transcripts (id, title, created_at) VALUES (?, ?, ?)"
        async with self._connection() as connection:
            try:
                await connection.execute(
                    query, (str(id), title, created_at.astimezone(UTC).isoformat())
                )
                await connection.commit()
            except aiosqlite.IntegrityError as error:
                raise ValueError(f"Transcript {id!r} already exists") from error
        return Transcript(id=id, created_at=created_at, title=title)

    async def save(self, transcript: Transcript) -> None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "UPDATE transcripts SET title = ?, created_at = ? WHERE id = ?",
                (
                    transcript.title,
                    transcript.created_at.astimezone(UTC).isoformat(),
                    str(transcript.id),
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Transcript {transcript.id!r} does not exist")

            await connection.execute(
                "DELETE FROM transcript_messages WHERE transcript_id = ?",
                (str(transcript.id),),
            )
            for message in transcript.messages:
                await connection.execute(
                    """
                    INSERT INTO transcript_messages
                        (transcript_id, role, data, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        str(transcript.id),
                        message.role,
                        _encode_message(message),
                        message.created_at.astimezone(UTC).isoformat(),
                    ),
                )
            await connection.commit()

    async def get(self, id: UUID) -> Transcript | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT title, created_at FROM transcripts WHERE id = ?", (str(id),)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            messages = await self._fetch_messages(connection, id)
        return _build_transcript(id, row, messages)

    async def list(self, *, limit: int | None = None) -> tuple[Transcript, ...]:
        query = (
            "SELECT id, title, created_at FROM transcripts "
            "ORDER BY created_at DESC, id DESC"
        )
        params: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)

        async with self._connection() as connection:
            cursor = await connection.execute(query, params)
            rows = await cursor.fetchall()
            transcripts = []
            for row in rows:
                transcript_id = UUID(cast(str, row["id"]))
                messages = await self._fetch_messages(connection, transcript_id)
                transcripts.append(_build_transcript(transcript_id, row, messages))
        return tuple(transcripts)

    async def delete(self, id: UUID) -> bool:
        async with self._connection() as connection:
            await connection.execute(
                "DELETE FROM transcript_messages WHERE transcript_id = ?", (str(id),)
            )
            cursor = await connection.execute(
                "DELETE FROM transcripts WHERE id = ?", (str(id),)
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def _fetch_messages(
        self, connection: aiosqlite.Connection, id: UUID
    ) -> tuple[ChatMessage, ...]:
        cursor = await connection.execute(
            """
            SELECT role, data, created_at FROM transcript_messages
            WHERE transcript_id = ?
            ORDER BY id
            """,
            (str(id),),
        )
        rows = await cursor.fetchall()
        return tuple(_decode_message(row) for row in rows)

    @asynccontextmanager
    async def _connection(self) -> AsyncGenerator[aiosqlite.Connection]:
        async with aiosqlite.connect(self._database) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("PRAGMA busy_timeout = 5000")
            await connection.execute(_CREATE_TRANSCRIPTS_TABLE)
            await connection.execute(_CREATE_MESSAGES_TABLE)
            await connection.execute(_CREATE_MESSAGES_INDEX)
            await connection.commit()
            yield connection


def _build_transcript(
    id: UUID, row: aiosqlite.Row, messages: tuple[ChatMessage, ...]
) -> Transcript:
    return Transcript(
        id=id,
        title=cast(str | None, row["title"]),
        created_at=datetime.fromisoformat(cast(str, row["created_at"])),
        messages=messages,
    )


def _encode_message(message: ChatMessage) -> str:
    match message:
        case UserMessage(content=content):
            data: dict[str, object] = {"content": content}
        case AssistantMessage(content=content, tool_calls=tool_calls):
            data = {
                "content": content,
                "tool_calls": [
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in tool_calls
                ],
            }
        case ToolCallMessage(tool_call_id=tool_call_id, content=content):
            data = {"tool_call_id": tool_call_id, "content": content}
    return json.dumps(data, separators=(",", ":"))


def _decode_message(row: aiosqlite.Row) -> ChatMessage:
    role = cast(str, row["role"])
    data = cast(dict[str, object], json.loads(cast(str, row["data"])))
    created_at = datetime.fromisoformat(cast(str, row["created_at"]))

    match role:
        case "user":
            return UserMessage(
                content=cast(str, data["content"]), created_at=created_at
            )
        case "assistant":
            tool_calls = tuple(
                ToolCall(id=call["id"], name=call["name"], arguments=call["arguments"])
                for call in cast(list[dict[str, str]], data["tool_calls"])
            )
            return AssistantMessage(
                content=cast(str | None, data["content"]),
                tool_calls=tool_calls,
                created_at=created_at,
            )
        case "tool":
            return ToolCallMessage(
                tool_call_id=cast(str, data["tool_call_id"]),
                content=cast(str, data["content"]),
                created_at=created_at,
            )
        case _:
            raise ValueError(f"Unknown message role: {role!r}")
