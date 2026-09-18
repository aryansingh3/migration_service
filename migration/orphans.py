from common.logger import Logger
from common.retry import with_retry
from config.settings import COUNT_CHUNK
from database.seatgeek_repository import SeatgeekRepository


def find_orphan_event_ids(repo: SeatgeekRepository) -> list:
    """event_ids in repo's collection that have no document in events (the event has ended / been removed)."""
    event_ids = with_retry("events _id scan", repo.all_event_ids)
    Logger.info(f"events: {len(event_ids)}")

    row_event_ids = with_retry("distinct event_id scan", repo.distinct_row_event_ids)
    Logger.info(f"distinct event_ids in {repo.collection}: {len(row_event_ids)}")

    # compared as strings so an ObjectId and its string form count as the same event
    return sorted((eid for eid in row_event_ids if str(eid) not in event_ids), key=str)


def count_orphan_rows(repo: SeatgeekRepository, event_ids: list) -> int:
    total = 0
    for i in range(0, len(event_ids), COUNT_CHUNK):
        total += repo.count_live_rows(event_ids[i : i + COUNT_CHUNK])
        Logger.info(f"counted {min(i + COUNT_CHUNK, len(event_ids))}/{len(event_ids)} event_ids, rows so far: {total}")
    return total
