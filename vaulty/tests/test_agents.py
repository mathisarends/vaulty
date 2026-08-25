import asyncio

import pytest
from agenttoolkit.builtins.fs import LocalWorkspace

from tests.test_tools import FakeRunner
from vaulty.agent import SystemPrompt, read_base_prompt
from vaulty.agents import INSTRUCTIONS_TEMPLATE, open_agents_home
from vaulty.config import AgentsSettings
from vaulty.tools import Dependencies, build_tools

SKILL = """\
---
name: weekly-review
description: Roll up the week's notes into a review page.
---

Open the daily notes of the past seven days and summarise them.
"""


@pytest.fixture
def base_prompt(tmp_path_factory):
    path = tmp_path_factory.mktemp("prompt") / "system_prompt.md"
    path.write_text("base prompt\n", encoding="utf-8")
    return path


def write_skill(root, name="weekly-review", body=SKILL):
    directory = root / "DOT.VAULTY" / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(body, encoding="utf-8")
    return directory


def call(tools, tool_name, **arguments):
    return asyncio.run(tools.execute(tool_name, arguments))


def test_open_agents_home_scaffolds_the_workspace(tmp_path):
    home = open_agents_home(tmp_path, AgentsSettings())

    assert home.directory == tmp_path / "DOT.VAULTY"
    assert (tmp_path / "DOT.VAULTY" / "skills").is_dir()
    assert home.instructions_file == tmp_path / "DOT.VAULTY" / "AGENTS.md"
    assert home.instructions == INSTRUCTIONS_TEMPLATE.strip()
    assert len(home.skills) == 0


def test_existing_instructions_are_kept(tmp_path):
    instructions = tmp_path / "DOT.VAULTY" / "AGENTS.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("Never touch the archive.", encoding="utf-8")

    home = open_agents_home(tmp_path, AgentsSettings())

    assert home.instructions == "Never touch the archive."


def test_system_prompt_appends_instructions_and_skill_catalogue(tmp_path):
    write_skill(tmp_path)
    home = open_agents_home(tmp_path, AgentsSettings())

    prompt = SystemPrompt(
        base="base prompt",
        instructions="Never touch the archive.",
        skills=home.skills,
    ).render()

    assert prompt.startswith("base prompt")
    assert "<workspace_instructions>\nNever touch the archive." in prompt
    assert "<available_skills>" in prompt
    assert "weekly-review" in prompt


def test_system_prompt_is_the_base_text_alone_without_a_workspace():
    assert SystemPrompt("base prompt").render() == "base prompt"


def test_system_prompt_omits_empty_sections(tmp_path):
    home = open_agents_home(tmp_path, AgentsSettings())

    prompt = SystemPrompt("base prompt", instructions="", skills=home.skills)

    assert prompt.render() == "base prompt"


def test_read_base_prompt_loads_the_bundled_instructions(base_prompt):
    assert read_base_prompt(base_prompt) == "base prompt"


def test_skill_tool_returns_instructions_and_relative_resources(tmp_path):
    directory = write_skill(tmp_path)
    (directory / "template.md").write_text("# Week", encoding="utf-8")
    home = open_agents_home(tmp_path, AgentsSettings())
    workspace = LocalWorkspace(tmp_path)
    tools = build_tools(Dependencies(workspace, FakeRunner(commands=[]), home.skills))

    result = call(tools, "skill", name="weekly-review")

    assert "Open the daily notes" in result
    assert "DOT.VAULTY/skills/weekly-review/template.md" in result


def test_list_skills_picks_up_skills_written_during_the_session(tmp_path):
    home = open_agents_home(tmp_path, AgentsSettings())
    workspace = LocalWorkspace(tmp_path)
    tools = build_tools(Dependencies(workspace, FakeRunner(commands=[]), home.skills))

    assert call(tools, "list_skills") == "no skills defined yet"

    write_skill(tmp_path)

    assert "weekly-review" in call(tools, "list_skills")


def test_skill_tools_are_unavailable_without_a_skills_registry(tmp_path):
    tools = build_tools(Dependencies(LocalWorkspace(tmp_path), FakeRunner(commands=[])))

    names = {schema["function"]["name"] for schema in tools.get_schema("openai")}
    assert "skill" not in names and "list_skills" not in names

    # the error boundary turns the refused call into a message for the model
    assert "Unknown tool 'skill'" in str(call(tools, "skill", name="weekly-review"))
