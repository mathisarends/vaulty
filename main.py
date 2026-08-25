import argparse
import asyncio
import sys
from pathlib import Path

from agenttoolkit.builtins.fs import LocalWorkspace

from vaulty.agent import Agent, TextDelta, ToolFinished, ToolStarted, TurnEnded
from vaulty.config import DEFAULT_CONFIG_PATH, Config, load_config, load_environment
from vaulty.llm import build_llm
from vaulty.sandbox import open_sandbox
from vaulty.tools import Dependencies, build_tools

DIM = "\033[2m"
CYAN = "\033[36m"
RESET = "\033[0m"


def _preview(text: str, limit: int = 160) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    return f"{single_line[:limit]}..."


def _format_arguments(arguments: dict) -> str:
    return ", ".join(
        f"{key}={_preview(str(value), 60)!r}" for key, value in arguments.items()
    )


async def chat(agent: Agent) -> None:
    print(f"{DIM}Vaulty ready. Ctrl-C or 'exit' to quit.{RESET}\n")
    while True:
        try:
            task = (await asyncio.to_thread(input, "you > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not task:
            continue
        if task in {"exit", "quit"}:
            return

        print()
        try:
            await _turn(agent, task)
        except KeyboardInterrupt:
            print(f"\n{DIM}interrupted{RESET}")
        print()


async def _turn(agent: Agent, task: str) -> None:
    streaming_text = False
    async for event in agent.run(task):
        match event:
            case TextDelta(text):
                sys.stdout.write(text)
                sys.stdout.flush()
                streaming_text = True
            case ToolStarted(name, arguments):
                if streaming_text:
                    print()
                    streaming_text = False
                print(f"{CYAN}• {name}({_format_arguments(arguments)}){RESET}")
            case ToolFinished(_, result):
                print(f"{DIM}  {_preview(result)}{RESET}")
            case TurnEnded(_, steps, stopped_early):
                if streaming_text:
                    print()
                if stopped_early:
                    print(f"{DIM}stopped after {steps} steps without an answer{RESET}")


async def _main(config: Config) -> None:
    workspace = LocalWorkspace(config.root)
    async with open_sandbox(workspace.root, config.sandbox) as sandbox:
        tools = build_tools(Dependencies(workspace, sandbox))
        agent = Agent(build_llm(config.llm), tools, max_steps=config.max_steps)
        await chat(agent)


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(prog="vaulty")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"config file (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_main(load_config(args.config)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
