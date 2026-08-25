import asyncio
from dataclasses import dataclass

import pytest
from agenttoolkit.builtins.fs import LocalWorkspace
from agenttoolkit.builtins.shell import CommandResult

from vaulty import Dependencies, build_tools


@dataclass
class FakeRunner:
    commands: list[str]

    async def execute(self, command, **kwargs):
        self.commands.append(command)
        return CommandResult(
            command=command,
            returncode=0,
            stdout="hello\n",
            stderr="",
            duration_seconds=0.01,
        )


@pytest.fixture
def registry(tmp_path):
    workspace = LocalWorkspace(tmp_path)
    runner = FakeRunner(commands=[])
    tools = build_tools(Dependencies(workspace, runner))
    return tools, workspace, runner


def call(tools, name, **arguments):
    return asyncio.run(tools.execute(name, arguments))


def test_schema_covers_file_and_shell_tools(registry):
    tools, _, _ = registry
    schemas = tools.get_schema("openai")
    names = {schema["function"]["name"] for schema in schemas}
    assert names == {
        "read_file",
        "write_file",
        "edit_file",
        "list_dir",
        "glob",
        "grep",
        "bash",
    }


def test_write_read_and_edit_roundtrip(registry):
    tools, workspace, _ = registry
    call(tools, "write_file", path="notes.md", content="draft\n")
    assert call(tools, "read_file", path="notes.md") == "draft"

    call(tools, "edit_file", path="notes.md", old="draft", new="final")
    assert (workspace.root / "notes.md").read_text(encoding="utf-8") == "final\n"


def test_grep_finds_written_content(registry):
    tools, _, _ = registry
    call(tools, "write_file", path="a.txt", content="alpha\nbeta\n")
    assert "a.txt:2: beta" in call(tools, "grep", pattern="beta")


def test_bash_reports_exit_code_and_output(registry):
    tools, _, runner = registry
    result = call(tools, "bash", command="echo hello")
    assert runner.commands == ["echo hello"]
    assert "exit code: 0" in result and "hello" in result


def test_tool_errors_are_returned_to_the_model(registry):
    tools, _, _ = registry
    assert "Tool failed" in call(tools, "read_file", path="missing.txt")
