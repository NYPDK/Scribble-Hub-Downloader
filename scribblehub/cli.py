from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download every chapter of a ScribbleHub story and bundle them into text files.",
    )
    parser.add_argument(
        "url",
        help="ScribbleHub series URL (e.g. https://www.scribblehub.com/series/...).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output",
        help="Destination directory for the chapter bundles (default: output).",
    )
    parser.add_argument(
        "-g",
        "--group-size",
        type=int,
        default=15,
        help="Number of chapters to store per text file (default: 15).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retries per request before giving up (default: 3).",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=3.0,
        help="Base backoff (seconds) between retries (default: 3.0).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5,
        help="Optional delay (seconds) between chapter requests to be polite to the server.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds for cloudscraper requests (default: 60).",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.group_size <= 0:
        raise SystemExit("Group size must be a positive integer.")
    if args.retries <= 0:
        raise SystemExit("Retries must be at least 1.")
    if args.backoff < 0:
        raise SystemExit("Backoff must be zero or greater.")
    if args.delay < 0:
        raise SystemExit("Delay must be zero or greater.")
    if args.timeout <= 0:
        raise SystemExit("Timeout must be a positive number.")
    output_path = Path(args.output)
    if output_path.exists() and not output_path.is_dir():
        raise SystemExit(f"Output path exists and is not a directory: {output_path}")
