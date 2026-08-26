from agenttoolkit import Inject, OutputBudget, Tools
from agenttoolkit.builtins.shell import CommandRunner


def register_shell_tools(tools: Tools, budget: OutputBudget) -> None:
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
