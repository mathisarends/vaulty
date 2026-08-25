import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath

from agenttoolkit.builtins.shell import (
    BindMount,
    CommandDefaults,
    CommandLimits,
    DockerSandbox,
    SandboxLimits,
    SandboxPolicy,
)

DEFAULT_IMAGE = "python:3.13-slim"
WORKSPACE_MOUNT = PurePosixPath("/workspace")


def build_sandbox(
    root: str | os.PathLike[str],
    *,
    image: str = DEFAULT_IMAGE,
    timeout_seconds: float = 60.0,
    max_output_bytes: int = 256 * 1024,
    enable_network: bool = False,
    memory_bytes: int = 512 * 1024 * 1024,
    cpus: float = 1.0,
    pids: int = 256,
) -> DockerSandbox:
    workspace = Path(root).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    return DockerSandbox(
        image,
        defaults=CommandDefaults(
            workspace,
            limits=CommandLimits(
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            ),
        ),
        policy=SandboxPolicy.for_workspace(
            workspace,
            writable=True,
            enable_network_access=enable_network,
            limits=SandboxLimits(memory_bytes=memory_bytes, cpus=cpus, pids=pids),
        ),
        mounts=(BindMount.read_write(workspace, WORKSPACE_MOUNT),),
        network_mode="bridge" if enable_network else None,
    )


@asynccontextmanager
async def open_sandbox(
    root: str | os.PathLike[str],
    **kwargs: object,
) -> AsyncIterator[DockerSandbox]:
    sandbox = build_sandbox(root, **kwargs)  # type: ignore[arg-type]
    async with sandbox:
        yield sandbox
