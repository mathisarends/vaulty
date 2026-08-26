from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

BASE_PROMPT_FILE = Path(__file__).parent / "system_prompt.md"


def read_base_prompt(path: Path = BASE_PROMPT_FILE) -> str:
    """Read the base instructions; the one place the prompt touches the disk."""
    return path.read_text(encoding="utf-8").strip()


@dataclass(frozen=True, slots=True)
class SystemPrompt:
    """The agent's system prompt, composed from what the caller hands in.

    Pure text assembly: the caller reads the base instructions (see
    `read_base_prompt`). Rendering never touches the filesystem.
    """

    base: str
    instructions: str | None = None

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
