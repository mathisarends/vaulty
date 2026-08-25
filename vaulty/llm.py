from functools import lru_cache

from llmify import ChatCodex, OpenAIModel
from llmify.providers.openai_responses import ReasoningEffort
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VAULTY_",
        extra="ignore",
    )

    model: OpenAIModel = OpenAIModel.GPT_5_6_LUNA
    reasoning_effort: ReasoningEffort = "medium"
    timeout_seconds: float = 120.0
    max_retries: int = 2


@lru_cache
def get_settings() -> LLMSettings:
    return LLMSettings()


def build_llm(settings: LLMSettings | None = None) -> ChatCodex:
    settings = settings or get_settings()
    return ChatCodex.from_cli(
        settings.model,
        reasoning_effort=settings.reasoning_effort,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
