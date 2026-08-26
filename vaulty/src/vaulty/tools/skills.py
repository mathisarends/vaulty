from pathlib import Path

from agenttoolkit import Inject, OutputBudget, Skills, Tools, provided
from agenttoolkit.builtins.fs import Workspace


def register_skill_tools(tools: Tools, budget: OutputBudget) -> None:
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


def _relative_to_workspace(directory: Path, workspace: Workspace) -> str:
    """Return a skill path usable by file tools, or its absolute path."""
    try:
        return directory.relative_to(Path(workspace.root).resolve()).as_posix()
    except ValueError:
        return directory.as_posix()
