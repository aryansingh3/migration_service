from typing import Iterator, List, Set

from bson import ObjectId
from pymongo import ReplaceOne
from pymongo.collection import Collection
from pymongo.write_concern import WriteConcern

from config.settings import CHUNK_SIZE, EVENT_KEY, EVENTS_COLLECTION
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


class SeatgeekRepository:
    """Every read and write the migration makes for one collection: live events + live <collection>, and backup <collection>."""

    def __init__(self, collection: str):
        self.collection = collection

    def _events(self) -> Collection:
        return db.live[EVENTS_COLLECTION]

    def _live(self) -> Collection:
        return db.live[self.collection]

    def _backup(self) -> Collection:
        return db.backup[self.collection].with_options(write_concern=WriteConcern("majority"))

    # --- events -------------------------------------------------------------

    def all_event_ids(self) -> Set[str]:
        """Every events._id, as strings."""
        return {str(e["_id"]) for e in self._events().find({}, {"_id": 1})}

    def existing_event_ids(self, event_ids: list) -> Set[str]:
        """Which of these ids exist in events right now, as strings."""
        cursor = self._events().find({"_id": {"$in": _both_forms(event_ids)}}, {"_id": 1})
        return {str(e["_id"]) for e in cursor}

    # --- live <collection> --------------------------------------------------

    def distinct_row_event_ids(self) -> list:
        """Distinct non-null event_id values. $sort + $group with no accumulators lets Mongo use
        DISTINCT_SCAN on the event_id index, so this never reads the documents themselves."""
        pipeline = [{"$sort": {EVENT_KEY: 1}}, {"$group": {"_id": f"${EVENT_KEY}"}}]
        return [d["_id"] for d in self._live().aggregate(pipeline, allowDiskUse=True) if d["_id"] is not None]

    def count_live_rows(self, event_ids: list) -> int:
        return self._live().count_documents({EVENT_KEY: {"$in": event_ids}})

    def iter_live_rows(self, event_ids: list) -> Iterator[dict]:
        return self._live().find({EVENT_KEY: {"$in": event_ids}}, batch_size=CHUNK_SIZE)

    def delete_live_rows(self, ids: list) -> int:
        """Delete live rows by _id; returns how many were deleted."""
        return self._live().delete_many({"_id": {"$in": ids}}).deleted_count

    # --- backup <collection> ------------------------------------------------

    def upsert_backup_rows(self, docs: List[dict]) -> int:
        """Insert-or-replace rows in backup by _id (safe to repeat); returns how many backup acknowledged."""
        result = self._backup().bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs], ordered=False)
        return result.matched_count + result.upserted_count

    def backup_ids(self, ids: list) -> list:
        """Which of these _ids exist in backup."""
        return [d["_id"] for d in self._backup().find({"_id": {"$in": ids}}, {"_id": 1})]
