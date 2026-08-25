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
| `vaulty/tools.py` | `Dependencies` provider + `read_file`, `write_file`, `edit_file`, `list_dir`, `glob`, `grep`, `bash` |
| `vaulty/agent.py` | The loop: stream → run tool calls → feed results back → repeat; emits `TextDelta`, `ToolStarted`, `ToolFinished`, `TurnEnded` |
| `main.py` | Terminal chat: streams the answer live and prints every tool call with its result |

## Usage

```bash
uv run python main.py
```

```text
you > leg eine notes.md an

Ich schaue mir das an.
• write_file(path='notes.md', content='hello world')
  wrote notes.md (11 chars)
Datei ist geschrieben.
```

```python
from vaulty import Agent, Dependencies, TextDelta, ToolStarted, build_llm, build_tools

async for event in agent.run("summarise the repo layout"):
    match event:
        case TextDelta(text):
            print(text, end="")
        case ToolStarted(name, arguments):
            print(name, arguments)
```

The workspace defaults to the Obsidian vault at `C:\obsidian\database`;
override it with `--root` or the `VAULTY_ROOT` environment variable.

Requires a logged-in Codex CLI (`~/.codex/auth.json`) and a running Docker daemon.
Settings: `VAULTY_MODEL`, `VAULTY_REASONING_EFFORT`, `VAULTY_TIMEOUT_SECONDS`,
`VAULTY_MAX_RETRIES` (env or `.env`).

## Git and GitHub

Build the sandbox image once (Git is installed by the `Dockerfile`):

```sh
./scripts/build-sandbox.sh
```

The agent can use Git and GitHub CLI directly in `bash`. The configured workspace
is mounted at `/workspace`, so it can commit and push its worktree and create a
pull request from the same container.

Provide a fine-grained GitHub token to the Vaulty host process:

```powershell
$env:GH_TOKEN = "github_pat_..."
uv run python main.py
```

Vaulty passes `GH_TOKEN` into the container when the variable is present. The
token is not stored in the image or in `vaulty.yaml`. Use a fine-grained token
with only the repository permissions required for pushing branches and creating
pull requests. Container network access must be enabled in `vaulty.yaml`.
