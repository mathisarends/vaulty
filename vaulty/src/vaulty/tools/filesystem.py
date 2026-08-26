from agenttoolkit import Inject, OutputBudget, Tools
from agenttoolkit.builtins.fs import Workspace

_LIST_LIMIT = 500
_GREP_LIMIT = 200
# Headroom so hidden matches do not eat into the visible ones.
_GREP_SCAN_LIMIT = _GREP_LIMIT * 5


def register_filesystem_tools(tools: Tools, budget: OutputBudget) -> None:
    @tools.tool("Read a UTF-8 text file. Paths are relative to the workspace root.")
    async def read_file(path: str, workspace: Inject[Workspace]) -> str:
        content = await workspace.read_file(path)
        return budget.shape(content, hint=f"read {path} in slices with the shell")

    @tools.tool("Create or overwrite a text file with the given content.")
    async def write_file(path: str, content: str, workspace: Inject[Workspace]) -> str:
        await workspace.write_file(path, content)
        return f"wrote {path} ({len(content)} chars)"

    @tools.tool(
        "Replace the exact string 'old' with 'new' in a file. "
        "Fails unless 'old' occurs exactly once, unless replace_all is true."
    )
    async def edit_file(
        path: str,
        old: str,
        new: str,
        workspace: Inject[Workspace],
        replace_all: bool = False,
    ) -> str:
        count = await workspace.edit_file(path, old, new, replace_all=replace_all)
        return f"replaced {count} occurrence(s) in {path}"

    @tools.tool(
        "List a directory in the workspace, optionally recursively. "
        "Hidden files and directories (e.g. .obsidian, .git) are skipped."
    )
    async def list_dir(
        workspace: Inject[Workspace],
        path: str = ".",
        recursive: bool = False,
    ) -> str:
        entries = await workspace.list_dir(path, recursive=recursive)
        visible = [entry for entry in entries if not _is_hidden(entry.path)][
            :_LIST_LIMIT
        ]
        if not visible:
            return f"{path} is empty"
        lines = [f"{'d' if entry.is_dir else 'f'} {entry.path}" for entry in visible]
        return budget.shape("\n".join(lines))

    @tools.tool(
        "Find files by glob pattern, e.g. 'src/**/*.py'. "
        "Hidden files and directories (e.g. .obsidian, .git) are skipped."
    )
    async def glob(pattern: str, workspace: Inject[Workspace]) -> str:
        entries = await workspace.glob(pattern)
        visible = [entry for entry in entries if not _is_hidden(entry.path)]
        if not visible:
            return f"no matches for {pattern}"
        return budget.shape("\n".join(entry.path for entry in visible))

    @tools.tool(
        "Search file contents with a regular expression. "
        "Optionally restrict the search to files matching a glob. "
        "Hidden files and directories (e.g. .obsidian, .git) are skipped."
    )
    async def grep(
        pattern: str,
        workspace: Inject[Workspace],
        glob: str | None = None,
        case_sensitive: bool = True,
    ) -> str:
        matches = await workspace.grep(
            pattern,
            glob=glob,
            case_sensitive=case_sensitive,
            max_matches=_GREP_SCAN_LIMIT,
        )
        visible = [match for match in matches if not _is_hidden(match.path)][
            :_GREP_LIMIT
        ]
        if not visible:
            return f"no matches for {pattern}"
        lines = [f"{match.path}:{match.line_number}: {match.line}" for match in visible]
        return budget.shape("\n".join(lines))


def _is_hidden(path: str) -> bool:
    return any(part.startswith(".") for part in path.replace("\\", "/").split("/"))
