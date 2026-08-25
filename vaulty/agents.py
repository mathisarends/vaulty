"""The workspace's own agent configuration: `AGENTS.md` plus a skills directory.

Both live under `<root>/vaulty/` by default, so an Obsidian vault carries the
same setup a code repo would keep next to its source.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from agenttoolkit import Skills

from vaulty.config import AgentsSettings

logger = logging.getLogger(__name__)

INSTRUCTIONS_TEMPLATE = """\
Instructions for agents working in this workspace. Everything below is loaded
into the system prompt on every session, so keep it short and concrete.

## Conventions

- (describe how notes are named, linked and filed)

## Do not touch

- (list directories the agent should leave alone)
"""


@dataclass(frozen=True, slots=True)
class AgentsHome:
    """The resolved agent configuration directory of a workspace."""

    directory: Path
    instructions_file: Path
    skills: Skills

    @property
    def instructions(self) -> str | None:
        """The workspace's `AGENTS.md`, or None when it is empty."""
        try:
            content = self.instructions_file.read_text(encoding="utf-8").strip()
        except OSError as error:
            logger.warning("Could not read %s: %s", self.instructions_file, error)
            return None
        return content or None


def open_agents_home(root: Path, settings: AgentsSettings) -> AgentsHome:
    """Create the agent configuration in `root` when missing, then load it."""
    home = settings.home(root)
    skills_dir = settings.skills_dir(root)
    instructions_file = settings.instructions_file(root)

    skills_dir.mkdir(parents=True, exist_ok=True)
    if not instructions_file.exists():
        instructions_file.write_text(INSTRUCTIONS_TEMPLATE, encoding="utf-8")
        logger.info("Created %s", instructions_file)

    return AgentsHome(
        directory=home,
        instructions_file=instructions_file,
        skills=Skills.from_dir(skills_dir),
    )
