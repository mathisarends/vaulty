import sys

import pytest

from cli.keys import Key, read_key

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="the msvcrt reader is Windows-only"
)


def press(monkeypatch: pytest.MonkeyPatch, *characters: str) -> None:
    import msvcrt

    stream = iter(characters)
    monkeypatch.setattr(msvcrt, "getwch", lambda: next(stream))


@windows_only
@pytest.mark.parametrize(
    ("characters", "expected"),
    [
        (("\xe0", "H"), Key.UP),
        (("\xe0", "P"), Key.DOWN),
        (("\x00", "H"), Key.UP),
        (("\r",), Key.ENTER),
        (("\x1b",), Key.CANCEL),
        (("q",), Key.CANCEL),
        (("j",), Key.DOWN),
        (("K",), Key.UP),
        (("z",), Key.OTHER),
        (("\xe0", "S"), Key.OTHER),
    ],
)
def test_windows_keys_map_to_picker_actions(monkeypatch, characters, expected) -> None:
    press(monkeypatch, *characters)

    assert read_key() is expected


@windows_only
def test_ctrl_c_still_interrupts(monkeypatch) -> None:
    press(monkeypatch, "\x03")

    with pytest.raises(KeyboardInterrupt):
        read_key()
