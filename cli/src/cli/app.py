import argparse
import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agenttoolkit.builtins.fs import LocalWorkspace
from rich.console import Console

from cli.terminal import TerminalChat
from runtime import SessionRunner
from storage import SessionTrigger, SqliteSessionRepository
from vaulty.agent import Agent, SystemPrompt, read_base_prompt
from vaulty.config import (
    DEFAULT_CONFIG_PATH,
    LEGACY_CONFIG_PATH,
    Config,
    load_config,
    load_environment,
)
from vaulty.llm import build_llm
from vaulty.sandbox import open_sandbox
from vaulty.tools import Dependencies, build_tools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vaulty",
        description="Chat with Vaulty in an isolated workspace.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=(
            f"config file (default: {DEFAULT_CONFIG_PATH}; legacy {LEGACY_CONFIG_PATH})"
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="workspace root (overrides the configured root)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable terminal colors",
    )
    return parser


async def run(config: Config, console: Console) -> None:
    workspace = LocalWorkspace(config.root)
    config.sessions.database.parent.mkdir(parents=True, exist_ok=True)
    repository = SqliteSessionRepository(config.sessions.database)

    async with open_sandbox(workspace.root, config.sandbox) as sandbox:
        tools = build_tools(Dependencies(workspace, sandbox))
        agent = Agent(
            build_llm(config.llm),
            tools,
            system_prompt=SystemPrompt(base=read_base_prompt()),
            compaction=config.compaction,
        )
        runner = await SessionRunner.start(
            agent, repository, trigger=SessionTrigger.CLI
        )

        def metadata(name: str) -> Mapping[str, Any]:
            tool = tools.get(name)
            return tool.extra if tool is not None else {}

        await TerminalChat(
            runner,
            console,
            workspace=Path(workspace.root),
            model=config.llm.model.value,
            metadata=metadata,
        ).run()


def main() -> None:
    load_environment()
    args = build_parser().parse_args()
    config = load_config(args.config)
    if args.root is not None:
        config = config.model_copy(update={"root": args.root})

    console = Console(no_color=args.no_color)
    try:
        asyncio.run(run(config, console))
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye.[/dim]")
