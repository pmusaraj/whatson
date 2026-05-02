#!/usr/bin/env python3
"""Build browser-friendly JSON from normalized XMLTV guide snapshots."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
WEB_DATA_DIR = ROOT / "web" / "data"

GUIDES = {
    "FR": [NORMALIZED_DIR / "guide-FR-tv.sfr.fr.xml"],
    "ES": [
        NORMALIZED_DIR / "guide-ES-programacion-tv.elpais.com.xml",
        NORMALIZED_DIR / "guide-ES-orangetv.orange.es.xml",
    ],
    "CA": [
        NORMALIZED_DIR / "guide-CA-tvpassport.com.xml",
        NORMALIZED_DIR / "guide-CA-tvhebdo.com.xml",
    ],
}

COUNTRY_NAMES = {
    "FR": "France",
    "ES": "Spain",
    "CA": "Canada",
}


def parse_xmltv_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d%H%M%S %z").astimezone(timezone.utc)


def parse_iso_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def text(element: ET.Element, selector: str):
    child = element.find(selector)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def program_window(programs: list[dict], now: datetime, hours: int = 3) -> list[dict]:
    window_end = now + timedelta(hours=hours)
    upcoming = []
    for program in programs:
        start_at = parse_iso_time(program["startAt"])
        end_at = parse_iso_time(program["endAt"])
        if end_at <= now:
            continue
        if start_at >= window_end:
            continue
        upcoming.append(program)
    return sorted(upcoming, key=lambda program: program["startAt"])


def ingest_guide(path: Path, channels: dict, programs_by_channel: dict, root_dir: Path) -> None:
    root = ET.parse(path).getroot()

    for channel in root.findall("channel"):
        channel_id = channel.attrib["id"]
        icon = channel.find("icon")
        channels.setdefault(
            channel_id,
            {
                "id": channel_id,
                "name": text(channel, "display-name") or channel_id,
                "logoUrl": icon.attrib.get("src") if icon is not None else None,
                "sources": [],
            },
        )
        try:
            source = str(path.relative_to(root_dir))
        except ValueError:
            source = str(path)
        if source not in channels[channel_id]["sources"]:
            channels[channel_id]["sources"].append(source)

    for programme in root.findall("programme"):
        channel_id = programme.attrib["channel"]
        if channel_id not in channels:
            continue
        program = {
            "title": text(programme, "title") or "Untitled",
            "description": text(programme, "desc"),
            "startAt": isoformat(parse_xmltv_time(programme.attrib["start"])),
            "endAt": isoformat(parse_xmltv_time(programme.attrib["stop"])),
        }
        programs = programs_by_channel.setdefault(channel_id, [])
        duplicate = any(
            existing["title"] == program["title"]
            and existing["startAt"] == program["startAt"]
            and existing["endAt"] == program["endAt"]
            for existing in programs
        )
        if not duplicate:
            programs.append(program)


def build_country_payload(country_code: str, paths: list[Path], root_dir: Path, now: datetime) -> dict:
    channels = {}
    programs_by_channel = {}
    source_guides = []

    for path in paths:
        if not path.exists():
            continue
        try:
            source_guides.append(str(path.relative_to(root_dir)))
        except ValueError:
            source_guides.append(str(path))
        ingest_guide(path, channels, programs_by_channel, root_dir)

    rows = []
    for channel_id, channel in channels.items():
        programs = program_window(programs_by_channel.get(channel_id, []), now, hours=3)
        if not programs:
            continue
        rows.append(
            {
                **channel,
                "currentProgram": next(
                    (
                        program
                        for program in programs
                        if parse_iso_time(program["startAt"]) <= now < parse_iso_time(program["endAt"])
                    ),
                    None,
                ),
                "programs": programs,
            }
        )

    rows.sort(key=lambda channel: (channel["currentProgram"] is None, channel["name"].lower()))

    return {
        "country": country_code,
        "countryName": COUNTRY_NAMES.get(country_code, country_code),
        "generatedAt": isoformat(now),
        "windowHours": 3,
        "sourceGuides": source_guides,
        "channelCount": len(rows),
        "channels": rows,
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    for country_code, paths in GUIDES.items():
        payload = build_country_payload(country_code, paths, ROOT, now)
        out = WEB_DATA_DIR / f"{country_code}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        index.append(
            {
                "code": country_code,
                "name": COUNTRY_NAMES.get(country_code, country_code),
                "channelCount": payload["channelCount"],
                "dataUrl": f"data/{country_code}.json",
            }
        )

    countries = {"generatedAt": isoformat(now), "countries": index}
    (WEB_DATA_DIR / "countries.json").write_text(json.dumps(countries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(countries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
