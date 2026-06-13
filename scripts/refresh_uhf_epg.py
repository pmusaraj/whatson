#!/usr/bin/env python3
"""Refresh only the UHF/XTream custom EPG snapshots and export."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPG_DIR = ROOT / ".cache" / "epg"
SOURCES_DIR = ROOT / "data" / "sources" / "iptv-org"
NORMALIZED_DIR = ROOT / "data" / "normalized"
DAYS_TO_GRAB = 3
START_DATE_OFFSET_DAYS = 1
GRAB_TIMEOUT_SECONDS = 240


def guide_output_for_channels_file(channels_file: Path) -> Path:
    stem = channels_file.name.removesuffix(".channels.xml")
    if not stem.startswith("custom-"):
        raise ValueError(f"Unexpected channels file name: {channels_file.name}")
    return NORMALIZED_DIR / f"guide-{stem.removeprefix('custom-')}.xml"


def run(command: list[str], *, env: dict[str, str] | None = None, timeout: int | None = None) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=timeout)


def main() -> int:
    if not EPG_DIR.exists():
        raise SystemExit(f"Missing iptv-org EPG checkout: {EPG_DIR}")
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    run(["python3", "scripts/build_uhf_grab_lists.py"])

    channels_files = sorted(SOURCES_DIR.glob("custom-uhf-*.channels.xml"))
    if not channels_files:
        raise SystemExit(f"No custom-uhf channel XML files found under {SOURCES_DIR}")

    start_date = (datetime.now(timezone.utc) - timedelta(days=START_DATE_OFFSET_DAYS)).date().isoformat()
    env = os.environ.copy()
    env["CURR_DATE"] = start_date

    print(
        f"Refreshing {len(channels_files)} UHF EPG channel files from CURR_DATE={start_date} for {DAYS_TO_GRAB} days",
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
        print("UHF grab failures/timeouts; using previous snapshots where available:", flush=True)
        for failure in failures:
            print(f"- {failure}", flush=True)

    run(["python3", "scripts/build_uhf_custom_xmltv.py"])
    run(["python3", "scripts/validate_uhf_xmltv.py"])
    print("UHF EPG refresh complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
