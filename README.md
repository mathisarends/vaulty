# vaulty

A small agentic loop built on [mm-agenttoolkit](https://pypi.org/project/mm-agenttoolkit/)
(tools, dependency injection, sandbox) and [py-llmify](https://pypi.org/project/py-llmify/)
(chat model). The agent gets file access to one workspace and a shell that runs
inside a locked-down Docker container.

## Layout

| Modul | Inhalt |
| --- | --- |
| `vaulty/llm.py` | `ChatCodex` (gpt-5.6-luna) via Codex-CLI-Login, konfigurierbar über `VAULTY_*` env vars |
| `vaulty/sandbox.py` | `DockerSandbox`: read-only rootfs, no network, workspace bind-mounted at `/workspace` |
| `vaulty/tools.py` | `Dependencies` provider + `read_file`, `write_file`, `edit_file`, `list_dir`, `glob`, `grep`, `bash` |
| `vaulty/agent.py` | The loop: stream → run tool calls → feed results back → repeat; emits `TextDelta`, `ToolStarted`, `ToolFinished`, `TurnEnded` |
| `vaulty/main.py` | Terminal chat: streams the answer live and prints every tool call with its result |

## Usage

```bash
uv run vaulty --root .
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

Requires a logged-in Codex CLI (`~/.codex/auth.json`) and a running Docker daemon.
Settings: `VAULTY_MODEL`, `VAULTY_REASONING_EFFORT`, `VAULTY_TIMEOUT_SECONDS`,
`VAULTY_MAX_RETRIES` (env or `.env`).
