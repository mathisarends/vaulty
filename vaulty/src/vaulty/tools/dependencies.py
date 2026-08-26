from agenttoolkit import DependencyProvider, Skills, ToolContext, provide
from agenttoolkit.builtins.fs import Workspace
from agenttoolkit.builtins.shell import CommandRunner
from agenttoolkit.builtins.todo import InMemoryTodoList, TodoList


class Dependencies(DependencyProvider):
    def __init__(
        self,
        workspace: Workspace,
        sandbox: CommandRunner,
        skills: Skills | None = None,
    ) -> None:
        self._workspace = workspace
        self._sandbox = sandbox
        self._skills = skills
        self._checklist: TodoList = InMemoryTodoList()

    @provide
    def workspace(self) -> Workspace:
        return self._workspace

    @provide
    def sandbox(self) -> CommandRunner:
        return self._sandbox

    @provide
    def skills(self) -> Skills:
        if self._skills is None:
            raise LookupError("This workspace has no skills directory")
        return self._skills

    @provide
    def checklist(self) -> TodoList:
        return self._checklist

    def context(self) -> ToolContext:
        """Optional dependencies, so `provided(...)` can gate tools on them."""
        return ToolContext(self._skills)
