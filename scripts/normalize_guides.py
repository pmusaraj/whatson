#!/usr/bin/env python3
"""Normalize generated XMLTV guide files into current-program samples."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"

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


def parse_xmltv_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d%H%M%S %z").astimezone(timezone.utc)


def text(element: ET.Element, selector: str) -> str | None:
    child = element.find(selector)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def ingest_guide(path: Path, channels: dict, first_program_by_channel: dict, now: datetime) -> None:
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
                "currentProgram": None,
                "programCount": 0,
                "sources": [],
            },
        )
        channels[channel_id]["sources"].append(str(path.relative_to(ROOT)))

    for programme in root.findall("programme"):
        channel_id = programme.attrib["channel"]
        start_at = parse_xmltv_time(programme.attrib["start"])
        end_at = parse_xmltv_time(programme.attrib["stop"])
        program = {
            "title": text(programme, "title"),
            "description": text(programme, "desc"),
            "startAt": start_at.isoformat().replace("+00:00", "Z"),
            "endAt": end_at.isoformat().replace("+00:00", "Z"),
        }
        if channel_id in channels:
            channels[channel_id]["programCount"] += 1
            first_program_by_channel.setdefault(channel_id, program)
            if start_at <= now < end_at:
                channels[channel_id]["currentProgram"] = program


def normalize_guides(country_code: str, paths: list[Path], now: datetime) -> dict:
    channels = {}
    first_program_by_channel = {}
    source_guides = []

    for path in paths:
        if not path.exists():
            continue
        source_guides.append(str(path.relative_to(ROOT)))
        ingest_guide(path, channels, first_program_by_channel, now)

    normalized_channels = []
    for channel in channels.values():
        sample = dict(channel)
        sample["sampleProgram"] = first_program_by_channel.get(channel["id"])
        normalized_channels.append(sample)

    normalized_channels.sort(key=lambda channel: (channel["currentProgram"] is None, channel["name"]))

    return {
        "country": country_code,
        "sourceGuides": source_guides,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "channelCount": len(channels),
        "channelsWithPrograms": sum(1 for c in channels.values() if c["programCount"] > 0),
        "channelsWithCurrentProgram": sum(1 for c in channels.values() if c["currentProgram"]),
        "channels": normalized_channels,
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    summary = {}
    for country_code, paths in GUIDES.items():
        existing = [path for path in paths if path.exists()]
        if not existing:
            print(f"missing guides for {country_code}", file=sys.stderr)
            continue
        data = normalize_guides(country_code, existing, now)
        out = NORMALIZED_DIR / f"current-sample-{country_code}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary[country_code] = {
            "guides": data["sourceGuides"],
            "currentSample": str(out.relative_to(ROOT)),
            "channelCount": data["channelCount"],
            "channelsWithPrograms": data["channelsWithPrograms"],
            "channelsWithCurrentProgram": data["channelsWithCurrentProgram"],
        }

    out = NORMALIZED_DIR / "current-sample-summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
