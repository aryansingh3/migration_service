from typing import Iterator, List, Set

from bson import ObjectId
from pymongo import ReplaceOne
from pymongo.collection import Collection
from pymongo.write_concern import WriteConcern

from config.settings import CHUNK_SIZE, EVENTS_COLLECTION, STATS_COLLECTION, STATS_EVENT_KEY
from database.database import db


def _both_forms(values: list) -> list:
    """Each id as ObjectId and as string, so an id stored either way still matches."""
    out = []
    for value in values:
        out.append(value)
        if isinstance(value, ObjectId):
            out.append(str(value))
        elif isinstance(value, str) and ObjectId.is_valid(value):
            out.append(ObjectId(value))
    return out


class SeatgeekStatsRepository:
    """Every read and write the migration makes: live events + seatgeek_stats, and backup seatgeek_stats."""

    @staticmethod
    def _events() -> Collection:
        return db.live[EVENTS_COLLECTION]

    @staticmethod
    def _live() -> Collection:
        return db.live[STATS_COLLECTION]

    @staticmethod
    def _backup() -> Collection:
        return db.backup[STATS_COLLECTION].with_options(write_concern=WriteConcern("majority"))

    # --- events -------------------------------------------------------------

    @staticmethod
    def all_event_ids() -> Set[str]:
        """Every events._id, as strings."""
        return {str(e["_id"]) for e in SeatgeekStatsRepository._events().find({}, {"_id": 1})}

    @staticmethod
    def existing_event_ids(event_ids: list) -> Set[str]:
        """Which of these ids exist in events right now, as strings."""
        cursor = SeatgeekStatsRepository._events().find({"_id": {"$in": _both_forms(event_ids)}}, {"_id": 1})
        return {str(e["_id"]) for e in cursor}

    # --- live seatgeek_stats ------------------------------------------------

    @staticmethod
    def distinct_stat_event_ids() -> list:
        """Distinct non-null event_id values. $sort + $group with no accumulators lets Mongo use
        DISTINCT_SCAN on the event_id index, so this never reads the documents themselves."""
        pipeline = [{"$sort": {STATS_EVENT_KEY: 1}}, {"$group": {"_id": f"${STATS_EVENT_KEY}"}}]
        return [d["_id"] for d in SeatgeekStatsRepository._live().aggregate(pipeline, allowDiskUse=True) if d["_id"] is not None]

    @staticmethod
    def count_live_rows(event_ids: list) -> int:
        return SeatgeekStatsRepository._live().count_documents({STATS_EVENT_KEY: {"$in": event_ids}})

    @staticmethod
    def iter_live_rows(event_ids: list) -> Iterator[dict]:
        return SeatgeekStatsRepository._live().find({STATS_EVENT_KEY: {"$in": event_ids}}, batch_size=CHUNK_SIZE)

    @staticmethod
    def delete_live_rows(ids: list) -> int:
        """Delete live rows by _id; returns how many were deleted."""
        return SeatgeekStatsRepository._live().delete_many({"_id": {"$in": ids}}).deleted_count

    # --- backup seatgeek_stats ----------------------------------------------

    @staticmethod
    def upsert_backup_rows(docs: List[dict]) -> int:
        """Insert-or-replace rows in backup by _id (safe to repeat); returns how many backup acknowledged."""
        result = SeatgeekStatsRepository._backup().bulk_write(
            [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs], ordered=False
        )
        return result.matched_count + result.upserted_count

    @staticmethod
    def backup_ids(ids: list) -> list:
        """Which of these _ids exist in backup."""
        return [d["_id"] for d in SeatgeekStatsRepository._backup().find({"_id": {"$in": ids}}, {"_id": 1})]
