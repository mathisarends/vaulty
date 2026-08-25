# vault-gardener

uv workspace with two members:

| Member | Contents |
| --- | --- |
| `vaulty/` | The agent app — see [vaulty/README.md](vaulty/README.md) |
| `scheduler/` | Async scheduling primitives (heartbeats, reminders, cron jobs) — see [scheduler/README.md](scheduler/README.md) |

```bash
uv run vaulty
```

## Processes

| Command | What it is |
| --- | --- |
| `uv run vaulty` | Interactive chat session |
| `uv run vaulty-daemon` | Long-running process that owns the schedule |

The daemon reads its jobs from the `scheduler:` block in `vaulty.yml` and
reconciles them into `.vaulty/scheduler.db` on every start, so editing the
config and restarting is the way to change the schedule.
