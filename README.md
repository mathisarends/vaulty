# vaulty

Vaulty is an agent that tends an [Obsidian](https://obsidian.md) vault. It runs
interactively from a terminal, or nightly on a cron schedule, and gets file
access to the vault plus a shell that runs inside a locked-down Docker
container.

```text
Vaulty interactive agent
Workspace  C:\obsidian\database
Model      gpt-5.6-luna

you › plan und erledige zwei Schritte

  • add_todos  items="['Notiz anlegen', 'Ergebnis prüfen']"
    Checklist
    [ ]  1  Notiz anlegen
    [ ]  2  Ergebnis prüfen

  • check_off  item='1'
    Checklist
    [x]  1  Notiz anlegen
    [ ]  2  Ergebnis prüfen
```

## Quickstart

```bash
uv run vaulty                 # interactive chat session
uv run vaulty --root PATH     # override the configured workspace for one session
uv run vaulty-daemon          # long-running process that owns the cron schedule
```

Local commands in the CLI: `/help`, `/clear`, `/compact`, `/resume`, `/exit`.
`/resume` lists the ten most recent sessions - cron and interactive alike -
and replays the picked transcript so the conversation reads as if it never
stopped.

Requires a logged-in Codex CLI (`~/.codex/auth.json`) and a running Docker
daemon. Build the sandbox image once with `./scripts/build-sandbox.sh`.

## Configuration

Settings live in `vaulty.yml`: the vault path (`root`), the model and
reasoning effort, context-compaction thresholds, the cron schedule, where
session/scheduler state is stored, and sandbox limits (image, timeout,
memory, CPU, network). A GitHub token for the agent's own `git`/`gh` use goes
in a local `.env` (`GH_TOKEN=...`), never in `vaulty.yml` or the image.

```yaml
scheduler:
  tasks:
    - id: daily-gardening
      name: daily
      cron: "0 4 * * *"
      prompt: Read Daily Review Instructions and follow the instructions
```

The daemon reconciles that block into `.vaulty/scheduler.db` on every start,
so editing the config and restarting is how you change the schedule.

## Workspace layout

This is a `uv` workspace of seven packages. `vaulty` is the agent core;
`cli` and `daemon` are the two frontends over it; `runtime`, `storage`,
`scheduler`, and `github` are runtime-agnostic building blocks each package
has its own README for.

| Package | What it is |
| --- | --- |
| [`vaulty/`](vaulty/README.md) | The agent: LLM client, Docker sandbox, file/shell/todo tools, system prompt, context compaction |
| [`cli/`](cli/README.md) | Interactive terminal client - chat loop, streamed answers, tool activity, `/resume` session picker |
| [`daemon/`](daemon/README.md) | Long-running process that owns the cron schedule and runs the agent on each due task |
| [`runtime/`](runtime/README.md) | Glue between the agent and session storage, shared by both frontends |
| [`storage/`](storage/README.md) | Async SQLite-backed storage for agent conversation sessions |
| [`scheduler/`](scheduler/README.md) | In-memory async scheduler (interval + cron triggers), independent of agent and storage |
| [`github/`](github/README.md) | Minimal async GitHub REST client for PR status, reviews, and comments |

### How a run flows

The CLI and the daemon each build an `Agent` and hand it to a
`runtime.SessionRunner`, which persists every turn through `storage` into
`.vaulty/sessions.db` - one database, read by both frontends. A cron run and
an interactive session are indistinguishable in `/resume` except for their
trigger.

The daemon holds the workspace and the sandbox open for its whole lifetime;
each due task still gets a fresh agent, so no run inherits a previous run's
state. On start, any cron session an earlier daemon left `running` - e.g.
after a hard kill - is marked `failed`, so it doesn't block resumption
forever. Interactive sessions are never touched this way, since one of them
may belong to a terminal that's still open.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```

Each package under the workspace has its own `pyproject.toml` and tests; see
its README for details specific to that package.
