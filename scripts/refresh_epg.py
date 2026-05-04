#!/usr/bin/env python3
"""Refresh curated iptv-org EPG snapshots and rebuild static web data.

The grabber is run with CURR_DATE set to yesterday and --days 3 so each
snapshot spans yesterday/today/tomorrow. build_web_data.py then emits a
smaller browser payload window: now - 4h through now + 20h.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPG_DIR = ROOT / ".cache" / "epg"
SOURCES_DIR = ROOT / "data" / "sources" / "iptv-org"
NORMALIZED_DIR = ROOT / "data" / "normalized"
WEB_DATA_DIR = ROOT / "web" / "data"
DAYS_TO_GRAB = 3
START_DATE_OFFSET_DAYS = 1
GRAB_TIMEOUT_SECONDS = 180


def guide_output_for_channels_file(channels_file: Path) -> Path:
    stem = channels_file.name.removesuffix(".channels.xml")
    if not stem.startswith("custom-"):
        raise ValueError(f"Unexpected channels file name: {channels_file.name}")
    guide_stem = "guide-" + stem.removeprefix("custom-")
    return NORMALIZED_DIR / f"{guide_stem}.xml"


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, timeout: int | None = None) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh curated EPG XMLTV snapshots and rebuild web/data JSON.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned grab commands without running them.",
    )
    args = parser.parse_args()

    if not EPG_DIR.exists():
        raise SystemExit(f"Missing iptv-org EPG checkout: {EPG_DIR}")

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    channels_files = sorted(SOURCES_DIR.glob("custom-*.channels.xml"))
    if not channels_files:
        raise SystemExit(f"No custom channel XML files found under {SOURCES_DIR}")

    start_date = (datetime.now(timezone.utc) - timedelta(days=START_DATE_OFFSET_DAYS)).date().isoformat()
    env = os.environ.copy()
    env["CURR_DATE"] = start_date

    print(
        f"Refreshing {len(channels_files)} curated EPG channel files "
        f"from CURR_DATE={start_date} for {DAYS_TO_GRAB} days",
        flush=True,
    )

    failures: list[str] = []
    for channels_file in channels_files:
        output_file = guide_output_for_channels_file(channels_file)
        command = [
            "npm",
            "run",
            "grab",
            "--prefix",
            str(EPG_DIR),
            "--",
            "--channels",
            str(channels_file),
            "--output",
            str(output_file),
            "--days",
            str(DAYS_TO_GRAB),
            "--maxConnections",
            "1",
            "--timeout",
            "30000",
        ]
        if args.dry_run:
            print("$", " ".join(command), flush=True)
            continue
        try:
            run(command, env=env, timeout=GRAB_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            message = f"TIMEOUT after {GRAB_TIMEOUT_SECONDS}s: {channels_file.name}"
            print(message, flush=True)
            failures.append(message)
        except subprocess.CalledProcessError as error:
            message = f"FAILED exit {error.returncode}: {channels_file.name}"
            print(message, flush=True)
            failures.append(message)

    if failures:
        print("Grab failures/timeouts; using previous snapshots for these sources:", flush=True)
        for failure in failures:
            print(f"- {failure}", flush=True)

    if args.dry_run:
        print("$ python3 scripts/build_web_data.py")
        print("$ python3 -m unittest discover -s tests -v")
        print("$ node --check web/app.js")
        return 0

    run(["python3", "scripts/build_web_data.py"])
    run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"])
    run(["node", "--check", "web/app.js"])

    print("EPG refresh complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
