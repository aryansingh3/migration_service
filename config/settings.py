import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Mongo -------------------------------------------------------------------
MONGO_TIMEOUT_MS = 2 * 60 * 1000
LIVE_DB = "tickets"  # on MONGODB_URI (production)
BACKUP_DB = "tickets_backup"  # on STAGING_MONGODB_URI; that cluster's `tickets` DB is the staging app's own data
EVENTS_COLLECTION = "events"
STATS_COLLECTION = "seatgeek_stats"
STATS_EVENT_KEY = "event_id"  # seatgeek_stats.event_id -> events._id

# --- Migration ---------------------------------------------------------------
EVENTS_PER_BATCH = 1000  # ended events handled per batch
CHUNK_SIZE = 1000  # rows per read / write / delete round trip
WORKERS = 8  # batches processed in parallel
COUNT_CHUNK = 10_000  # event_ids per count query (dry run)

# Set to a small number (e.g. 10) to try a real run on a few events first. None = all ended events.
MAX_EVENTS = None

OUTPUT_FILE = os.path.join(PROJECT_ROOT, "outputs", "seatgeek_stats_orphan_event_ids.json")

# --- Health (checked on both live and backup) ---------------------------------
HEALTH_MAX_CPU_PCT = {"live": 91, "backup": 75}  # mongod CPU at/above this -> pause, resume when it drops
# disk at/above this -> stop (waiting does not free disk). live is higher: the migration only deletes there,
# it writes to staging only, and freed live space is reused by Mongo rather than returned to the disk.
HEALTH_MAX_DISK_PCT = {"live": 80, "backup": 75}
HEALTH_CHECK_EVERY_S = 15  # a healthy reading is trusted this long before re-checking
HEALTH_RETRY_S = 30  # while paused, re-check this often
HEALTH_MAX_PAUSE_S = 30 * 60  # stop the run if a single pause lasts longer
HEALTH_CPU_SAMPLE_S = 5  # CPU % is averaged over this window

# Create this file (touch STOP) to stop a running migration cleanly after the batches in flight finish.
STOP_FILE = os.path.join(PROJECT_ROOT, "STOP")

# --- Daily schedule (main.py --daily) -----------------------------------------
DAILY_RUN_AT = "13:00"  # HH:MM, local time in DAILY_RUN_TZ - a quiet time for live
DAILY_RUN_TZ = "Asia/Kolkata"

# how often a running batch reports rows copied/deleted so far (big batches log rarely otherwise)
PROGRESS_LOG_EVERY_S = 60
