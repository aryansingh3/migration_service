import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from common.logger import Logger
from config.settings import BACKUP_DB, EVENTS_PER_BATCH, LIVE_DB, MAX_EVENTS, OUTPUT_FILE, STATS_COLLECTION, WORKERS
from database.database import db
from migration.archive import archive_batch
from migration.orphans import count_orphan_rows, find_orphan_event_ids


def run(dry_run: bool) -> None:
    started = time.time()
    db.assert_different_clusters()
    Logger.info(f"{'DRY RUN' if dry_run else 'RUN'}: live {LIVE_DB}.{STATS_COLLECTION} -> staging {BACKUP_DB}.{STATS_COLLECTION}")

    orphans = find_orphan_event_ids()
    if MAX_EVENTS:
        orphans = orphans[:MAX_EVENTS]
    Logger.info(f"ended event_ids to process: {len(orphans)}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump([str(oid) for oid in orphans], f)
    Logger.info(f"ended event_ids written to {OUTPUT_FILE}")

    if dry_run:
        rows = count_orphan_rows(orphans)
        Logger.info(f"DRY RUN done in {time.time() - started:.0f}s: would copy then delete {rows} rows of {len(orphans)} ended events - nothing written")
        return

    batches = [orphans[i : i + EVENTS_PER_BATCH] for i in range(0, len(orphans), EVENTS_PER_BATCH)]
    totals = {"events": 0, "revived": 0, "copied": 0, "deleted": 0}

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        try:
            for n, result in enumerate(pool.map(archive_batch, batches), 1):
                for k in totals:
                    totals[k] += result[k]
                rate = totals["deleted"] / max(time.time() - started, 1)
                Logger.info(f"batch {n}/{len(batches)}: {result} | total {totals} | {rate:.0f} rows/s")
        except Exception:
            pool.shutdown(wait=True, cancel_futures=True)  # stop queued batches; running ones finish their own copy->delete
            raise

    Logger.info(f"RUN done in {time.time() - started:.0f}s: {totals}")
