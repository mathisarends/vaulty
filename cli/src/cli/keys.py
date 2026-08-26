"""Reading single keypresses, on Windows and on POSIX terminals.

The terminal is put into raw mode for one key and restored right after, so
an interrupted picker cannot leave the shell in a broken state.
"""

import sys
from enum import Enum, auto


class Key(Enum):
    UP = auto()
    DOWN = auto()
    ENTER = auto()
    CANCEL = auto()
    OTHER = auto()


_BY_CHARACTER = {
    "\r": Key.ENTER,
    "\n": Key.ENTER,
    "\x1b": Key.CANCEL,
    "q": Key.CANCEL,
    "k": Key.UP,
    "j": Key.DOWN,
}


def supported() -> bool:
    """Whether keys can be read at all - false when input is piped."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def read_key() -> Key:
    """Block until one key is pressed. Raises `KeyboardInterrupt` on Ctrl-C."""
    if sys.platform == "win32":
        return _read_windows()
    return _read_posix()


def _read_windows() -> Key:
    import msvcrt

    character = msvcrt.getwch()
    if character == "\x03":
        raise KeyboardInterrupt
    if character in ("\x00", "\xe0"):  # a two-part arrow or function key
        return {"H": Key.UP, "P": Key.DOWN}.get(msvcrt.getwch(), Key.OTHER)
    return _BY_CHARACTER.get(character.casefold(), Key.OTHER)


def _read_posix() -> Key:
    import select
    import termios
    import tty

    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        character = sys.stdin.read(1)
        if character == "\x03":
            raise KeyboardInterrupt
        if character == "\x1b" and select.select([descriptor], [], [], 0.05)[0]:
            return {"A": Key.UP, "B": Key.DOWN}.get(sys.stdin.read(2)[-1:], Key.OTHER)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)
    return _BY_CHARACTER.get(character.casefold(), Key.OTHER)
