#!/usr/bin/env python3
"""Build a UHF/XTream-specific XMLTV export from approved channel mappings.

This script is intentionally data-driven:

1. Refresh the upstream What's On TV XMLTV snapshots / web/data/epg.xml.
2. Rebuild data/uhf-channel-mapping.csv if the UHF channel list changed.
3. Run this script to emit an XMLTV file containing only rows marked `ok`.

Each UHF channel gets its own stable XMLTV channel id: `uhf:<uhf_pk>`.
That avoids collisions when several IPTV playlist rows map to the same guide
channel, and gives us a deterministic ID to write back into an M3U later.
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import re

ROOT = Path(__file__).resolve().parents[1]
MAPPING_CSV = ROOT / "data" / "uhf-channel-mapping.csv"
SOURCE_EPG_XML = ROOT / "web" / "data" / "epg.xml"
NORMALIZED_DIR = ROOT / "data" / "normalized"
OUT_DIR = ROOT / "web" / "data" / "uhf"
OUT_XML = OUT_DIR / "epg.xml"
OUT_GZ = OUT_DIR / "epg.xml.gz"
OUT_CHANNELS_CSV = OUT_DIR / "channels.csv"
OUT_CHANNELS_JSON = OUT_DIR / "channels.json"
OUT_SUMMARY_JSON = OUT_DIR / "summary.json"

CHANNEL_FIELDS = [
    "custom_xmltv_id",
    "uhf_pk",
    "category",
    "name",
    "target_xmltv_id",
    "target_name",
    "target_country",
    "target_guide_sites",
    "target_in_current_epg",
    "source_epg_channel_id",
    "logo_url",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def add_text(parent: ET.Element, tag: str, value: str | None, **attrs: str) -> ET.Element | None:
    if not value:
        return None
    child = ET.SubElement(parent, tag, attrs)
    child.text = value
    return child


def copy_child_texts(source: ET.Element, dest: ET.Element, tag: str) -> None:
    for child in source.findall(tag):
        if child.text:
            add_text(dest, tag, child.text, **child.attrib)


def copy_programme(source_programme: ET.Element, custom_channel_id: str) -> ET.Element:
    attrs = dict(source_programme.attrib)
    attrs["channel"] = custom_channel_id
    copied = ET.Element("programme", attrs)
    # Preserve normal XMLTV metadata used by the app and other guide clients.
    for child in list(source_programme):
        copied.append(copy_element(child))
    return copied


def copy_element(element: ET.Element) -> ET.Element:
    copied = ET.Element(element.tag, dict(element.attrib))
    copied.text = element.text
    copied.tail = element.tail
    for child in list(element):
        copied.append(copy_element(child))
    return copied


def load_ok_mappings() -> list[dict[str, str]]:
    if not MAPPING_CSV.exists():
        raise FileNotFoundError(f"Missing mapping CSV: {MAPPING_CSV}")
    with MAPPING_CSV.open(newline="", encoding="utf-8") as infile:
        rows = [row for row in csv.DictReader(infile) if row.get("review") == "ok" and row.get("target_xmltv_id")]
    for row in rows:
        row["custom_xmltv_id"] = f"uhf:{row['uhf_pk']}"
    rows.sort(key=lambda row: (row["target_country"], row["category"], row["name"], row["uhf_pk"]))
    return rows


def source_xml_files() -> list[Path]:
    files = []
    if SOURCE_EPG_XML.exists():
        files.append(SOURCE_EPG_XML)
    files.extend(sorted(NORMALIZED_DIR.glob("guide-uhf-*.xml")))
    if not files:
        raise FileNotFoundError(f"Missing source XMLTV: {SOURCE_EPG_XML} and no {NORMALIZED_DIR}/guide-uhf-*.xml")
    return files


def target_id_for_source_channel(path: Path, raw_id: str) -> str:
    if ":" in raw_id:
        return raw_id
    match = re.match(r"guide-uhf-([A-Z]+)-", path.name)
    if match:
        return f"{match.group(1)}:{raw_id}"
    # web/data/epg.xml already uses country-prefixed IDs, so this fallback is
    # only for malformed/legacy inputs.
    return raw_id


def source_epg_indexes() -> tuple[dict[str, ET.Element], dict[str, list[ET.Element]], list[str]]:
    channels: dict[str, ET.Element] = {}
    programmes_by_channel: dict[str, list[ET.Element]] = defaultdict(list)
    seen_programmes: set[tuple[str, str, str, str]] = set()
    source_files = source_xml_files()

    for source_file in source_files:
        root = ET.parse(source_file).getroot()
        for channel in root.findall("channel"):
            raw_id = channel.attrib["id"]
            target_id = target_id_for_source_channel(source_file, raw_id)
            if target_id not in channels:
                copied = copy_element(channel)
                copied.attrib["id"] = target_id
                channels[target_id] = copied
        for programme in root.findall("programme"):
            raw_channel_id = programme.attrib["channel"]
            target_id = target_id_for_source_channel(source_file, raw_channel_id)
            key = (
                target_id,
                programme.attrib.get("start", ""),
                programme.attrib.get("stop", ""),
                (programme.findtext("title") or ""),
            )
            if key in seen_programmes:
                continue
            seen_programmes.add(key)
            copied = copy_element(programme)
            copied.attrib["channel"] = target_id
            programmes_by_channel[target_id].append(copied)

    source_names = [str(path.relative_to(ROOT)) for path in source_files]
    return channels, dict(programmes_by_channel), source_names


def build_xmltv(rows: list[dict[str, str]]) -> tuple[ET.ElementTree, dict]:
    source_channels, source_programmes, source_files = source_epg_indexes()
    generated_at = now_utc()
    tv = ET.Element(
        "tv",
        {
            "generator-info-name": "heywhatson.tv UHF custom XMLTV",
            "generator-info-url": "https://heywhatson.tv",
            "source-info-name": "UHF OK mappings over curated XMLTV export",
            "date": generated_at,
        },
    )
    tv.append(ET.Comment(f" Generated from {MAPPING_CSV.relative_to(ROOT)} and {SOURCE_EPG_XML.relative_to(ROOT)} at {generated_at} "))

    included_rows = []
    missing_source_targets = []
    missing_programme_targets = []
    programme_count = 0

    for row in rows:
        target_id = row["target_xmltv_id"]
        source_channel = source_channels.get(target_id)
        programmes = source_programmes.get(target_id, [])
        if source_channel is None:
            missing_source_targets.append(target_id)
            continue
        if not programmes:
            missing_programme_targets.append(target_id)
            continue

        channel = ET.SubElement(tv, "channel", {"id": row["custom_xmltv_id"]})
        add_text(channel, "display-name", row["name"])
        add_text(channel, "display-name", row["target_name"])
        add_text(channel, "display-name", row["target_country"])
        logo = row.get("logo_url")
        if not logo:
            source_icon = source_channel.find("icon")
            logo = source_icon.attrib.get("src") if source_icon is not None else ""
        if logo:
            ET.SubElement(channel, "icon", {"src": logo})

        for programme in programmes:
            tv.append(copy_programme(programme, row["custom_xmltv_id"]))
            programme_count += 1
        included_rows.append(row)

    ET.indent(tv, space="  ")
    summary = {
        "generatedAt": generated_at,
        "mappingCsv": str(MAPPING_CSV.relative_to(ROOT)),
        "sourceEpgXml": str(SOURCE_EPG_XML.relative_to(ROOT)),
        "sourceXmlFiles": source_files,
        "outputXml": str(OUT_XML.relative_to(ROOT)),
        "outputGzip": str(OUT_GZ.relative_to(ROOT)),
        "okMappingRows": len(rows),
        "includedChannels": len(included_rows),
        "programmes": programme_count,
        "missingCurrentSourceTargets": len(set(missing_source_targets)),
        "missingProgrammeTargets": len(set(missing_programme_targets)),
        "includedByCategory": dict(Counter(row["category"] for row in included_rows)),
        "includedByCountry": dict(Counter(row["target_country"] for row in included_rows)),
        "duplicateTargetMappings": {
            target_id: count
            for target_id, count in Counter(row["target_xmltv_id"] for row in included_rows).items()
            if count > 1
        },
        "missingSourceTargetSamples": sorted(set(missing_source_targets))[:50],
        "missingProgrammeTargetSamples": sorted(set(missing_programme_targets))[:50],
    }
    return ET.ElementTree(tv), summary


def write_outputs(tree: ET.ElementTree, rows: list[dict[str, str]], summary: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tree.write(OUT_XML, encoding="utf-8", xml_declaration=True)
    with OUT_GZ.open("wb") as raw_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as gzip_file:
            tree.write(gzip_file, encoding="utf-8", xml_declaration=True)

    # The channel list is the rebuildable join table: UHF row -> custom XMLTV id -> source guide id.
    included_custom_ids = {
        channel.attrib["id"]
        for channel in ET.parse(OUT_XML).getroot().findall("channel")
    }
    included_rows = [row for row in rows if row["custom_xmltv_id"] in included_custom_ids]
    with OUT_CHANNELS_CSV.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=CHANNEL_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in CHANNEL_FIELDS} for row in included_rows])
    OUT_CHANNELS_JSON.write_text(json.dumps(included_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    rows = load_ok_mappings()
    tree, summary = build_xmltv(rows)
    write_outputs(tree, rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
