# transcripts

Async storage for agent conversation transcripts, typed as a normal LLM
chat: `UserMessage`, `AssistantMessage` (with `tool_calls`), and
`ToolCallMessage` (a tool's result).

`Transcript` is an immutable aggregate: `.append(message)` returns a new
`Transcript` with the message added, and `save()` persists whatever the
transcript currently holds (title and messages) in one shot.

```python
repository = SqliteTranscriptRepository(db_path)

transcript = await repository.create(uuid4(), datetime.now(UTC), title="Tend the vault")
transcript = transcript.append(
    UserMessage(content="tidy up the vault", created_at=datetime.now(UTC))
)
transcript = transcript.append(
    AssistantMessage(
        tool_calls=(ToolCall(id="1", name="list_notes", arguments="{}"),),
        created_at=datetime.now(UTC),
    )
)
transcript = transcript.append(
    ToolCallMessage(tool_call_id="1", content="12 notes", created_at=datetime.now(UTC))
)
await repository.save(transcript)

again = await repository.get(transcript.id)
recent = await repository.list(limit=20)  # most recently created first
```

- `TranscriptRepository` — the port: async `create`/`save`/`get`/`list`/`delete`.
  `create` registers a transcript (with its title and creation time) and
  returns it; `save` raises `KeyError` if the transcript doesn't exist yet.
- `MemoryTranscriptRepository` — for tests/ephemeral processes.
- `SqliteTranscriptRepository` — for durable storage. Serializes the three
  message types itself, so no host-provided codec is needed.

## Dependencies

None beyond the standard library for `MemoryTranscriptRepository`;
`SqliteTranscriptRepository` needs `aiosqlite`.
