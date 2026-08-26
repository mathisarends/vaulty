"""The long-running Vaulty process.

A single asyncio process that owns the schedule and stays up between runs.
Jobs are declared in `vaulty.yml` and reconciled into a SQLite store on every
start, so the deployed schedule always matches the config file while missed
runs and job state survive a restart.

Each due task runs the agent through a `SessionRunner`, so a cron run leaves
the same kind of transcript an interactive one does and can be picked up in
the CLI afterwards.
"""

import asyncio
import json
import logging
import signal
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from zoneinfo import ZoneInfo

from agenttoolkit.builtins.fs import LocalWorkspace
from agenttoolkit.builtins.shell import CommandRunner

from runtime import SessionRunner
from scheduler import Cron, ScheduledJob, ScheduledRun, Scheduler, SqliteJobStore
from storage import (
    SessionRepository,
    SessionStatus,
    SessionTrigger,
    SqliteSessionRepository,
)
from vaulty.agent import (
    Agent,
    ContextCompacted,
    SystemPrompt,
    TurnEnded,
    read_base_prompt,
)
from vaulty.config import Config, ScheduledTaskSettings, SchedulerSettings
from vaulty.llm import build_llm
from vaulty.sandbox import open_sandbox
from vaulty.tools import Dependencies, build_tools

type TaskRunner = Callable[[ScheduledRun[Task]], Awaitable[None]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Task:
    """What a scheduled run should ask the agent to do."""

    prompt: str


class TaskCodec:
    """Stores payloads as JSON so a restart can read back what it scheduled."""

    def encode(self, value: Task) -> str:
        return json.dumps(asdict(value))

    def decode(self, value: str) -> Task:
        return Task(**json.loads(value))


async def serve(config: Config) -> None:
    """Hold the workspace and the sandbox open while the schedule runs."""
    workspace = LocalWorkspace(config.root)
    config.sessions.database.parent.mkdir(parents=True, exist_ok=True)
    repository = SqliteSessionRepository(config.sessions.database)

    await _fail_orphaned_runs(repository)

    async with open_sandbox(workspace.root, config.sandbox) as sandbox:
        run_task = _task_runner(config, workspace, sandbox, repository)
        scheduler = _build_scheduler(config.scheduler, run_task)
        await _reconcile(scheduler, config.scheduler)

        if not config.scheduler.tasks:
            logger.warning("No tasks configured - the daemon will idle")

        async with scheduler:
            logger.info("Vaulty daemon running - Ctrl-C to stop")
            await _wait_for_shutdown()
    logger.info("Vaulty daemon stopped")


async def _fail_orphaned_runs(repository: SessionRepository) -> None:
    """Close out sessions an earlier daemon was killed in the middle of.

    Such a session stays marked running forever, and nothing may resume it -
    so a hard kill would silently lock away every run it was working on. Only
    cron sessions are touched: this process is their only writer, while a
    running CLI session may belong to a terminal that is open right now.
    """
    for session in await repository.list():
        if session.trigger is not SessionTrigger.CRON:
            continue
        if session.status is not SessionStatus.RUNNING:
            continue
        await repository.save(session.with_status(SessionStatus.FAILED))
        logger.warning(
            "Session %s was left running by an earlier daemon - marked failed",
            session.id,
        )


def _task_runner(
    config: Config,
    workspace: LocalWorkspace,
    sandbox: CommandRunner,
    repository: SessionRepository,
) -> TaskRunner:
    """Run one due task on a fresh agent, recording it as a cron session."""
    llm = build_llm(config.llm)

    async def run_task(run: ScheduledRun[Task]) -> None:
        label = run.job_name or run.job_id
        logger.info(
            "Run %s (%s) due %s: %s",
            label,
            run.kind,
            run.scheduled_for.isoformat(),
            run.payload.prompt,
        )
        # Tools are rebuilt per run so each one starts with an empty checklist.
        agent = Agent(
            llm,
            build_tools(Dependencies(workspace, sandbox)),
            system_prompt=SystemPrompt(base=read_base_prompt()),
            compaction=config.compaction,
        )
        session = await SessionRunner.start(
            agent, repository, trigger=SessionTrigger.CRON, title=label
        )
        try:
            async for event in session.run(run.payload.prompt):
                _log_event(label, event)
        finally:
            await session.finish()
            logger.info("Run %s recorded as session %s", label, session.session.id)

    return run_task


def _log_event(label: str, event: object) -> None:
    """Tool calls are already logged by the agent; report the rest."""
    match event:
        case ContextCompacted(before_tokens, after_tokens):
            logger.info(
                "Run %s compacted context: %s -> %s estimated tokens",
                label,
                before_tokens,
                after_tokens,
            )
        case TurnEnded(text, steps):
            logger.info("Run %s finished after %s steps: %s", label, steps, text)


async def _report_failure(job: ScheduledJob[Task], error: Exception) -> None:
    logger.error("Job %s failed: %s", job.name or job.id, error)


def _build_scheduler(
    settings: SchedulerSettings, run_task: TaskRunner
) -> Scheduler[Task]:
    settings.database.parent.mkdir(parents=True, exist_ok=True)
    store = SqliteJobStore[Task](settings.database, payload_codec=TaskCodec())
    return Scheduler(run_task, store, error_handler=_report_failure)


async def _reconcile(scheduler: Scheduler[Task], settings: SchedulerSettings) -> None:
    """Make the stored schedule match the config file."""
    configured = {task.id for task in settings.tasks}

    for job in await scheduler.list():
        if job.id not in configured:
            await scheduler.remove(job.id)
            logger.info("Removed job %s - no longer in config", job.id)

    for task in settings.tasks:
        job = await _upsert_job(scheduler, task, settings.timezone)
        logger.info(
            "Job %s scheduled (%s), next run %s",
            task.id,
            task.cron,
            job.next_run_at.isoformat() if job else "unknown",
        )


async def _upsert_job(
    scheduler: Scheduler[Task], task: ScheduledTaskSettings, timezone: str
) -> ScheduledJob[Task] | None:
    trigger = Cron(expression=task.cron, timezone=ZoneInfo(timezone))
    payload = Task(prompt=task.prompt)

    if await scheduler.get(task.id) is None:
        return await scheduler.schedule(
            trigger=trigger, payload=payload, job_id=task.id, name=task.name
        )

    return await scheduler.update(
        task.id, trigger=trigger, payload=payload, name=task.name
    )


async def _wait_for_shutdown() -> None:
    """Block until the process is asked to stop, on POSIX and on Windows."""
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def request_stop(*_: object) -> None:
        loop.call_soon_threadsafe(stop.set)

    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)

    for received in signals:
        try:
            loop.add_signal_handler(received, stop.set)
        except (NotImplementedError, ValueError):
            signal.signal(received, request_stop)

    await stop.wait()
