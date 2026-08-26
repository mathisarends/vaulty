# vaulty

A small agentic loop built on [mm-agenttoolkit](https://pypi.org/project/mm-agenttoolkit/)
(tools, dependency injection, sandbox) and [py-llmify](https://pypi.org/project/py-llmify/)
(chat model). The agent gets file access to one workspace and a shell that runs
inside a locked-down Docker container.

## Layout

| Modul | Inhalt |
| --- | --- |
| `vaulty/llm.py` | `ChatCodex` (gpt-5.6-luna) via Codex-CLI-Login, konfigurierbar über `VAULTY_*` env vars |
| `vaulty/sandbox.py` | `DockerSandbox`: read-only rootfs, workspace bind-mounted at `/workspace` |
| `vaulty/tools/` | Semantisch getrennte File-, Shell-, Skill- und Todo-Tools sowie Dependency Wiring |
| `vaulty/agents.py` | `DOT.VAULTY/` im Workspace: `AGENTS.md` + Skills-Registry aus dem agenttoolkit |
| `vaulty/agent/` | Agent loop, `SystemPrompt` (Basistext + Workspace-Sektionen) und loss-aware context compaction |
| `vaulty/cli/` | Terminal client: commands, streamed answers, tool activity and checklist rendering |
| `vaulty/main.py` | Backward-compatible shim for `python -m vaulty.main` |

## Usage

```bash
uv run vaulty
```

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

Local commands are `/help`, `/clear`, and `/exit`. Use `--root PATH` to override
the configured workspace for one session and `--no-color` for plain output.

```python
from vaulty import Agent, Dependencies, TextDelta, ToolStarted, build_llm, build_tools

async for event in agent.run("summarise the repo layout"):
    match event:
        case TextDelta(text):
            print(text, end="")
        case ToolStarted(name, arguments):
            print(name, arguments)
```

Existing conversation history can be restored when the agent is created, or
injected immediately before a later run. Injected messages are placed before an
optional new user task:

```python
from llmify import AssistantMessage, UserMessage

history = [
    UserMessage(content="Remember this repository."),
    AssistantMessage(content="I will."),
]
agent = Agent(llm, tools, messages=history)

async for event in agent.run("Continue where we left off"):
    ...

# A caller may also provide the next message and continue without adding a task.
async for event in agent.run(messages=[UserMessage(content="Now inspect tests")]):
    ...
```

The workspace defaults to the Obsidian vault at `C:\obsidian\database`;
override it with `--root` or the `VAULTY_ROOT` environment variable.

Requires a logged-in Codex CLI (`~/.codex/auth.json`) and a running Docker daemon.
Settings: `VAULTY_MODEL`, `VAULTY_REASONING_EFFORT`, `VAULTY_TIMEOUT_SECONDS`,
`VAULTY_MAX_RETRIES` (env or `.env`).

## Workspace configuration (`DOT.VAULTY/`)

Where a code repo keeps its agent setup next to the source, Vaulty keeps it
inside the workspace itself — by default `<root>/DOT.VAULTY/`, so in the Obsidian
vault at `C:\obsidian\database\DOT.VAULTY\`:

```text
DOT.VAULTY/
  AGENTS.md                    standing instructions, loaded into every system prompt
  skills/
    weekly-review/SKILL.md     one directory per skill, name must match the directory
```

Deliberately not a dot-folder: Obsidian hides those from the vault, so the notes
app could neither show nor edit them. The directory is created on start when
missing, together with an `AGENTS.md` template. Change the location in
`vaulty.yml`:

```yaml
agents:
  directory: DOT.VAULTY
  skills_dirname: skills
  instructions_filename: AGENTS.md
```

Skills are discovered by `agenttoolkit.Skills`. Their names and descriptions go
into the system prompt; the agent loads a full skill with the `skill` tool and
re-reads the catalogue with `list_skills`, so skills it writes during a session
are usable immediately.

## Context compaction

Vaulty compacts older conversation turns before the active model approaches its
context limit. It resolves the window from the model profiles in `vaulty/llm.py`.
Set `compaction.context_window_tokens` in `vaulty.yml` (or `vaulty.yaml`) when an explicit override
is needed. Recent complete turns remain verbatim; older history is replaced with
a model-generated working checkpoint. Compaction can repeat during long sessions.

## Git and GitHub

Build the sandbox image once (Git is installed by the `Dockerfile`):

```sh
./scripts/build-sandbox.sh
```

The agent can use Git and GitHub CLI directly in `bash`. The configured workspace
is mounted at `/workspace`, so it can commit and push its worktree and create a
pull request from the same container.

Put a fine-grained GitHub token in the local `.env` file:

```dotenv
GH_TOKEN=github_pat_...
```

Vaulty loads `.env` without overriding variables already exported by the host,
then passes `GH_TOKEN` into the container. The token is not stored in the image
or in `vaulty.yml`; `.env` is ignored by Git. Use a fine-grained token with only
the repository permissions required for pushing branches and creating pull
requests. Container network access must be enabled in `vaulty.yml`.
