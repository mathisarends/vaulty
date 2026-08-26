from agenttoolkit import DependencyProvider, provide
from agenttoolkit.builtins.fs import Workspace
from agenttoolkit.builtins.shell import CommandRunner
from agenttoolkit.builtins.todo import InMemoryTodoList, TodoList


class Dependencies(DependencyProvider):
    def __init__(self, workspace: Workspace, sandbox: CommandRunner) -> None:
        self._workspace = workspace
        self._sandbox = sandbox
        self._checklist: TodoList = InMemoryTodoList()

    @provide
    def workspace(self) -> Workspace:
        return self._workspace

    @provide
    def sandbox(self) -> CommandRunner:
        return self._sandbox

    @provide
    def checklist(self) -> TodoList:
        return self._checklist
