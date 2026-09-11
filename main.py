import json
import os

from database.database import db

COUNT_CHUNK = 10_000
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "seatgeek_stats_orphan_event_ids.json")

seatgeek_stats = db.prod_tickets.seatgeek_stats

event_ids = {e["_id"] for e in db.prod_tickets.events.find({}, {"_id": 1})}
print(f"events: {len(event_ids)}")

# $sort + $group with no accumulators lets Mongo use DISTINCT_SCAN on the
# event_id index, so this never touches the 80GB of documents
stat_event_ids = {
    doc["_id"]
    for doc in seatgeek_stats.aggregate(
        [{"$sort": {"event_id": 1}}, {"$group": {"_id": "$event_id"}}],
        allowDiskUse=True,
    )
}
print(f"distinct event_ids in seatgeek_stats: {len(stat_event_ids)}")

orphan_event_ids = sorted(stat_event_ids - event_ids)
print(f"event_ids with no event: {len(orphan_event_ids)}")

orphan_docs = 0
for i in range(0, len(orphan_event_ids), COUNT_CHUNK):
    chunk = orphan_event_ids[i : i + COUNT_CHUNK]
    orphan_docs += seatgeek_stats.count_documents({"event_id": {"$in": chunk}})
    print(f"counted {min(i + COUNT_CHUNK, len(orphan_event_ids))}/{len(orphan_event_ids)}, orphan docs so far: {orphan_docs}")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump([str(oid) for oid in orphan_event_ids], f)

print(f"total seatgeek_stats docs without an event: {orphan_docs}")
print(f"orphan event_ids written to {OUTPUT_FILE}")
