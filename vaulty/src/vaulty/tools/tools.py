from agenttoolkit import (
    CallLoggingMiddleware,
    ErrorBoundaryMiddleware,
    OutputBudget,
    Tools,
)

from .dependencies import Dependencies
from .filesystem import register_filesystem_tools
from .shell import register_shell_tools
from .todos import register_todo_tools

_BUDGET = OutputBudget()


def build_tools(
    dependencies: Dependencies,
    *,
    budget: OutputBudget = _BUDGET,
) -> Tools:
    tools = Tools(
        dependencies=[dependencies],
        middleware=(CallLoggingMiddleware(), ErrorBoundaryMiddleware()),
    )
    register_filesystem_tools(tools, budget)
    register_shell_tools(tools, budget)
    register_todo_tools(tools)
    return tools
