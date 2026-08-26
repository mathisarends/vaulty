from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import llmify
import pytest
from agenttoolkit.builtins.fs import LocalWorkspace

from daemon import daemon
from daemon.daemon import Task
from scheduler import ScheduledRun
from storage import MemorySessionRepository, SessionStatus, SessionTrigger
from vaulty.agent import AgentEvent, TurnEnded
from vaulty.config import Config


class StubAgent:
    """Stands in for the real agent, which would need a model and a sandbox."""

    failure: Exception | None = None

    def __init__(self, llm: object, tools: object, **_: object) -> None:
        self.messages: list[llmify.Message] = [
            llmify.SystemMessage(content="you are vaulty")
        ]

    async def run(self, task: str) -> AsyncIterator[AgentEvent]:
        self.messages.append(llmify.UserMessage(content=task))
        if type(self).failure is not None:
            raise type(self).failure
        self.messages.append(llmify.AssistantMessage(content="tended"))
        yield TurnEnded(text="tended", steps=1)


@pytest.fixture
def agentless(monkeypatch: pytest.MonkeyPatch) -> None:
    StubAgent.failure = None
    monkeypatch.setattr(daemon, "build_llm", lambda settings: object())
    monkeypatch.setattr(daemon, "build_tools", lambda dependencies: object())
    monkeypatch.setattr(daemon, "Agent", StubAgent)


def due_run() -> ScheduledRun[Task]:
    return ScheduledRun(
        job_id="daily-gardening",
        kind="cron",
        scheduled_for=datetime.now(UTC),
        payload=Task(prompt="Read Daily Review Instructions"),
        job_name="daily",
    )


def build_runner(tmp_path: Path, repository: MemorySessionRepository):
    return daemon._task_runner(
        Config(root=tmp_path),
        LocalWorkspace(tmp_path),
        object(),  # the sandbox reaches build_tools, which is stubbed out
        repository,
    )


async def test_a_due_run_is_recorded_as_a_cron_session(agentless, tmp_path):
    repository = MemorySessionRepository()

    await build_runner(tmp_path, repository)(due_run())

    session = (await repository.list())[0]
    assert session.trigger is SessionTrigger.CRON
    assert session.title == "daily"
    assert session.status is SessionStatus.FINISHED
    assert [message.role for message in session.messages] == ["user", "assistant"]


async def test_a_failing_run_leaves_the_session_failed(agentless, tmp_path):
    StubAgent.failure = RuntimeError("the model went away")
    repository = MemorySessionRepository()

    with pytest.raises(RuntimeError, match="went away"):
        await build_runner(tmp_path, repository)(due_run())

    session = (await repository.list())[0]
    assert session.status is SessionStatus.FAILED
    assert [message.role for message in session.messages] == ["user"]
