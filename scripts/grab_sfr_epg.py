#!/usr/bin/env python3
"""Fetch SFR France's shared daily guide once, then select mapped channels."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ENDPOINT = "https://static-cdn.tv.sfr.net/data/epg/gen8"


def fetch_segment(url: str) -> dict:
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
                data = json.load(response)
            if not isinstance(data, dict) or not isinstance(data.get("epg"), dict):
                raise ValueError(f"Expected an EPG channel map from {url}")
            return data["epg"]
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def xmltv_time(value: str | int) -> str:
    parsed = (datetime.fromtimestamp(value / 1000, timezone.utc) if isinstance(value, (int, float))
              else datetime.fromisoformat(value.replace("Z", "+00:00")))
    return parsed.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S %z")


def build_guide(channels: ET.Element, segments: list[dict]) -> ET.ElementTree:
    tv = ET.Element("tv", {"generator-info-name": "heywhatson.tv SFR France"})
    by_site_id = {channel.get("site_id"): channel for channel in channels}
    for channel in channels:
        output = ET.SubElement(tv, "channel", {"id": channel.attrib["xmltv_id"]})
        ET.SubElement(output, "display-name", {"lang": "fr"}).text = channel.text
    programmes = {}
    for segment in segments:
        for site_id, events in segment.items():
            channel = by_site_id.get(str(site_id))
            if channel is None:
                continue
            channel_id = channel.attrib["xmltv_id"]
            for item in events:
                start, stop = xmltv_time(item["startDate"]), xmltv_time(item["endDate"])
                if stop <= start or not item.get("title"):
                    continue
                programme = ET.Element("programme", {"channel": channel_id, "start": start, "stop": stop})
                for tag, key in [("title", "title"), ("sub-title", "subTitle"), ("desc", "longSynopsis")]:
                    if item.get(key):
                        ET.SubElement(programme, tag, {"lang": "fr"}).text = item[key]
                if item.get("genre"):
                    ET.SubElement(programme, "category", {"lang": "fr"}).text = item["genre"]
                programmes[(channel_id, start, stop)] = programme
    for key in sorted(programmes):
        tv.append(programmes[key])
    if not programmes:
        raise ValueError("SFR returned no programmes for the selected channels")
    ET.indent(tv, space="  ")
    return ET.ElementTree(tv)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--days", type=int, default=3)
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")
    urls = [f"{ENDPOINT}/guide_web_{args.start_date + timedelta(days=day):%Y%m%d}.json"
            for day in range(args.days)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        segments = list(pool.map(fetch_segment, urls))
    tree = build_guide(ET.parse(args.channels).getroot(), segments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".xml.tmp")
    tree.write(temporary, encoding="utf-8", xml_declaration=True)
    temporary.replace(args.output)
    print(f"SFR: {len(urls)} requests, {len(tree.getroot().findall('programme'))} programmes", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
