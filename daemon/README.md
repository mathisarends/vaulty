# daemon

The long-running Vaulty process. Owns the schedule (via `scheduler`), reconciles
it against `vaulty.yml` on every start, and runs the `vaulty` agent on each due
task.

```sh
./scripts/daemon.sh
```

## What a run does

The daemon holds the workspace and the Docker sandbox open for its whole
lifetime; each due task gets a fresh agent (and with it a fresh checklist) so
one run cannot inherit the previous one's state.

Every run is recorded through `runtime.SessionRunner` as a session with
`trigger=cron` and the job's name as its title, in the same database the CLI
reads. A finished nightly run therefore shows up in `/resume` and can be picked
up interactively; one that crashed is stored as `failed` with whatever it
managed to say.

On start, any cron session left `running` by an earlier daemon is marked
`failed`. A hard kill would otherwise leave it `running` forever, and nothing
may resume such a session - the run would be locked away for good. Interactive
sessions are never touched; one of them may belong to a terminal that is open
right now.

Tool calls are logged by the agent itself. The daemon logs the schedule, context
compactions, and the final answer of each run.
