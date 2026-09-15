#!/usr/bin/env python3
"""Fetch Virgin UK's shared daily segments once, then select mapped channels."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ENDPOINT = "https://staticqbr-prod-gb.gnp.cloud.virgintvgo.virginmedia.com/eng/web/epg-service-lite/gb/en/events/segments"


def fetch_segment(url: str) -> list[dict]:
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
                data = json.load(response)
            if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
                raise ValueError(f"Expected a channel array from {url}")
            return data["entries"]
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def xmltv_time(value: str | int) -> str:
    parsed = (datetime.fromtimestamp(value, timezone.utc) if isinstance(value, (int, float))
              else datetime.fromisoformat(value.replace("Z", "+00:00")))
    return parsed.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S %z")


def build_guide(channels: ET.Element, segments: list[list[dict]]) -> ET.ElementTree:
    tv = ET.Element("tv", {"generator-info-name": "heywhatson.tv Virgin UK"})
    by_site_id = {channel.get("site_id"): channel for channel in channels}
    for channel in channels:
        output = ET.SubElement(tv, "channel", {"id": channel.attrib["xmltv_id"]})
        ET.SubElement(output, "display-name", {"lang": "en"}).text = channel.text
    programmes = {}
    for segment in segments:
        for listing in segment:
            channel = by_site_id.get(str(listing.get("channelId")))
            if channel is None:
                continue
            channel_id = channel.attrib["xmltv_id"]
            for item in listing.get("events", []):
                start, stop = xmltv_time(item["startTime"]), xmltv_time(item["endTime"])
                if stop <= start or not item.get("title"):
                    continue
                programme = ET.Element("programme", {"channel": channel_id, "start": start, "stop": stop})
                for tag, key in [("title", "title"), ("sub-title", "seriesName"), ("desc", "description")]:
                    if item.get(key):
                        ET.SubElement(programme, tag, {"lang": "en"}).text = item[key]
                programmes[(channel_id, start, stop)] = programme
    for key in sorted(programmes):
        tv.append(programmes[key])
    if not programmes:
        raise ValueError("Virgin returned no programmes for the selected channels")
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
    urls = [f"{ENDPOINT}/{args.start_date + timedelta(days=day):%Y%m%d}{segment:02d}0000"
            for day in range(args.days) for segment in (0, 6, 12, 18)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        segments = list(pool.map(fetch_segment, urls))
    tree = build_guide(ET.parse(args.channels).getroot(), segments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".xml.tmp")
    tree.write(temporary, encoding="utf-8", xml_declaration=True)
    temporary.replace(args.output)
    print(f"Virgin: {len(urls)} requests, {len(tree.getroot().findall('programme'))} programmes", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
