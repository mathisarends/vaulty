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
| `vaulty/agent.py` | The loop: invoke → run tool calls → feed results back → repeat until the model answers |

## Usage

```bash
uv run vaulty "add a test for the parser and make it pass" --root . --verbose
```

```python
from vaulty import run

result = await run("summarise the repo layout", root=".")
print(result.text, result.steps)
```

Requires a logged-in Codex CLI (`~/.codex/auth.json`) and a running Docker daemon.
Settings: `VAULTY_MODEL`, `VAULTY_REASONING_EFFORT`, `VAULTY_TIMEOUT_SECONDS`,
`VAULTY_MAX_RETRIES` (env or `.env`).
