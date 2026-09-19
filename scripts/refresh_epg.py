#!/usr/bin/env python3
"""Refresh curated iptv-org EPG snapshots and rebuild static web data.

The grabber is run with CURR_DATE set to yesterday and --days 4 so each
snapshot covers the four-hour lookback and full 48-hour lookahead.
build_web_data.py emits a browser payload window: now - 4h through now + 48h.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EPG_DIR = ROOT / ".cache" / "epg"
SOURCES_DIR = ROOT / "data" / "sources" / "iptv-org"
NORMALIZED_DIR = ROOT / "data" / "normalized"
WEB_DATA_DIR = ROOT / "web" / "data"
DAYS_TO_GRAB = 4
START_DATE_OFFSET_DAYS = 1
GRAB_TIMEOUT_SECONDS = 120


def guide_output_for_channels_file(channels_file: Path) -> Path:
    stem = channels_file.name.removesuffix(".channels.xml")
    if not stem.startswith("custom-"):
        raise ValueError(f"Unexpected channels file name: {channels_file.name}")
    guide_stem = "guide-" + stem.removeprefix("custom-")
    return NORMALIZED_DIR / f"{guide_stem}.xml"


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, timeout: int | None = None) -> None:
    print("$", " ".join(command), flush=True)
    with subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True) as process:
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh curated EPG XMLTV snapshots and rebuild web/data JSON.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned grab commands without running them.",
    )
    parser.add_argument("--skip-editor-picks", action="store_true", help="Rebuild guides without requesting editorial selections")
    parser.add_argument("--countries", nargs="+", help="Refresh only these country codes")
    args = parser.parse_args()

    if not EPG_DIR.exists():
        raise SystemExit(f"Missing iptv-org EPG checkout: {EPG_DIR}")

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    channels_files = sorted(
        path
        for path in SOURCES_DIR.glob("custom-*.channels.xml")
        if not path.name.startswith("custom-uhf-")
    )
    if args.countries:
        countries = {country.upper() for country in args.countries}
        channels_files = [path for path in channels_files
                          if path.name.removeprefix("custom-").removeprefix("premium-").split("-")[0] in countries]
    channels_files = [path for path in channels_files if len(ET.parse(path).getroot())]
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
        source_env = env.copy()
        if channels_file.name.endswith("-guidatv.sky.it.channels.xml"):
            source_env["CURR_DATE"] = datetime.now(timezone.utc).date().isoformat()
        timeout = max(GRAB_TIMEOUT_SECONDS, min(900, len(ET.parse(channels_file).getroot()) * DAYS_TO_GRAB * 10))
        if channels_file.name.endswith("-tv.sfr.fr.channels.xml"):
            command = ["python3", "scripts/grab_sfr_epg.py", "--channels", str(channels_file),
                       "--output", str(output_file), "--start-date", start_date, "--days", str(DAYS_TO_GRAB)]
            timeout = 300
        if channels_file.name.endswith("-superguidatv.it.channels.xml"):
            command = ["python3", "scripts/grab_superguida_epg.py", "--channels", str(channels_file),
                       "--output", str(output_file), "--days", str(DAYS_TO_GRAB)]
            timeout = 900
        if args.dry_run:
            print("$", " ".join(command), flush=True)
            continue
        try:
            run(command, env=source_env, timeout=timeout)
        except subprocess.TimeoutExpired:
            message = f"TIMEOUT after {timeout}s: {channels_file.name}"
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
        if not args.countries:
            print("$ python3 scripts/build_mls_apple_xmltv.py")
        print("$ python3 scripts/build_web_data.py")
        if not args.skip_editor_picks:
            print("$ python3 scripts/build_editor_picks.py")
        print("$ python3 -m unittest discover -s tests -v")
        print("$ node --check web/app.js")
        return 0

    if not args.countries:
        try:
            run(["python3", "scripts/build_mls_apple_xmltv.py"])
        except subprocess.CalledProcessError as error:
            print(f"FAILED exit {error.returncode}: build_mls_apple_xmltv.py; using previous MLS Apple snapshot if present", flush=True)
        except Exception as error:
            print(f"FAILED: build_mls_apple_xmltv.py: {error}; using previous MLS Apple snapshot if present", flush=True)

    run(["python3", "scripts/build_web_data.py"])
    if not args.skip_editor_picks:
        run(["python3", "scripts/build_editor_picks.py"])
    run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"])
    run(["node", "--check", "web/app.js"])

    print("EPG refresh complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
