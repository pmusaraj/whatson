#!/usr/bin/env python3
"""Build a global 3-day XMLTV export from curated guide snapshots."""

from __future__ import annotations

import gzip
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import build_web_data

ROOT = Path(__file__).resolve().parents[1]
WEB_DATA_DIR = ROOT / "web" / "data"
GLOBAL_EPG_PATH = WEB_DATA_DIR / "epg.xml"
GLOBAL_EPG_GZ_PATH = WEB_DATA_DIR / "epg.xml.gz"


class ExportProgramme(dict):
    pass


def xmltv_time_to_sort_key(value: str) -> datetime:
    return build_web_data.parse_xmltv_time(value)


def channel_display_name(channel: ET.Element) -> str:
    return build_web_data.channel_display_name(channel)


def export_channel_id(country_code: str, raw_channel_id: str) -> str:
    return f"{country_code}:{raw_channel_id}"


def ingest_export_guide(
    country_code: str,
    guide: build_web_data.LocalGuide,
    channels: dict[str, dict],
    programmes_by_channel: dict[str, list[dict]],
    premium_sports_ids: set[str],
    premium_sports_only: bool,
) -> str | None:
    if not guide.path.exists():
        return None

    root = ET.parse(guide.path).getroot()
    included_raw_ids = set()

    for channel in root.findall("channel"):
        raw_id = channel.attrib["id"]
        name = channel_display_name(channel)
        if premium_sports_only and not build_web_data.is_premium_sports_channel(raw_id, name, premium_sports_ids):
            continue

        channel_id = export_channel_id(country_code, raw_id)
        icon = channel.find("icon")
        row = channels.setdefault(
            channel_id,
            {
                "id": channel_id,
                "rawId": raw_id,
                "country": country_code,
                "countryName": build_web_data.COUNTRY_NAMES.get(country_code, country_code),
                "name": name,
                "logoUrl": icon.attrib.get("src") if icon is not None else None,
                "providers": [],
                "sources": [],
            },
        )
        if not row.get("logoUrl") and icon is not None:
            row["logoUrl"] = icon.attrib.get("src")
        if guide.provider not in row["providers"]:
            row["providers"].append(guide.provider)
        try:
            source = str(guide.path.relative_to(ROOT))
        except ValueError:
            source = str(guide.path)
        if source not in row["sources"]:
            row["sources"].append(source)
        included_raw_ids.add(raw_id)

    for programme in root.findall("programme"):
        raw_channel_id = programme.attrib["channel"]
        if raw_channel_id not in included_raw_ids:
            continue
        channel_id = export_channel_id(country_code, raw_channel_id)
        title = build_web_data.text(programme, "title") or "Untitled"
        description = build_web_data.text(programme, "desc")
        categories = build_web_data.texts(programme, "category")
        export_programme = {
            "title": title,
            "subtitle": build_web_data.text(programme, "sub-title"),
            "description": description,
            "categories": categories,
            "imageUrl": build_web_data.first_image_url(programme),
            "start": programme.attrib["start"],
            "stop": programme.attrib["stop"],
            "startAt": build_web_data.isoformat(build_web_data.parse_xmltv_time(programme.attrib["start"])),
            "endAt": build_web_data.isoformat(build_web_data.parse_xmltv_time(programme.attrib["stop"])),
        }
        build_web_data.add_program(programmes_by_channel, channel_id, export_programme)

    try:
        return str(guide.path.relative_to(ROOT))
    except ValueError:
        return str(guide.path)


