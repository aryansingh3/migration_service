import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from common.logger import Logger
from common.slack_alert import SlackAlert
from common.stop import StopRequested, sleep_unless_stopped, stop_requested
from config.settings import DAILY_RUN_AT, DAILY_RUN_TZ


def next_daily_run(now: datetime) -> datetime:
    hour, minute = map(int, DAILY_RUN_AT.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def run_once(run, dry_run: bool) -> bool:
    """One migration run; logs and alerts on failure. Returns False if it failed."""
    try:
        run(dry_run=dry_run)
        return True
    except Exception as e:
        Logger.critical(f"migration failed: {e}", print_exception=True)
        SlackAlert.send(e)
        return False


def run_daily(run) -> None:
    """Run the migration every day at DAILY_RUN_AT (DAILY_RUN_TZ), forever. touch STOP to end the loop."""
    tz = ZoneInfo(DAILY_RUN_TZ)
    while True:
        at = next_daily_run(datetime.now(tz))
        Logger.info(f"daily: next run at {at:%Y-%m-%d %H:%M} {DAILY_RUN_TZ}")
        try:
            sleep_unless_stopped((at - datetime.now(tz)).total_seconds(), slice_s=30)
        except StopRequested:
            break
        run_once(run, dry_run=False)  # a failed day (e.g. disk over limit) is retried at the next scheduled time
        if stop_requested():
            break
    Logger.warning("daily: STOP file found - daily loop ended (delete STOP and start again to resume)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move seatgeek_stats rows of ended events (event_id not in events) from live to staging tickets_backup.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="find and count only, writes nothing")
    mode.add_argument("--run", action="store_true", help="copy to tickets_backup, verify, then delete from live")
    mode.add_argument("--daily", action="store_true", help=f"--run every day at {DAILY_RUN_AT} {DAILY_RUN_TZ}, forever")
    args = parser.parse_args()

    from migration.runner import run  # imported here so --help works without connecting to Mongo

    if args.daily:
        if stop_requested():
            raise SystemExit("STOP file exists - delete it before starting the daily loop")
        run_daily(run)
    elif not run_once(run, dry_run=args.dry_run):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
