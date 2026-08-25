from llmify import ChatCodex

from vaulty.config import LLMConfig


def build_llm(config: LLMConfig) -> ChatCodex:
    return ChatCodex.from_cli(
        config.model,
        reasoning_effort=config.reasoning_effort,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )
