import os

from pretty_pie_log import PieLogger, PieLogLevel

from config.settings import LOG_BACKUPS, LOG_DIR, LOG_DIR_MAX_MB, LOG_FILE_MAX_MB


def prune_logs(limit_mb: int = LOG_DIR_MAX_MB) -> None:
    """Keep logs/ under the cap: delete the oldest files first. The file being written is left alone
    (the rotating handler caps it at LOG_FILE_MAX_MB anyway)."""
    if not os.path.isdir(LOG_DIR):
        return
    files = [os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR)]
    files = [f for f in files if os.path.isfile(f)]
    total = sum(os.path.getsize(f) for f in files)
    limit = limit_mb * 1024 * 1024
    for path in sorted(files, key=os.path.getmtime):  # oldest first
        if total <= limit:
            break
        if os.path.basename(path) == "main.log":
            continue
        try:
            size = os.path.getsize(path)
            os.remove(path)
            total -= size
        except OSError:
            pass


# relative_log_directory_path is resolved from this file's folder (common/), so "../logs" = <project>/logs
Logger: PieLogger = PieLogger(
    logger_name="main",
    minimum_log_level=PieLogLevel.DEBUG,
    log_file_size_limit=LOG_FILE_MAX_MB * 1024 * 1024,
    timestamp_padding=25,
    log_level_padding=10,
    max_backup_files=LOG_BACKUPS,
    relative_log_directory_path="../logs",
    global_context=True,
)

prune_logs()
