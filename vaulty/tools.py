from agenttoolkit import (
    CallLoggingMiddleware,
    DependencyProvider,
    ErrorBoundaryMiddleware,
    Inject,
    OutputBudget,
    Tools,
    provide,
)
from agenttoolkit.builtins.fs import Workspace
from agenttoolkit.builtins.shell import CommandRunner

BUDGET = OutputBudget()
LIST_LIMIT = 500
GREP_LIMIT = 200
# headroom so hidden matches do not eat into the visible ones
GREP_SCAN_LIMIT = GREP_LIMIT * 5


class Dependencies(DependencyProvider):
    def __init__(self, workspace: Workspace, sandbox: CommandRunner) -> None:
        self._workspace = workspace
        self._sandbox = sandbox

    @provide
    def workspace(self) -> Workspace:
        return self._workspace

    @provide
    def sandbox(self) -> CommandRunner:
        return self._sandbox


def build_tools(
    dependencies: Dependencies,
    *,
    budget: OutputBudget = BUDGET,
) -> Tools:
    tools = Tools(
        dependencies=[dependencies],
        middleware=(CallLoggingMiddleware(), ErrorBoundaryMiddleware()),
    )

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
        visible = [e for e in entries if not _is_hidden(e.path)][:LIST_LIMIT]
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
        visible = [e for e in entries if not _is_hidden(e.path)]
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
            max_matches=GREP_SCAN_LIMIT,
        )
        visible = [m for m in matches if not _is_hidden(m.path)][:GREP_LIMIT]
        if not visible:
            return f"no matches for {pattern}"
        lines = [f"{m.path}:{m.line_number}: {m.line}" for m in visible]
        return budget.shape("\n".join(lines))

    @tools.tool(
        "Run a shell command inside the Docker sandbox. The workspace is mounted "
        "at /workspace and is the working directory; there is no network access."
    )
    async def bash(command: str, sandbox: Inject[CommandRunner]) -> str:
        result = await sandbox.execute(command)
        if result.timed_out:
            return f"command timed out after {result.duration_seconds:.1f}s"
        output = budget.shape(result.output.strip())
        if not output:
            return f"exit code: {result.exit_code} (no output)"
        return f"exit code: {result.exit_code}\n{output}"

    return tools


def _is_hidden(path: str) -> bool:
    return any(part.startswith(".") for part in path.replace("\\", "/").split("/"))
