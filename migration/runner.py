import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from common.logger import Logger
from common.retry import with_retry
from common.slack_alert import SlackAlert
from config.settings import BACKUP_DB, EVENTS_PER_BATCH, LIVE_DB, MAX_EVENTS, OUTPUT_FILE, STATS_COLLECTION, STOP_FILE, WORKERS
from database.database import db
from health.monitor import HealthMonitor
from migration.archive import archive_batch
from migration.orphans import count_orphan_rows, find_orphan_event_ids


class StopRequested(Exception):
    """The STOP file appeared: finish what is in flight and stop cleanly."""


def run(dry_run: bool) -> None:
    started = time.time()
    if os.path.exists(STOP_FILE):
        raise RuntimeError(f"{STOP_FILE} exists - delete it before starting a run")
    db.assert_different_clusters()
    Logger.info(f"{'DRY RUN' if dry_run else 'RUN'}: live {LIVE_DB}.{STATS_COLLECTION} -> staging {BACKUP_DB}.{STATS_COLLECTION}")

    health = HealthMonitor()
    Logger.info(f"health ok: {'; '.join(map(str, health.wait_until_healthy()))}")

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

    def work(batch: list) -> dict:
        if os.path.exists(STOP_FILE):
            raise StopRequested
        health.wait_until_healthy()  # pauses (or stops) before touching the DBs
        return with_retry(f"batch of {len(batch)} events", lambda: archive_batch(batch))

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        try:
            for n, result in enumerate(pool.map(work, batches), 1):
                for k in totals:
                    totals[k] += result[k]
                rate = totals["deleted"] / max(time.time() - started, 1)
                Logger.info(f"batch {n}/{len(batches)}: {result} | total {totals} | {rate:.0f} rows/s")
        except StopRequested:
            pool.shutdown(wait=True, cancel_futures=True)
            Logger.warning(f"STOP file found - stopping cleanly after {totals}")
            SlackAlert.send_message(f"🛑 migration stopped by request: {totals}")
        except Exception:
            pool.shutdown(wait=True, cancel_futures=True)  # stop queued batches; running ones finish their own copy->delete
            raise

    Logger.info(f"RUN done in {time.time() - started:.0f}s (paused {health.paused_s:.0f}s): {totals}")
