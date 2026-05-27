"""
SaaS Radar — entry point.

Usage:
    python run_daily.py          # run now, then repeat daily at DAILY_RUN_TIME
    python run_daily.py --now    # run once immediately and exit
    python run_daily.py --time 09:30  # override run time for this session

Environment variables (set in your shell or a .env file):
    ANTHROPIC_API_KEY   required — Claude API key
    APIFY_TOKEN         required for TrustMRR + startups.rip scraping
    DAILY_RUN_TIME      optional — default "08:00" (24h HH:MM)
"""

import argparse
import logging
import sys
import time

import schedule

from config       import DAILY_RUN_TIME, ANTHROPIC_API_KEY, APIFY_TOKEN
from daily_runner import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _check_env() -> bool:
    ok = True
    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY is not set. Claude analysis will be disabled.")
        ok = False
    if not APIFY_TOKEN:
        log.warning(
            "APIFY_TOKEN is not set. "
            "startups.rip and TrustMRR scraping will be skipped."
        )
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="SaaS Radar — daily opportunity finder")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run once immediately and exit (skips scheduler)",
    )
    parser.add_argument(
        "--time",
        default=DAILY_RUN_TIME,
        metavar="HH:MM",
        help=f"Daily run time in 24h format (default: {DAILY_RUN_TIME})",
    )
    args = parser.parse_args()

    _check_env()

    if args.now:
        log.info("Running immediately (--now flag)")
        run()
        sys.exit(0)

    run_time = args.time
    log.info("SaaS Radar scheduler started — will run daily at %s", run_time)
    log.info("Running immediately for today's report…")
    run()

    schedule.every().day.at(run_time).do(run)
    log.info("Next run scheduled at %s. Ctrl+C to stop.", run_time)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
