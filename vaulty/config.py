from pathlib import Path

import yaml
from dotenv import load_dotenv
from llmify import OpenAIModel
from llmify.providers.openai_responses import ReasoningEffort
from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path("vaulty.yaml")
DEFAULT_ENV_PATH = Path(".env")


class LLMConfig(BaseModel):
    model: OpenAIModel = OpenAIModel.GPT_5_6_LUNA
    reasoning_effort: ReasoningEffort = "medium"
    timeout_seconds: float = 120.0
    max_retries: int = 2


class SandboxConfig(BaseModel):
    image: str = "vaulty-sandbox:latest"
    timeout_seconds: float = 60.0
    max_output_bytes: int = 256 * 1024
    enable_network: bool = True
    memory_bytes: int = 512 * 1024 * 1024
    cpus: float = 1.0
    pids: int = 256


class Config(BaseModel):
    root: Path = Path(r"C:\obsidian\database")
    max_steps: int = 20
    llm: LLMConfig = LLMConfig()
    sandbox: SandboxConfig = SandboxConfig()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    return Config.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def load_environment(path: Path = DEFAULT_ENV_PATH) -> bool:
    """Load local secrets without replacing explicitly exported variables."""
    return load_dotenv(path, override=False)
