import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from common.logger import Logger
from common.retry import with_retry
from common.slack_alert import SlackAlert
from common.stop import raise_if_stopped, stop_requested, StopRequested
from config.settings import BACKUP_DB, COLLECTIONS, EVENTS_PER_BATCH, LIVE_DB, MAX_EVENTS, OUTPUT_FILE, PROGRESS_LOG_EVERY_S, STOP_FILE, WORKERS
from database.database import db
from database.seatgeek_repository import SeatgeekRepository
from health.monitor import HealthMonitor
from migration.archive import archive_batch
from migration.orphans import count_orphan_rows, find_orphan_event_ids


def run(dry_run: bool, collections: list = COLLECTIONS) -> None:
    """Migrate each collection in turn, the same way. A STOP request or an error ends the whole run."""
    if os.path.exists(STOP_FILE):
        raise RuntimeError(f"{STOP_FILE} exists - delete it before starting a run")
    db.assert_different_clusters()

    health = HealthMonitor()
    for collection in collections:
        _run_collection(SeatgeekRepository(collection), health, dry_run)
        if stop_requested():
            break


def _run_collection(repo: SeatgeekRepository, health: HealthMonitor, dry_run: bool) -> None:
    started = time.time()
    name = repo.collection
    Logger.info(f"{'DRY RUN' if dry_run else 'RUN'}: live {LIVE_DB}.{name} -> staging {BACKUP_DB}.{name}")
    Logger.info(f"health ok: {'; '.join(map(str, health.wait_until_healthy()))}")

    orphans = find_orphan_event_ids(repo)
    if MAX_EVENTS:
        orphans = orphans[:MAX_EVENTS]
    Logger.info(f"ended event_ids to process: {len(orphans)}")

    output_file = OUTPUT_FILE.format(collection=name)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump([str(oid) for oid in orphans], f)
    Logger.info(f"ended event_ids written to {output_file}")

    if dry_run:
        rows = count_orphan_rows(repo, orphans)
        Logger.info(f"{name} DRY RUN done in {time.time() - started:.0f}s: would copy then delete {rows} rows of {len(orphans)} ended events - nothing written")
        return

    batches = [orphans[i : i + EVENTS_PER_BATCH] for i in range(0, len(orphans), EVENTS_PER_BATCH)]
    SlackAlert.send_message(f"🚀 {name} migration started: {len(orphans):,} ended events in {len(batches)} batches, {WORKERS} workers")
    totals = {"events": 0, "revived": 0, "copied": 0, "deleted": 0}

    progress = {"rows": 0, "logged_at": time.time()}

    def checkpoint(rows: int = 0) -> None:
        # between every chunk of a batch: stop at once if asked, pause if a DB is over its limits,
        # and show that work is happening even when one batch takes minutes
        raise_if_stopped()
        health.wait_until_healthy()
        progress["rows"] += rows
        if time.time() - progress["logged_at"] >= PROGRESS_LOG_EVERY_S:
            progress["logged_at"] = time.time()
            done = totals["deleted"] + progress["rows"]
            Logger.info(f"working: {done:,} rows this run ({done / max(time.time() - started, 1):.0f} rows/s), batches finished {totals['events'] // EVENTS_PER_BATCH}/{len(batches)}")

    def work(batch: list) -> dict:
        checkpoint()
        return with_retry(f"batch of {len(batch)} events", lambda: archive_batch(repo, batch, checkpoint))

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        try:
            for n, result in enumerate(pool.map(work, batches), 1):
                for k in totals:
                    totals[k] += result[k]
                progress["rows"] = 0
                rate = totals["deleted"] / max(time.time() - started, 1)
                Logger.info(f"batch {n}/{len(batches)}: {result} | total {totals} | {rate:.0f} rows/s")
            SlackAlert.send_message(f"✅ {name} migration finished in {(time.time() - started) / 3600:.1f} h: {totals}")
        except StopRequested:
            pool.shutdown(wait=True, cancel_futures=True)
            Logger.warning(f"STOP file found - stopping cleanly after {totals}")
            SlackAlert.send_message(f"🛑 {name} migration stopped by request: {totals}")
        except Exception:
            pool.shutdown(wait=True, cancel_futures=True)  # stop queued batches; running ones finish their own copy->delete
            raise

    Logger.info(f"{name} RUN done in {time.time() - started:.0f}s (paused {health.paused_s:.0f}s): {totals}")
