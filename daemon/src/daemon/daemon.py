"""The long-running Vaulty process.

A single asyncio process that owns the schedule and stays up between runs.
Jobs are declared in `vaulty.yml` and reconciled into a SQLite store on every
start, so the deployed schedule always matches the config file while missed
runs and job state survive a restart.

The runner currently only logs; instantiating the agent is the next step.
"""

import argparse
import asyncio
import json
import logging
import signal
from dataclasses import asdict, dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from scheduler import Cron, ScheduledJob, ScheduledRun, Scheduler, SqliteJobStore
from vaulty.config import (
    DEFAULT_CONFIG_PATH,
    Config,
    SchedulerSettings,
    load_config,
    load_environment,
)

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


async def run_task(run: ScheduledRun[Task]) -> None:
    logger.info(
        "Run %s (%s) due %s: %s",
        run.job_name or run.job_id,
        run.kind,
        run.scheduled_for.isoformat(),
        run.payload.prompt,
    )


async def _report_failure(job: ScheduledJob[Task], error: Exception) -> None:
    logger.error("Job %s failed: %s", job.name or job.id, error)


def build_scheduler(settings: SchedulerSettings) -> Scheduler[Task]:
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
        trigger = Cron(expression=task.cron, timezone=ZoneInfo(settings.timezone))
        payload = Task(prompt=task.prompt)
        if await scheduler.get(task.id) is None:
            job = await scheduler.schedule(
                trigger=trigger, payload=payload, job_id=task.id, name=task.name
            )
        else:
            job = await scheduler.update(
                task.id, trigger=trigger, payload=payload, name=task.name
            )
        logger.info(
            "Job %s scheduled (%s), next run %s",
            task.id,
            task.cron,
            job.next_run_at.isoformat() if job else "unknown",
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


async def serve(config: Config) -> None:
    scheduler = build_scheduler(config.scheduler)
    await _reconcile(scheduler, config.scheduler)

    if not config.scheduler.tasks:
        logger.warning("No tasks configured - the daemon will idle")

    async with scheduler:
        logger.info("Vaulty daemon running - Ctrl-C to stop")
        await _wait_for_shutdown()
    logger.info("Vaulty daemon stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    load_environment()

    parser = argparse.ArgumentParser(prog="vaulty-daemon")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()

    try:
        asyncio.run(serve(load_config(args.config)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
