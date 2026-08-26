from datetime import UTC, datetime

import llmify

import storage
from runtime import to_llm, to_storage


def test_round_trip_preserves_the_conversation() -> None:
    now = datetime.now(UTC)
    live: list[llmify.Message] = [
        llmify.SystemMessage(content="you are vaulty"),
        llmify.UserMessage(content="tidy up"),
        llmify.AssistantMessage(
            content="on it",
            tool_calls=[
                llmify.ToolCall(
                    id="1",
                    function=llmify.Function(name="list_notes", arguments="{}"),
                )
            ],
        ),
        llmify.ToolResultMessage(tool_call_id="1", content="12 notes"),
        llmify.AssistantMessage(content="done"),
    ]

    stored = to_storage(live, now)
    assert [message.role for message in stored] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]

    restored = to_llm(stored)
    assert [message.role for message in restored] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assistant = restored[1]
    assert isinstance(assistant, llmify.AssistantMessage)
    assert assistant.text == "on it"
    assert assistant.tool_calls[0].function.name == "list_notes"


def test_the_system_prompt_is_never_stored() -> None:
    stored = to_storage(
        [llmify.SystemMessage(content="stale prompt")], datetime.now(UTC)
    )
    assert stored == ()


def test_an_assistant_message_without_text_stays_empty() -> None:
    stored = to_storage(
        [
            llmify.AssistantMessage(
                tool_calls=[
                    llmify.ToolCall(
                        id="1", function=llmify.Function(name="noop", arguments="{}")
                    )
                ]
            )
        ],
        datetime.now(UTC),
    )
    assert isinstance(stored[0], storage.AssistantMessage)
    assert stored[0].content is None
