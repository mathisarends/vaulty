from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from agenttoolkit import Skills

BASE_PROMPT_FILE = Path(__file__).parent / "system_prompt.md"

SKILLS_INTRO = (
    "Skills are procedures this workspace has written down. When one matches "
    "the task, call `skill` with its name before doing the work yourself, and "
    "follow the instructions it returns."
)


def read_base_prompt(path: Path = BASE_PROMPT_FILE) -> str:
    """Read the base instructions; the one place the prompt touches the disk."""
    return path.read_text(encoding="utf-8").strip()


@dataclass(frozen=True, slots=True)
class SystemPrompt:
    """The agent's system prompt, composed from what the caller hands in.

    Pure text assembly: the caller reads the base instructions (see
    `read_base_prompt`) and the workspace's `AGENTS.md`, and passes the loaded
    skill registry. Rendering never touches the filesystem.
    """

    base: str
    instructions: str | None = None
    skills: Skills | None = None

    def render(self) -> str:
        return "\n\n".join(self._sections())

    def __str__(self) -> str:
        return self.render()

    def _sections(self) -> Iterator[str]:
        yield self.base.strip()

        if self.instructions:
            yield (
                "<workspace_instructions>\n"
                f"{self.instructions.strip()}\n"
                "</workspace_instructions>"
            )

        catalogue = self.skills.render_prompt() if self.skills is not None else ""
        if catalogue:
            yield f"{SKILLS_INTRO}\n\n{catalogue}"
