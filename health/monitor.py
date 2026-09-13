import threading
import time
from dataclasses import dataclass
from typing import List, Optional

from common.logger import Logger
from common.retry import with_retry
from common.stop import raise_if_stopped, sleep_unless_stopped
from common.slack_alert import SlackAlert
from config.settings import (
    HEALTH_CHECK_EVERY_S,
    HEALTH_CPU_SAMPLE_S,
    HEALTH_MAX_CPU_PCT,
    HEALTH_MAX_DISK_PCT,
    HEALTH_MAX_PAUSE_S,
    HEALTH_RETRY_S,
)
from database.server_stats_repository import ServerStatsRepository as stats

TARGETS = ("live", "backup")


class HealthStop(RuntimeError):
    """Raised to stop the run: a disk is too full, or a pause lasted longer than HEALTH_MAX_PAUSE_S."""


@dataclass
class Reading:
    target: str
    cpu_pct: float
    disk_pct: float

    def __str__(self) -> str:
        return f"{self.target}: cpu {self.cpu_pct:.0f}%, disk {self.disk_pct:.1f}%"


class HealthMonitor:
    """Blocks the migration while either DB is over its CPU limit; stops it when a disk is over its limit."""

    def __init__(self):
        self._lock = threading.Lock()  # one worker checks; the others wait on it, so a pause pauses them all
        self._last_healthy = 0.0
        self._cores = {t: stats.num_cores(t) for t in TARGETS}
        self.paused_s = 0.0

    def read(self) -> List[Reading]:
        first = {t: stats.cpu_sample(t) for t in TARGETS}
        time.sleep(HEALTH_CPU_SAMPLE_S)
        second = {t: stats.cpu_sample(t) for t in TARGETS}
        readings = []
        for t in TARGETS:
            cpu_us = second[t][0] - first[t][0]
            wall_us = (second[t][1] - first[t][1]) * 1000
            readings.append(Reading(t, 100 * cpu_us / max(wall_us * self._cores[t], 1), stats.disk_used_pct(t)))
        return readings

    def wait_until_healthy(self) -> Optional[List[Reading]]:
        """Returns the healthy readings, or None when a recent healthy check is still trusted."""
        with self._lock:
            if time.time() - self._last_healthy < HEALTH_CHECK_EVERY_S:
                return None
            paused_at = None
            while True:
                raise_if_stopped()
                readings = with_retry("health check", self.read)
                full = [r for r in readings if r.disk_pct >= HEALTH_MAX_DISK_PCT[r.target]]
                if full:
                    over = "; ".join(f"{r} >= {HEALTH_MAX_DISK_PCT[r.target]}%" for r in full)
                    raise HealthStop(f"disk over limit ({over}) - migration stopped")

                busy = [r for r in readings if r.cpu_pct >= HEALTH_MAX_CPU_PCT[r.target]]
                if not busy:
                    if paused_at is not None:
                        waited = time.time() - paused_at
                        self.paused_s += waited
                        message = f"migration resumed after {waited / 60:.1f} min pause ({'; '.join(map(str, readings))})"
                        Logger.info(message)
                        SlackAlert.send_message(f"▶️ {message}")
                    self._last_healthy = time.time()
                    return readings

                reason = "cpu over limit (" + "; ".join(f"{r} >= {HEALTH_MAX_CPU_PCT[r.target]}%" for r in busy) + ")"
                if paused_at is None:
                    paused_at = time.time()
                    SlackAlert.send_message(f"⏸️ migration paused: {reason} - rechecking every {HEALTH_RETRY_S}s")
                elif time.time() - paused_at >= HEALTH_MAX_PAUSE_S:
                    raise HealthStop(f"paused {HEALTH_MAX_PAUSE_S // 60} min and still {reason} - migration stopped")
                Logger.warning(f"paused {time.time() - paused_at:.0f}s: {reason} - rechecking in {HEALTH_RETRY_S}s")
                sleep_unless_stopped(HEALTH_RETRY_S)
