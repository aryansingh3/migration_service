import time
from typing import Callable, TypeVar

from pymongo.errors import PyMongoError

from common.logger import Logger

T = TypeVar("T")


def with_retry(label: str, call: Callable[[], T], attempts: int = 4, delay_s: int = 15) -> T:
    """Retry a Mongo operation on transient errors (dropped socket, laptop sleep, failover).

    Safe for the migration: copying re-writes the same rows by _id, and deletes only ever
    target _ids that were re-read and verified inside the same attempt.
    """
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except PyMongoError as err:
            if attempt == attempts:
                raise
            Logger.warning(f"{label} failed ({type(err).__name__}: {err}) - retrying in {delay_s}s ({attempt}/{attempts - 1})")
            time.sleep(delay_s)
    raise AssertionError("unreachable")
