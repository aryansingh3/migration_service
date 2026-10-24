import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Logs ---------------------------------------------------------------------
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE_MAX_MB = 50  # one log file is rotated at this size
LOG_BACKUPS = 4  # rotated copies kept: 50 x (1 + 4) = 250 MB worst case
LOG_DIR_MAX_MB = 250  # anything above this in logs/ is deleted, oldest first

# --- Mongo -------------------------------------------------------------------
MONGO_TIMEOUT_MS = 2 * 60 * 1000
LIVE_DB = "tickets"  # on MONGODB_URI (production)
BACKUP_DB = "tickets_backup"  # on STAGING_MONGODB_URI; that cluster's `tickets` DB is the staging app's own data
EVENTS_COLLECTION = "events"
# migrated one after another, same method for each: rows whose event_id is not in events move live -> backup
COLLECTIONS = ["seatgeek_stats", "seatgeek_event_sales"]
EVENT_KEY = "event_id"  # <collection>.event_id -> events._id (ObjectId, indexed on live in every collection above)

# --- Migration ---------------------------------------------------------------
EVENTS_PER_BATCH = 1000  # ended events handled per batch
CHUNK_SIZE = 1000  # rows per read / write / delete round trip
WORKERS = 8  # batches processed in parallel
COUNT_CHUNK = 10_000  # event_ids per count query (dry run)

# Set to a small number (e.g. 10) to try a real run on a few events first. None = all ended events.
MAX_EVENTS = None

OUTPUT_FILE = os.path.join(PROJECT_ROOT, "outputs", "{collection}_orphan_event_ids.json")

# --- Health (checked on both live and backup) ---------------------------------
HEALTH_MAX_CPU_PCT = {"live": 91, "backup": 75}  # mongod CPU at/above this -> pause, resume when it drops
# disk at/above this -> stop (waiting does not free disk). live is higher: the migration only deletes there,
# it writes to staging only, and freed live space is reused by Mongo rather than returned to the disk.
HEALTH_MAX_DISK_PCT = {"live": 95, "backup": 85}
HEALTH_CHECK_EVERY_S = 15  # a healthy reading is trusted this long before re-checking
HEALTH_RETRY_S = 30  # while paused, re-check this often
HEALTH_MAX_PAUSE_S = 30 * 60  # stop the run if a single pause lasts longer
HEALTH_CPU_SAMPLE_S = 5  # CPU % is averaged over this window

# Create this file (touch STOP) to stop a running migration cleanly after the batches in flight finish.
STOP_FILE = os.path.join(PROJECT_ROOT, "STOP")

# --- Daily schedule (main.py --daily) -----------------------------------------
# HH:MM, local time in DAILY_RUN_TZ - quiet times for live. One collection per slot, never two at once.
DAILY_RUN_AT = {"seatgeek_stats": "13:00", "seatgeek_event_sales": "15:00"}
DAILY_RUN_TZ = "Asia/Kolkata"

# how often a running batch reports rows copied/deleted so far (big batches log rarely otherwise)
PROGRESS_LOG_EVERY_S = 60
