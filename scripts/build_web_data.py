#!/usr/bin/env python3
"""Build browser-friendly JSON from XMLTV guide snapshots and FAST sports feeds."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
WEB_DATA_DIR = ROOT / "web" / "data"

COUNTRY_NAMES = {
    "FR": "France",
    "ES": "Spain",
    "CA": "Canada",
}

IPTV_CHANNELS_API = "https://iptv-org.github.io/api/channels.json"

SPORTS_TERMS = re.compile(
    r"\b(sport|sports|football|soccer|fifa|liga|laliga|champions|nba|nfl|nhl|mlb|tsn|"
    r"sportsnet|eurosport|tennis|golf|fight|boxing|mma|ufc|racing|motor|f1|formula|"
    r"skate|surf|ski|cycling|bike|poker|darts|cricket|rugby|wrestling)\b",
    re.I,
)

SPORTS_ID_TERMS = re.compile(
    r"(Sport|Sports|Eurosport|TSN|Sportsnet|LaLiga|NBA|NFL|NHL|MLB|UFC|FIFA|Golf|Tennis|Fight|Racing)",
    re.I,
)


class LocalGuide(NamedTuple):
    path: Path
    provider: str
    provider_key: str


class RemoteGuide(NamedTuple):
    url: str
    provider: str
    provider_key: str


GUIDES = {
    "FR": [LocalGuide(NORMALIZED_DIR / "guide-FR-tv.sfr.fr.xml", "Validated grabber", "validated")],
    "ES": [
        LocalGuide(NORMALIZED_DIR / "guide-ES-programacion-tv.elpais.com.xml", "Validated grabber", "validated"),
        LocalGuide(NORMALIZED_DIR / "guide-ES-orangetv.orange.es.xml", "Validated grabber", "validated"),
    ],
    "CA": [
        LocalGuide(NORMALIZED_DIR / "guide-CA-tvpassport.com.xml", "Validated grabber", "validated"),
        LocalGuide(NORMALIZED_DIR / "guide-CA-tvhebdo.com.xml", "Validated grabber", "validated"),
    ],
}

FAST_SPORTS_GUIDES = {
    country: [
        RemoteGuide(f"https://i.mjh.nz/PlutoTV/{country.lower()}.xml", "Pluto TV", "plutotv"),
        RemoteGuide(f"https://i.mjh.nz/SamsungTVPlus/{country.lower()}.xml", "Samsung TV Plus", "samsungtvplus"),
        RemoteGuide(f"https://i.mjh.nz/Plex/{country.lower()}.xml", "Plex", "plex"),
    ]
    for country in COUNTRY_NAMES
}


def fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def sports_channel_ids_by_country() -> dict[str, set[str]]:
    result = {country: set() for country in COUNTRY_NAMES}
    loaded_local = False

    for country in COUNTRY_NAMES:
        path = ROOT / "data" / "sources" / "iptv-org" / f"channels-{country}.json"
        if not path.exists():
            continue
        loaded_local = True
        for channel in json.loads(path.read_text(encoding="utf-8")):
            if "sports" in (channel.get("categories") or []):
                result[country].add(channel.get("id"))

    if loaded_local:
        return result

    try:
        channels = fetch_json(IPTV_CHANNELS_API)
    except Exception:
        return result

    for channel in channels:
        country = channel.get("country")
        if country not in result or channel.get("closed"):
            continue
        if "sports" in (channel.get("categories") or []):
            result[country].add(channel.get("id"))
    return result


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


def channel_display_name(channel: ET.Element) -> str:
    names = [child.text.strip() for child in channel.findall("display-name") if child.text and child.text.strip()]
    return names[0] if names else channel.attrib["id"]


def is_sports_channel(channel_id: str, name: str, sports_ids: set[str]) -> bool:
    return channel_id in sports_ids or bool(SPORTS_TERMS.search(name)) or bool(SPORTS_ID_TERMS.search(channel_id))


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


def add_program(programs_by_channel: dict, channel_id: str, program: dict) -> None:
    programs = programs_by_channel.setdefault(channel_id, [])
    duplicate = any(
        existing["title"] == program["title"]
        and existing["startAt"] == program["startAt"]
        and existing["endAt"] == program["endAt"]
        for existing in programs
    )
    if not duplicate:
        programs.append(program)


def ingest_xmltv_root(
    root: ET.Element,
    source: str,
    provider: str,
    provider_key: str,
    channels: dict,
    programs_by_channel: dict,
    sports_ids: set[str],
    sports_only: bool,
) -> None:
    included_ids = set()

    for channel in root.findall("channel"):
        raw_id = channel.attrib["id"]
        channel_id = f"{provider_key}:{raw_id}"
        name = channel_display_name(channel)
        if sports_only and not is_sports_channel(raw_id, name, sports_ids):
            continue

        icon = channel.find("icon")
        channels.setdefault(
            channel_id,
            {
                "id": channel_id,
                "name": name,
                "logoUrl": icon.attrib.get("src") if icon is not None else None,
                "provider": provider,
                "providerKey": provider_key,
                "sources": [],
            },
        )
        if source not in channels[channel_id]["sources"]:
            channels[channel_id]["sources"].append(source)
        included_ids.add(raw_id)

    for programme in root.findall("programme"):
        raw_channel_id = programme.attrib["channel"]
        if raw_channel_id not in included_ids:
            continue
        channel_id = f"{provider_key}:{raw_channel_id}"
        program = {
            "title": text(programme, "title") or "Untitled",
            "description": text(programme, "desc"),
            "startAt": isoformat(parse_xmltv_time(programme.attrib["start"])),
            "endAt": isoformat(parse_xmltv_time(programme.attrib["stop"])),
        }
        add_program(programs_by_channel, channel_id, program)


def ingest_local_guide(
    guide: LocalGuide,
    channels: dict,
    programs_by_channel: dict,
    root_dir: Path,
    sports_ids: set[str],
    sports_only: bool,
) -> str | None:
    if not guide.path.exists():
        return None
    try:
        source = str(guide.path.relative_to(root_dir))
    except ValueError:
        source = str(guide.path)
    ingest_xmltv_root(ET.parse(guide.path).getroot(), source, guide.provider, guide.provider_key, channels, programs_by_channel, sports_ids, sports_only)
    return source


def ingest_remote_guide(
    guide: RemoteGuide,
    channels: dict,
    programs_by_channel: dict,
    sports_ids: set[str],
    sports_only: bool,
) -> str | None:
    try:
        root = ET.fromstring(fetch_bytes(guide.url))
    except Exception as error:
        print(f"warning: failed to load {guide.url}: {error}", file=sys.stderr)
        return None
    ingest_xmltv_root(root, guide.url, guide.provider, guide.provider_key, channels, programs_by_channel, sports_ids, sports_only)
    return guide.url


def build_country_payload(
    country_code: str,
    guides: list[LocalGuide | RemoteGuide],
    root_dir: Path,
    now: datetime,
    sports_only: bool = False,
    sports_ids: set[str] | None = None,
) -> dict:
    channels = {}
    programs_by_channel = {}
    source_guides = []
    sports_ids = sports_ids or set()

    for guide in guides:
        source = None
        if isinstance(guide, LocalGuide):
            source = ingest_local_guide(guide, channels, programs_by_channel, root_dir, sports_ids, sports_only)
        else:
            source = ingest_remote_guide(guide, channels, programs_by_channel, sports_ids, sports_only)
        if source:
            source_guides.append(source)

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

    rows.sort(key=lambda channel: (channel["currentProgram"] is None, channel["provider"], channel["name"].lower()))

    return {
        "country": country_code,
        "countryName": COUNTRY_NAMES.get(country_code, country_code),
        "generatedAt": isoformat(now),
        "windowHours": 3,
        "sportsOnly": sports_only,
        "sourceGuides": source_guides,
        "channelCount": len(rows),
        "channels": rows,
    }


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    sports_ids = sports_channel_ids_by_country()

    index = []
    for country_code, guides in GUIDES.items():
        payload = build_country_payload(country_code, guides, ROOT, now, sports_ids=sports_ids[country_code])
        out = WEB_DATA_DIR / f"{country_code}.json"
        write_json(out, payload)

        sports_guides = [*guides, *FAST_SPORTS_GUIDES[country_code]]
        sports_payload = build_country_payload(
            country_code,
            sports_guides,
            ROOT,
            now,
            sports_only=True,
            sports_ids=sports_ids[country_code],
        )
        sports_out = WEB_DATA_DIR / f"sports-{country_code}.json"
        write_json(sports_out, sports_payload)

        index.append(
            {
                "code": country_code,
                "name": COUNTRY_NAMES.get(country_code, country_code),
                "channelCount": payload["channelCount"],
                "sportsChannelCount": sports_payload["channelCount"],
                "dataUrl": f"data/{country_code}.json",
                "sportsDataUrl": f"data/sports-{country_code}.json",
            }
        )

    countries = {"generatedAt": isoformat(now), "countries": index}
    write_json(WEB_DATA_DIR / "countries.json", countries)
    print(json.dumps(countries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
