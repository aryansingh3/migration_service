from pretty_pie_log import PieLogger, PieLogLevel

# relative_log_directory_path is resolved from this file's folder (common/), so "../logs" = <project>/logs
Logger: PieLogger = PieLogger(
    logger_name="main",
    minimum_log_level=PieLogLevel.DEBUG,
    log_file_size_limit=int(100 * 1024 * 1024),  # 100 mb
    timestamp_padding=25,
    log_level_padding=10,
    max_backup_files=20,
    relative_log_directory_path="../logs",
    global_context=True,
)
