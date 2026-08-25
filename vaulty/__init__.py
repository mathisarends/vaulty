import argparse
import asyncio
import logging
from pathlib import Path

from agenttoolkit.builtins.fs import LocalWorkspace

from vaulty.agent import SYSTEM_PROMPT, Agent, AgentResult
from vaulty.llm import LLMSettings, build_llm, get_settings
from vaulty.sandbox import DEFAULT_IMAGE, build_sandbox, open_sandbox
from vaulty.tools import Dependencies, build_tools

__all__ = [
    "DEFAULT_IMAGE",
    "SYSTEM_PROMPT",
    "Agent",
    "AgentResult",
    "Dependencies",
    "LLMSettings",
    "build_llm",
    "build_sandbox",
    "build_tools",
    "get_settings",
    "main",
    "open_sandbox",
    "run",
]


async def run(
    task: str,
    *,
    root: str | Path = ".",
    image: str = DEFAULT_IMAGE,
    max_steps: int = 20,
    enable_network: bool = False,
) -> AgentResult:
    workspace = LocalWorkspace(root)
    async with open_sandbox(
        workspace.root,
        image=image,
        enable_network=enable_network,
    ) as sandbox:
        tools = build_tools(Dependencies(workspace, sandbox))
        agent = Agent(build_llm(), tools, max_steps=max_steps)
        return await agent.run(task)


def main() -> None:
    parser = argparse.ArgumentParser(prog="vaulty")
    parser.add_argument("task", help="what the agent should do")
    parser.add_argument("--root", default=".", help="workspace root (default: cwd)")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="sandbox image")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument(
        "--network",
        action="store_true",
        help="allow network access inside the sandbox",
    )
    parser.add_argument("--verbose", action="store_true", help="log every tool call")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    result = asyncio.run(
        run(
            args.task,
            root=args.root,
            image=args.image,
            max_steps=args.max_steps,
            enable_network=args.network,
        )
    )
    print(result.text)
