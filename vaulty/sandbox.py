import os
from collections.abc import AsyncGenerator
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

from vaulty.config import SandboxConfig

WORKSPACE_MOUNT = PurePosixPath("/workspace")


def build_sandbox(
    root: str | os.PathLike[str],
    config: SandboxConfig,
) -> DockerSandbox:
    workspace = Path(root).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    return DockerSandbox(
        config.image,
        defaults=CommandDefaults(
            workspace,
            limits=CommandLimits(
                timeout_seconds=config.timeout_seconds,
                max_output_bytes=config.max_output_bytes,
            ),
        ),
        policy=SandboxPolicy.for_workspace(
            workspace,
            writable=True,
            enable_network_access=config.enable_network,
            limits=SandboxLimits(
                memory_bytes=config.memory_bytes,
                cpus=config.cpus,
                pids=config.pids,
            ),
        ),
        mounts=(BindMount.read_write(workspace, WORKSPACE_MOUNT),),
        network_mode="bridge" if config.enable_network else None,
    )


@asynccontextmanager
async def open_sandbox(
    root: str | os.PathLike[str],
    config: SandboxConfig,
) -> AsyncGenerator[DockerSandbox]:
    async with build_sandbox(root, config) as sandbox:
        yield sandbox
