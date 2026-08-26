from collections.abc import Sequence

from agenttoolkit import Inject, Tools
from agenttoolkit.builtins.todo import Todo, TodoList, TodoStatus

_MARKS = {
    TodoStatus.PENDING: " ",
    TodoStatus.IN_PROGRESS: "~",
    TodoStatus.COMPLETED: "x",
}


def register_todo_tools(tools: Tools) -> None:
    @tools.tool(
        "Write down the steps a multi-step task needs, in the order you will do "
        "them. Items are appended to the checklist and numbered. Returns the "
        "updated checklist."
    )
    async def add_todos(items: list[str], checklist: Inject[TodoList]) -> str:
        for item in items:
            await checklist.add(item)
        return _render_checklist(await checklist.list())

    @tools.tool(
        "Show the checklist: every item with its number and whether it is done. "
        "Read it between steps to see what is left."
    )
    async def todos(checklist: Inject[TodoList]) -> str:
        return _render_checklist(await checklist.list())

    @tools.tool(
        "Tick off one checklist item by its number, once it is actually done. "
        "Returns the updated checklist."
    )
    async def check_off(item: int, checklist: Inject[TodoList]) -> str:
        await checklist.complete(item)
        return _render_checklist(await checklist.list())


def _render_checklist(items: Sequence[Todo]) -> str:
    if not items:
        return "the checklist is empty"
    return "\n".join(
        f"{item.id}. [{_MARKS[item.status]}] {item.content}" for item in items
    )
