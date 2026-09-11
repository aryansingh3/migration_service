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
EVENTS_PER_BATCH = 100  # ended events handled per batch
CHUNK_SIZE = 1000  # rows per read / write / delete round trip
WORKERS = 4  # batches processed in parallel
COUNT_CHUNK = 10_000  # event_ids per count query (dry run)

# Set to a small number (e.g. 10) to try a real run on a few events first. None = all ended events.
MAX_EVENTS = None

OUTPUT_FILE = os.path.join(PROJECT_ROOT, "outputs", "seatgeek_stats_orphan_event_ids.json")
