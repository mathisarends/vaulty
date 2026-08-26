from datetime import UTC, datetime

import storage
from runtime import UserPrompt, replay
from vaulty.agent import TextDelta, ToolFinished, ToolStarted


def transcript() -> tuple[storage.ChatMessage, ...]:
    now = datetime.now(UTC)
    return (
        storage.UserMessage(content="tidy up", created_at=now),
        storage.AssistantMessage(
            content="on it",
            tool_calls=(
                storage.ToolCall(
                    id="1", name="list_notes", arguments='{"folder": "inbox"}'
                ),
            ),
            created_at=now,
        ),
        storage.ToolCallMessage(tool_call_id="1", content="12 notes", created_at=now),
        storage.AssistantMessage(content="done", created_at=now),
    )


def test_a_transcript_replays_as_the_events_that_produced_it() -> None:
    events = list(replay(transcript()))

    assert events == [
        UserPrompt("tidy up"),
        TextDelta("on it"),
        ToolStarted(name="list_notes", arguments={"folder": "inbox"}),
        ToolFinished(name="list_notes", result="12 notes", metadata={}),
        TextDelta("done"),
    ]


def test_tool_metadata_is_looked_up_by_name() -> None:
    events = list(
        replay(transcript(), metadata=lambda name: {"terminal_renderer": name})
    )

    finished = events[3]
    assert isinstance(finished, ToolFinished)
    assert finished.metadata == {"terminal_renderer": "list_notes"}


def test_an_assistant_message_without_text_yields_no_delta() -> None:
    now = datetime.now(UTC)
    events = list(
        replay(
            (
                storage.AssistantMessage(
                    tool_calls=(storage.ToolCall(id="1", name="noop", arguments="{}"),),
                    created_at=now,
                ),
            )
        )
    )

    assert events == [ToolStarted(name="noop", arguments={})]


def test_malformed_arguments_are_shown_as_none() -> None:
    now = datetime.now(UTC)
    events = list(
        replay(
            (
                storage.AssistantMessage(
                    tool_calls=(
                        storage.ToolCall(id="1", name="noop", arguments="not json"),
                    ),
                    created_at=now,
                ),
            )
        )
    )

    assert events == [ToolStarted(name="noop", arguments={})]


def test_a_result_without_its_call_still_renders() -> None:
    now = datetime.now(UTC)
    events = list(
        replay(
            (storage.ToolCallMessage(tool_call_id="9", content="?", created_at=now),)
        )
    )

    assert events == [ToolFinished(name="unknown", result="?", metadata={})]
