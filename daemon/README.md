# daemon

The long-running Vaulty process. Owns the schedule (via `scheduler`), reconciles
it against `vaulty.yml` on every start, and runs the `vaulty` agent on each due
task.
