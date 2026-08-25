from llmify import ChatCodex

from vaulty.config import LLMSettings

_CONTEXT_WINDOW_TOKENS = {
    "gpt-5.6-sol": 272_000,
    "gpt-5.6-terra": 272_000,
    "gpt-5.6-luna": 272_000,
    "gpt-5.5": 272_000,
    "gpt-5.5-pro": 272_000,
    "gpt-5.4": 272_000,
    "gpt-5.4-pro": 272_000,
    "gpt-5.4-mini": 272_000,
    "gpt-5.4-nano": 272_000,
    "gpt-5.3-codex": 272_000,
}
_UNKNOWN_MODEL_CONTEXT_WINDOW_TOKENS = 128_000


def build_llm(config: LLMSettings) -> ChatCodex:
    return ChatCodex.from_cli(
        config.model,
        reasoning_effort=config.reasoning_effort,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )


def resolve_context_window_tokens(model: str, override: int | None = None) -> int:
    if override is not None:
        return override
    return _CONTEXT_WINDOW_TOKENS.get(model, _UNKNOWN_MODEL_CONTEXT_WINDOW_TOKENS)
