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

Local commands are `/help`, `/clear`, `/compact`, `/resume`, and `/exit`. Use `--root PATH`
to override the configured workspace for one session and `--no-color` for plain
output.

## Sessions

Every run opens a session through `runtime.SessionRunner` and records the
conversation in the database at `sessions.database` (`.vaulty/sessions.db` by
default) - the same store the daemon writes its cron runs to. The session is
marked finished when the terminal exits, whichever way it exits.

`/resume` lists the ten most recent sessions. Walk them with the arrow keys
(or `j`/`k`), open one with enter, back out with escape or `q`. The transcript
is replayed into the terminal, so the conversation reads as if it had never
stopped.

```text
you › /resume

     #  when    start  state
     1  8m ago  cron   running   Read Daily Review Instructions and follow the…
  ›  2  2h ago  cli    finished  tidy up the inbox
     3  3d ago  cron   failed    Read Daily Review Instructions
  ↑↓ move · enter open · esc cancel
```

`/resume 2` opens a row straight away without the picker. When there is no
terminal to read keys from - a piped stdin, or a test driving the console -
the picker falls back to typing a row number.

Cron runs show up alongside interactive ones. A session another agent still
owns is listed but cannot be picked - both agents would append to the same
transcript. Leaving a session that was never spoken to deletes it instead of
storing an empty transcript.
