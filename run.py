from __future__ import annotations

import argparse
import os
import sys

from app.config import Settings
from app.logging_config import configure_logging
from app.main import run_pipeline
from app.scheduler import start_scheduler


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto research aggregator")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run the full pipeline once and exit.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    configure_logging(settings.log_level)

    if args.run_once:
        try:
            stats = run_pipeline(settings)
        except ValueError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            sys.exit(2)
        print(f"Collected articles: {stats.collected}")
        print(f"New articles: {stats.new}")
        print(f"Duplicate articles: {stats.duplicates}")
        print(f"Extraction success: {stats.extraction_success}")
        print(f"Summary success: {stats.summary_success}")
        print(f"Telegram publish success: {stats.publish_success}")
        print(f"Failed: {stats.failed}")
        if stats.failed and os.getenv("GITHUB_ACTIONS") == "true":
            print(
                f"::warning::Research digest had {stats.failed} failure(s). "
                "Check source and article errors in the run log."
            )
    else:
        try:
            start_scheduler(settings)
        except ValueError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
