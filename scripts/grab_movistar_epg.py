#!/usr/bin/env python3
"""Read Movistar's public daily HTML schedules without optional detail/API calls."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
import time
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


class ScheduleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.entry = None
        self.div_depth = 0
        self.field = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "div":
            if self.entry is not None:
                self.div_depth += 1
            elif "container_box" in classes:
                self.entry = {}
                self.div_depth = 1
        if self.entry is not None and tag == "li":
            self.field = next((name for name in ("title", "time", "genre") if name in classes), None)

    def handle_data(self, data):
        if self.entry is not None and self.field:
            self.entry[self.field] = self.entry.get(self.field, "") + data

    def handle_endtag(self, tag):
        if tag == "li":
            self.field = None
        if tag == "div" and self.entry is not None:
            self.div_depth -= 1
            if not self.div_depth:
                entry = {key: " ".join(value.split()) for key, value in self.entry.items()}
                if entry.get("title") and entry.get("time"):
                    self.entries.append(entry)
                self.entry = None


def parse_schedule(html: str, day: date) -> list[dict]:
    parser = ScheduleParser()
    parser.feed(html)
    if not parser.entries:
        raise ValueError(f"No schedule entries for {day}")
    result = []
    current_day = day
    for item in parser.entries:
        hour, minute = map(int, item["time"].split(":"))
        start = datetime.combine(current_day, datetime.min.time()).replace(hour=hour, minute=minute, tzinfo=MADRID)
        start = start.astimezone(timezone.utc)
        if result and start < result[-1]["start"]:
            # The second occurrence of an autumn DST hour belongs to the same day.
            folded = start.astimezone(MADRID).replace(fold=1).astimezone(timezone.utc)
            if folded > result[-1]["start"]:
                start = folded
            else:
                current_day += timedelta(days=1)
                start = datetime.combine(current_day, datetime.min.time()).replace(hour=hour, minute=minute, tzinfo=MADRID).astimezone(timezone.utc)
        result.append({**item, "start": start})
    return result


def fetch_schedule(channel: ET.Element, day: date) -> tuple[str, list[dict]]:
    site_id = quote(channel.attrib["site_id"].lower(), safe="")
    url = f"https://www.movistarplus.es/programacion-tv/{site_id}/{day.isoformat()}"
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
                html = response.read().decode("utf-8")
            return channel.attrib["xmltv_id"], parse_schedule(html, day)
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def build_guide(channels: ET.Element, pages: list[tuple[str, list[dict]]], end_day: date) -> ET.ElementTree:
    tv = ET.Element("tv", {"generator-info-name": "heywhatson.tv Movistar public schedules"})
    by_channel = {}
    for channel in channels:
        channel_id = channel.attrib["xmltv_id"]
        by_channel[channel_id] = {}
        ET.SubElement(ET.SubElement(tv, "channel", id=channel_id), "display-name", lang="es").text = channel.text
    for channel_id, entries in pages:
        for entry in entries:
            by_channel[channel_id][entry["start"]] = entry
    for channel_id, entries in by_channel.items():
        ordered = sorted(entries.values(), key=lambda entry: entry["start"])
        # A following start is the evidence for the previous programme's end.
        # Fetch an extra day to supply that boundary; never invent a final stop.
        for entry, following in zip(ordered, ordered[1:]):
            if entry["start"].astimezone(MADRID).date() >= end_day:
                continue
            attrs = {"channel": channel_id, "start": entry["start"].strftime("%Y%m%d%H%M%S %z"),
                     "stop": following["start"].strftime("%Y%m%d%H%M%S %z")}
            programme = ET.SubElement(tv, "programme", attrs)
            ET.SubElement(programme, "title", lang="es").text = entry["title"]
            if entry.get("genre"):
                ET.SubElement(programme, "category", lang="es").text = entry["genre"]
    if not tv.findall("programme"):
        raise ValueError("No programmes with known end times")
    ET.indent(tv, space="  ")
    return ET.ElementTree(tv)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=3)
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")
    channels = ET.parse(args.channels).getroot()
    jobs = [(channel, args.start_date + timedelta(days=offset)) for channel in channels for offset in range(args.days + 1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = list(pool.map(lambda job: fetch_schedule(*job), jobs))
    tree = build_guide(channels, pages, args.start_date + timedelta(days=args.days))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".xml.tmp")
    tree.write(temporary, encoding="utf-8", xml_declaration=True)
    temporary.replace(args.output)
    print(f"Movistar: {len(jobs)} pages, {len(tree.getroot().findall('programme'))} programmes", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
