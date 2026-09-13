from typing import Callable, Optional

from config.settings import CHUNK_SIZE
from database.seatgeek_stats_repository import SeatgeekStatsRepository as repo

Checkpoint = Optional[Callable[..., None]]


def _chunks(items: list, size: int = CHUNK_SIZE):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _copy(event_ids: list, checkpoint: Checkpoint = None) -> list:
    """Upsert every live row of the events into backup; returns the _ids written."""
    written, docs = [], []

    def flush():
        if not docs:
            return
        acknowledged = repo.upsert_backup_rows(docs)
        if acknowledged != len(docs):
            raise RuntimeError(f"backup acknowledged {acknowledged} of {len(docs)} rows")
        written.extend(d["_id"] for d in docs)
        written_now = len(docs)
        docs.clear()
        if checkpoint:
            checkpoint(written_now)

    for doc in repo.iter_live_rows(event_ids):
        docs.append(doc)
        if len(docs) >= CHUNK_SIZE:
            flush()
    flush()
    return written


def archive_batch(event_ids: list, checkpoint: Checkpoint = None) -> dict:
    """copy -> verify -> delete for one batch of ended events. Live rows are deleted only once confirmed in backup."""
    # an event may have come back since the scan - never touch those
    revived = repo.existing_event_ids(event_ids)
    event_ids = [e for e in event_ids if str(e) not in revived]

    copied = _copy(event_ids, checkpoint)

    verified = [i for chunk in _chunks(copied) for i in repo.backup_ids(chunk)]
    if len(verified) != len(copied):
        raise RuntimeError(f"only {len(verified)} of {len(copied)} copied rows found in backup - nothing deleted for this batch")

    # only the _ids read and verified above: a row that lands after the read stays in live
    deleted = 0
    for chunk in _chunks(verified):
        deleted += repo.delete_live_rows(chunk)
        if checkpoint:
            checkpoint()
    return {"events": len(event_ids), "revived": len(revived), "copied": len(copied), "deleted": deleted}
