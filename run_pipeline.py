"""Command-line entry point for the job market intelligence pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from job_tracker import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect and normalize public job-board listings")
    parser.add_argument("--config", type=Path, default=Path("config/sources.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_pipeline(args.config, args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
