from collections.abc import Iterator
from pathlib import Path

from vaulty.agents import AgentsHome

BASE_PROMPT_FILE = Path(__file__).parent / "system_prompt.md"

SKILLS_INTRO = (
    "Skills are procedures this workspace has written down. When one matches "
    "the task, call `skill` with its name before doing the work yourself, and "
    "follow the instructions it returns."
)


class SystemPrompt:
    """The agent's system prompt: base instructions plus what the workspace adds.

    The base text lives in `system_prompt.md`; an `AgentsHome` contributes the
    workspace's `AGENTS.md` and the catalogue of its skills.
    """

    def __init__(
        self,
        home: AgentsHome | None = None,
        *,
        base_file: Path = BASE_PROMPT_FILE,
    ) -> None:
        self._home = home
        self._base_file = base_file

    @property
    def base(self) -> str:
        return self._base_file.read_text(encoding="utf-8").strip()

    def render(self) -> str:
        sections = [self.base]
        if self._home is not None:
            sections.extend(self._workspace_sections(self._home))
        return "\n\n".join(sections)

    def __str__(self) -> str:
        return self.render()

    def _workspace_sections(self, home: AgentsHome) -> Iterator[str]:
        instructions = home.instructions
        if instructions:
            yield (
                f'<workspace_instructions source="{home.instructions_file}">\n'
                f"{instructions}\n"
                "</workspace_instructions>"
            )

        catalogue = home.skills.render_prompt()
        if catalogue:
            yield f"{SKILLS_INTRO}\n\n{catalogue}"
