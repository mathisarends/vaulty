# runtime

The glue between `vaulty` (the agent) and `storage` (the session store).
Both frontends - `cli` and `daemon` - build their agent, hand it to a
`SessionRunner`, and get identical persistence behaviour.

```python
agent = Agent(llm, tools)
runner = await SessionRunner.start(agent, repository, trigger=SessionTrigger.CLI)

async for event in runner.run("tidy up the vault"):
    ...  # render as usual

await runner.finish()
```

Resuming works the same way, except the agent is built from the stored
transcript first:

```python
session = await repository.get(id)
agent = Agent(llm, tools, messages=to_llm(session.messages))
runner = await SessionRunner.reopen(agent, repository, session)
```

`reopen` refuses a session that is still `RUNNING`, since two agents
appending to one transcript would corrupt it.

## What is translated, and what is not

`messages.to_storage` / `messages.to_llm` map between the two message
types. The system prompt is deliberately *not* stored: resuming a session
renders today's prompt rather than restoring a stale one, which matters
for a cron session picked up weeks later.

The runner writes after each turn and only appends what the agent gained
since the last write, so timestamps of older messages stay put.

## Known issue: compaction duplicates history

Compaction rewrites the agent's message list in place - older turns are
replaced by a generated checkpoint. The runner sees this as new messages
and appends them, so the stored transcript ends up holding both the
original turns and their summary.

The proper fix is an append-only journal in `storage`: the database is the
history for display, the agent's list is the model's working window. That
is deliberately deferred.
