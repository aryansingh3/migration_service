import os
import time

from config.settings import STOP_FILE


class StopRequested(Exception):
    """The STOP file appeared: drop what is in flight and stop cleanly."""


def stop_requested() -> bool:
    return os.path.exists(STOP_FILE)


def raise_if_stopped() -> None:
    if stop_requested():
        raise StopRequested


def sleep_unless_stopped(seconds: float, slice_s: float = 2.0) -> None:
    """Sleep, but wake within slice_s of a STOP appearing so pauses stay interruptible."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        raise_if_stopped()
        time.sleep(min(slice_s, deadline - time.time()))
    raise_if_stopped()
