from pathlib import Path

import yaml
from dotenv import load_dotenv
from llmify import OpenAIModel
from llmify.providers.openai_responses import ReasoningEffort
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path("vaulty.yml")
DEFAULT_ENV_PATH = Path(".env")

# Backward-compatible legacy filename.
LEGACY_CONFIG_PATH = Path("vaulty.yaml")


class LLMSettings(BaseModel):
    model: OpenAIModel = OpenAIModel.GPT_5_6_LUNA
    reasoning_effort: ReasoningEffort = "medium"
    timeout_seconds: float = 120.0
    max_retries: int = 2


class CompactionSettings(BaseModel):
    enabled: bool = True
    context_window_tokens: int | None = Field(default=None, ge=128)
    trigger_fraction: float = Field(default=0.8, gt=0.0, lt=1.0)
    retain_tokens: int = Field(default=32_000, ge=0)
    summary_max_tokens: int = Field(default=8_000, gt=0)


class AgentsSettings(BaseModel):
    """Where the workspace keeps its agent configuration.

    A plain `VAULTY/` folder at the workspace root: Obsidian hides dot-folders
    from the vault, so `.agents/` would be unreachable from the app. Relative
    paths are resolved against the workspace root.
    """

    directory: Path = Path("VAULTY")
    skills_dirname: str = "skills"
    instructions_filename: str = "AGENTS.md"

    def home(self, root: Path) -> Path:
        return self.directory if self.directory.is_absolute() else root / self.directory

    def skills_dir(self, root: Path) -> Path:
        return self.home(root) / self.skills_dirname

    def instructions_file(self, root: Path) -> Path:
        return self.home(root) / self.instructions_filename


class SandboxSettings(BaseModel):
    image: str = "vaulty-sandbox:latest"
    timeout_seconds: float = 60.0
    max_output_bytes: int = 256 * 1024
    enable_network: bool = True
    memory_bytes: int = 512 * 1024 * 1024
    cpus: float = 1.0
    pids: int = 256


class Config(BaseModel):
    root: Path = Path(r"C:\obsidian\database")
    agents: AgentsSettings = Field(default_factory=AgentsSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    compaction: CompactionSettings = Field(default_factory=CompactionSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)


def _resolve_config_path(path: Path) -> Path:
    if path.exists():
        return path

    if path.name == "vaulty.yml":
        legacy = path.with_name("vaulty.yaml")
        if legacy.exists():
            return legacy

    return path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    config_path = _resolve_config_path(path)

    if not config_path.exists():
        return Config()

    return Config.model_validate(
        yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    )


def load_environment(path: Path = DEFAULT_ENV_PATH) -> bool:
    """Load local secrets without replacing explicitly exported variables."""
    return load_dotenv(path, override=False)
