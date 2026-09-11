import argparse

from common.logger import Logger
from common.slack_alert import SlackAlert


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move seatgeek_stats rows of ended events (event_id not in events) from live to staging tickets_backup.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="find and count only, writes nothing")
    mode.add_argument("--run", action="store_true", help="copy to tickets_backup, verify, then delete from live")
    args = parser.parse_args()

    from migration.runner import run  # imported here so --help works without connecting to Mongo

    try:
        run(dry_run=args.dry_run)
    except Exception as e:
        Logger.critical(f"migration failed: {e}", print_exception=True)
        SlackAlert.send(e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
