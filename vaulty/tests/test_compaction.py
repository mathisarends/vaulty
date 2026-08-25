from vaulty.llm import resolve_context_window_tokens


def test_context_window_override_wins():
    assert resolve_context_window_tokens("any-model", 123_456) == 123_456


def test_context_window_comes_from_model_profile():
    assert resolve_context_window_tokens("gpt-5.6-luna") == 272_000


def test_unknown_model_uses_conservative_context_window():
    assert resolve_context_window_tokens("custom-model") == 128_000
