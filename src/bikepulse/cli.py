"""Command-line entry point for local runs and scheduler integration."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict

from bikepulse.config import load_settings
from bikepulse.ingestion import refresh_sample
from bikepulse.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BikePulse NYC data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="ingest, transform, load, validate, and export")
    run.add_argument("--source", choices=("sample", "live"), default="sample")
    run.add_argument("--run-id", help="stable run ID for a deterministic replay")

    sample = subparsers.add_parser("refresh-sample", help="replace sample with current API data")
    sample.add_argument("--station-limit", type=int, default=200)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.command == "refresh-sample":
        refresh_sample(settings, station_limit=args.station_limit)
        print(json.dumps({"sample_refreshed": True, "station_limit": args.station_limit}))
        return

    result = run_pipeline(settings, source=args.source, run_id=args.run_id)
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "checks": [asdict(check) for check in result.checks],
                "summary": result.summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

