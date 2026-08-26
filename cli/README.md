# cli

Vaulty's interactive terminal client. One of two frontends over the same agent
core - the other is `daemon`, which runs the agent on a cron schedule.

| Modul | Inhalt |
| --- | --- |
| `cli/app.py` | Argument parsing, config loading, wiring the agent and its sandbox |
| `cli/terminal.py` | The chat loop: local commands, streamed answers, tool activity and checklist rendering |

```bash
uv run vaulty
```

Local commands are `/help`, `/clear`, `/compact`, and `/exit`. Use `--root PATH`
to override the configured workspace for one session and `--no-color` for plain
output.
