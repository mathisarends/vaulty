# storage

Async storage for agent conversation sessions, typed as a normal LLM
chat: `UserMessage`, `AssistantMessage` (with `tool_calls`), and
`ToolCallMessage` (a tool's result).

`Session` is an immutable aggregate: `.append(message)` returns a new
`Session` with the message added, and `save()` persists whatever the
session currently holds (title and messages) in one shot.

```python
repository = SqliteSessionRepository(db_path)

session = await repository.create(
    uuid4(), datetime.now(UTC), trigger=SessionTrigger.CLI, title="Tend the vault"
)
session = session.append(
    UserMessage(content="tidy up the vault", created_at=datetime.now(UTC))
)
session = session.append(
    AssistantMessage(
        tool_calls=(ToolCall(id="1", name="list_notes", arguments="{}"),),
        created_at=datetime.now(UTC),
    )
)
session = session.append(
    ToolCallMessage(tool_call_id="1", content="12 notes", created_at=datetime.now(UTC))
)
await repository.save(session)

again = await repository.get(session.id)
recent = await repository.list(limit=20)  # most recently created first
```

- `SessionRepository` — the port: async `create`/`save`/`get`/`list`/`delete`.
  `create` registers a session (with its trigger, title, and creation time)
  and returns it; `save` raises `KeyError` if the session doesn't exist yet.
- `SessionTrigger` (`CRON` | `CLI`) records what started the session.
- `MemorySessionRepository` — for tests/ephemeral processes.
- `SqliteSessionRepository` — for durable storage. Serializes the three
  message types itself, so no host-provided codec is needed.

## Dependencies

None beyond the standard library for `MemorySessionRepository`;
`SqliteSessionRepository` needs `aiosqlite`.