def build_global_export() -> tuple[dict[str, dict], dict[str, list[dict]], list[str]]:
    channels: dict[str, dict] = {}
    programmes_by_channel: dict[str, list[dict]] = {}
    source_guides: list[str] = []
    premium_sports_ids_by_country = build_web_data.premium_sports_channel_ids_by_country()

    for country_code, guides in build_web_data.GUIDES.items():
        premium_sports_ids = premium_sports_ids_by_country[country_code]
        for guide in guides:
            if not isinstance(guide, build_web_data.LocalGuide):
                continue
            source = ingest_export_guide(country_code, guide, channels, programmes_by_channel, premium_sports_ids, False)
            if source:
                source_guides.append(source)
        for guide in build_web_data.PREMIUM_SPORTS_GUIDES[country_code]:
            if not isinstance(guide, build_web_data.LocalGuide):
                continue
            source = ingest_export_guide(country_code, guide, channels, programmes_by_channel, premium_sports_ids, True)
            if source:
                source_guides.append(source)

    # Drop channels that ended up without programmes after filtering/deduping.
    channels = {channel_id: channel for channel_id, channel in channels.items() if programmes_by_channel.get(channel_id)}
    programmes_by_channel = {
        channel_id: sorted(programmes, key=lambda programme: (programme["startAt"], programme["endAt"], programme["title"]))
        for channel_id, programmes in programmes_by_channel.items()
        if channel_id in channels
    }
    return channels, programmes_by_channel, source_guides


def add_text(parent: ET.Element, tag: str, value: str | None, **attrs: str) -> ET.Element | None:
    if not value:
        return None
    child = ET.SubElement(parent, tag, attrs)
    child.text = value
    return child


def build_xmltv_tree(channels: dict[str, dict], programmes_by_channel: dict[str, list[dict]], source_guides: list[str]) -> ET.ElementTree:
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    tv = ET.Element(
        "tv",
        {
            "generator-info-name": "heywhatson.tv",
            "generator-info-url": "https://heywhatson.tv",
            "source-info-name": "Aggregated curated XMLTV snapshots",
            "date": generated_at,
        },
    )
    comment = ET.Comment(f" Generated from {len(source_guides)} source XMLTV snapshots at {generated_at} ")
    tv.append(comment)

    for channel_id, channel in sorted(channels.items(), key=lambda item: (item[1]["country"], item[1]["name"].lower(), item[0])):
        channel_element = ET.SubElement(tv, "channel", {"id": channel_id})
        add_text(channel_element, "display-name", channel["name"])
        add_text(channel_element, "display-name", channel["countryName"])
        if channel.get("logoUrl"):
            ET.SubElement(channel_element, "icon", {"src": channel["logoUrl"]})

    all_programmes = []
    for channel_id, programmes in programmes_by_channel.items():
        for programme in programmes:
            all_programmes.append((channel_id, programme))

    for channel_id, programme in sorted(all_programmes, key=lambda item: (item[1]["startAt"], item[0], item[1]["title"])):
        programme_element = ET.SubElement(
            tv,
            "programme",
            {
                "channel": channel_id,
                "start": programme["start"],
                "stop": programme["stop"],
            },
        )
        add_text(programme_element, "title", programme.get("title"))
        add_text(programme_element, "sub-title", programme.get("subtitle"))
        add_text(programme_element, "desc", programme.get("description"))
        for category in programme.get("categories") or []:
            add_text(programme_element, "category", category)
        if programme.get("imageUrl"):
            ET.SubElement(programme_element, "icon", {"src": programme["imageUrl"]})

    ET.indent(tv, space="  ")
    return ET.ElementTree(tv)


def write_xmltv(path: Path, tree: ET.ElementTree) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    with GLOBAL_EPG_GZ_PATH.open("wb") as raw_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as gzip_file:
            tree.write(gzip_file, encoding="utf-8", xml_declaration=True)


def main() -> int:
    channels, programmes_by_channel, source_guides = build_global_export()
    tree = build_xmltv_tree(channels, programmes_by_channel, source_guides)
    write_xmltv(GLOBAL_EPG_PATH, tree)
    programme_count = sum(len(programmes) for programmes in programmes_by_channel.values())
    print(
        f"Wrote {GLOBAL_EPG_PATH.relative_to(ROOT)} and {GLOBAL_EPG_GZ_PATH.relative_to(ROOT)} "
        f"with {len(channels)} channels and {programme_count} programmes from {len(source_guides)} source snapshots"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
