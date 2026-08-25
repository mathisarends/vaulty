from pathlib import Path

from agenttoolkit import (
    CallLoggingMiddleware,
    DependencyProvider,
    ErrorBoundaryMiddleware,
    Inject,
    OutputBudget,
    Skills,
    ToolContext,
    Tools,
    provide,
    provided,
)
from agenttoolkit.builtins.fs import Workspace
from agenttoolkit.builtins.shell import CommandRunner

BUDGET = OutputBudget()
LIST_LIMIT = 500
GREP_LIMIT = 200
# headroom so hidden matches do not eat into the visible ones
GREP_SCAN_LIMIT = GREP_LIMIT * 5


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

    def context(self) -> ToolContext:
        """Optional dependencies, so `provided(...)` can gate tools on them."""
        return ToolContext(self._skills)


def build_tools(
    dependencies: Dependencies,
    *,
    budget: OutputBudget = BUDGET,
) -> Tools:
    tools = Tools(
        dependencies=[dependencies],
        context=dependencies.context(),
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
        "at /workspace and is the working directory. Git and GitHub CLI are "
        "installed, and GH_TOKEN is available when configured on the host."
    )
    async def bash(command: str, sandbox: Inject[CommandRunner]) -> str:
        result = await sandbox.execute(command)
        if result.timed_out:
            return f"command timed out after {result.duration_seconds:.1f}s"
        output = budget.shape(result.output.strip())
        if not output:
            return f"exit code: {result.exit_code} (no output)"
        return f"exit code: {result.exit_code}\n{output}"

    @tools.tool(
        "List the skills available in this workspace, with their descriptions. "
        "Use it to pick up skills that were added after the session started.",
        available_when=provided(Skills),
    )
    async def list_skills(skills: Inject[Skills]) -> str:
        skills.refresh_if_changed()
        if not len(skills):
            return "no skills defined yet"
        return budget.shape(
            "\n".join(f"{skill.name}: {skill.description}" for skill in skills)
        )

    @tools.tool(
        "Load a skill by name and return its instructions. Follow them for the "
        "rest of the task. Bundled resource files are listed at the end.",
        available_when=provided(Skills),
    )
    async def skill(
        name: str,
        skills: Inject[Skills],
        workspace: Inject[Workspace],
    ) -> str:
        skills.refresh_if_changed()
        loaded = skills.load(name)
        sections = [f"# Skill: {loaded.name}", loaded.instructions]
        if loaded.resources:
            directory = _relative_to_workspace(loaded.directory, workspace)
            files = "\n".join(f"- {directory}/{path}" for path in loaded.resources)
            sections.append(f"Files bundled with this skill:\n{files}")
        return budget.shape("\n\n".join(sections))

    return tools


def _relative_to_workspace(directory: Path, workspace: Workspace) -> str:
    """Skill paths the file tools can use, falling back to the absolute path."""
    try:
        return directory.relative_to(Path(workspace.root).resolve()).as_posix()
    except ValueError:
        return directory.as_posix()


def _is_hidden(path: str) -> bool:
    return any(part.startswith(".") for part in path.replace("\\", "/").split("/"))
