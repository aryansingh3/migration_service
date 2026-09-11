from typing import Tuple

from pymongo.database import Database

from database.database import db


class ServerStatsRepository:
    """Server-level reads used by the health monitor. `target` is "live" or "backup"."""

    @staticmethod
    def _db(target: str) -> Database:
        return db.live if target == "live" else db.backup

    @staticmethod
    def disk_used_pct(target: str) -> float:
        """% used of the disk volume that holds the database."""
        stats = ServerStatsRepository._db(target).command("dbStats")
        return 100 * stats["fsUsedSize"] / stats["fsTotalSize"]

    @staticmethod
    def num_cores(target: str) -> int:
        return ServerStatsRepository._db(target).client.admin.command("hostInfo")["system"]["numCores"]

    @staticmethod
    def cpu_sample(target: str) -> Tuple[int, int]:
        """(total CPU time used by mongod in microseconds, server uptime in ms). CPU % comes from two samples."""
        status = ServerStatsRepository._db(target).client.admin.command("serverStatus")
        extra = status["extra_info"]
        return extra["user_time_us"] + extra["system_time_us"], status["uptimeMillis"]
