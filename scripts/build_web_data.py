#!/usr/bin/env python3
"""Build browser-friendly JSON from XMLTV guide snapshots and premium sports feeds."""

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
    "US": "United States",
    "UK": "United Kingdom",
    "IT": "Italy",
    "DE": "Germany",
    "TR": "Turkiye",
    "PT": "Portugal",
    "MX": "Mexico",
    "BR": "Brazil",
}

IPTV_CHANNELS_API = "https://iptv-org.github.io/api/channels.json"
PROGRAM_WINDOW_START_OFFSET_HOURS = 4
PROGRAM_WINDOW_HOURS = 24

PREMIUM_SPORTS_TERMS = re.compile(
    r"(canal\+|canal plus|bein|dazn|rmc sport|eurosport|multisports|infosport|"
    r"movistar|laliga|liga de campeones|champions|vamos|deportes|golf|"
    r"tsn|sportsnet|rds|tva sports|cbs sports|espn|fox sports|fs1|fs2|"
    r"nbc sports|nfl network|mlb network|nba tv|tennis channel|sky sports|"
    r"tnt sports|premier sports|sky sport|rai sport|sportitalia|sport tv|"
    r"sporttv|s sport|trt spor|sportdigital|benfica tv|sporting tv|tudn|"
    r"claro sports|sporTV|premiere clubes|combate|band sports)",
    re.I,
)

PREMIUM_SPORTS_ID_TERMS = re.compile(
    r"(CanalPlus|beIN|DAZN|RMCSport|Eurosport|MultiSports|InfosportPlus|"
    r"Movistar|LaLiga|LigadeCampeones|Vamos|Deportes|Golf|TSN|Sportsnet|RDS|TVASports|CBSSports|"
    r"ESPN|FoxSports|NBCSports|NFLNetwork|MLBNetwork|NBATV|TennisChannel|SkySports|TNTSports|"
    r"PremierSports|SkySport|RaiSport|Sportitalia|SportTV|SSport|TRTSpor|Sportdigital|BenficaTV|SportingTV|"
    r"TUDN|ClaroSports|SporTV|PremiereClubes|Combate|BandSports)",
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
    "US": [
        LocalGuide(NORMALIZED_DIR / "guide-US-tvtv.us.xml", "TVTV US guide", "tvtv-us"),
        LocalGuide(NORMALIZED_DIR / "guide-US-tvguide.com.xml", "TV Guide US guide", "tvguide-us"),
    ],
    "UK": [
        LocalGuide(NORMALIZED_DIR / "guide-UK-mytelly.co.uk.xml", "MyTelly UK guide", "mytelly-uk"),
        LocalGuide(NORMALIZED_DIR / "guide-UK-sky.com.xml", "Sky UK guide", "sky-uk"),
    ],
    "IT": [
        LocalGuide(NORMALIZED_DIR / "guide-IT-guidatv.sky.it.xml", "Sky Italia guide", "sky-it"),
        LocalGuide(NORMALIZED_DIR / "guide-IT-superguidatv.it.xml", "Super Guida TV guide", "superguidatv-it"),
    ],
    "DE": [
        LocalGuide(NORMALIZED_DIR / "guide-DE-web.magentatv.de.xml", "MagentaTV Germany guide", "magenta-de"),
        LocalGuide(NORMALIZED_DIR / "guide-DE-sky.de.xml", "Sky Germany guide", "sky-de"),
    ],
    "TR": [
        LocalGuide(NORMALIZED_DIR / "guide-TR-tvplus.com.tr.xml", "TV+ Turkiye guide", "tvplus-tr"),
        LocalGuide(NORMALIZED_DIR / "guide-TR-digiturk.com.tr.xml", "Digiturk guide", "digiturk-tr"),
    ],
    "PT": [
        LocalGuide(NORMALIZED_DIR / "guide-PT-meo.pt.xml", "MEO Portugal guide", "meo-pt"),
        LocalGuide(NORMALIZED_DIR / "guide-PT-nostv.pt.xml", "NOS Portugal guide", "nos-pt"),
        LocalGuide(NORMALIZED_DIR / "guide-PT-vodafone.pt.xml", "Vodafone Portugal guide", "vodafone-pt"),
    ],
    "MX": [
        LocalGuide(NORMALIZED_DIR / "guide-MX-gatotv.com.xml", "GatoTV Mexico guide", "gatotv-mx"),
    ],
    "BR": [
        LocalGuide(NORMALIZED_DIR / "guide-BR-mi.tv_br.xml", "Mi.tv Brazil guide", "mitv-br"),
    ],
}

PREMIUM_SPORTS_GUIDES = {
    "FR": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-FR-canalplus.com.xml", "Canal+ guide", "premium-canalplus"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-FR-tv.sfr.fr.xml", "SFR guide", "premium-sfr"),
    ],
    "ES": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-ES-orangetv.orange.es.xml", "Orange Spain guide", "premium-orange-es"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-ES-programacion-tv.elpais.com.xml", "El País guide", "premium-elpais"),
    ],
    "CA": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-CA-tvpassport.com.xml", "TV Passport guide", "premium-tvpassport"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-CA-tvhebdo.com.xml", "TV Hebdo guide", "premium-tvhebdo"),
    ],
    "US": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-US-tvtv.us.xml", "TVTV US sports guide", "premium-tvtv-us"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-US-tvguide.com.xml", "TV Guide US sports guide", "premium-tvguide-us"),
    ],
    "UK": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-UK-virgintvgo.virginmedia.com.xml", "Virgin TV Go UK sports guide", "premium-virgin-uk"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-UK-sky.com.xml", "Sky UK sports guide", "premium-sky-uk"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-UK-mytelly.co.uk.xml", "MyTelly UK sports guide", "premium-mytelly-uk"),
    ],
    "IT": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-IT-guidatv.sky.it.xml", "Sky Italia sports guide", "premium-sky-it"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-IT-superguidatv.it.xml", "Super Guida TV sports guide", "premium-superguidatv-it"),
    ],
    "DE": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-DE-sky.de.xml", "Sky Germany sports guide", "premium-sky-de"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-DE-web.magentatv.de.xml", "MagentaTV Germany sports guide", "premium-magenta-de"),
    ],
    "TR": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-TR-digiturk.com.tr.xml", "Digiturk sports guide", "premium-digiturk-tr"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-TR-tvplus.com.tr.xml", "TV+ Turkiye sports guide", "premium-tvplus-tr"),
    ],
    "PT": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-PT-meo.pt.xml", "MEO Portugal sports guide", "premium-meo-pt"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-PT-nostv.pt.xml", "NOS Portugal sports guide", "premium-nos-pt"),
        LocalGuide(NORMALIZED_DIR / "guide-premium-PT-vodafone.pt.xml", "Vodafone Portugal sports guide", "premium-vodafone-pt"),
    ],
    "MX": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-MX-gatotv.com.xml", "GatoTV Mexico sports guide", "premium-gatotv-mx"),
    ],
    "BR": [
        LocalGuide(NORMALIZED_DIR / "guide-premium-BR-mi.tv_br.xml", "Mi.tv Brazil sports guide", "premium-mitv-br"),
    ],
}


def fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def premium_sports_channel_ids_by_country() -> dict[str, set[str]]:
    result = {country: set() for country in COUNTRY_NAMES}
    loaded_local = False

    for country in COUNTRY_NAMES:
        path = ROOT / "data" / "sources" / "iptv-org" / f"channels-{country}.json"
        if not path.exists():
            continue
        loaded_local = True
        for channel in json.loads(path.read_text(encoding="utf-8")):
            if "sports" in (channel.get("categories") or []) and is_premium_sports_channel(
                channel.get("id", ""), channel.get("name", ""), set()
            ):
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


def texts(element: ET.Element, selector: str) -> list[str]:
    values = []
    for child in element.findall(selector):
        if child.text and child.text.strip():
            values.append(child.text.strip())
    return values


def first_image_url(programme: ET.Element) -> str | None:
    for selector in ("image", "icon"):
        child = programme.find(selector)
        if child is not None:
            src = child.attrib.get("src") or child.text
            if src and src.strip():
                return src.strip()
    return None


def infer_sport_type(title: str, description: str | None, categories: list[str]) -> str | None:
    haystack = " ".join([title, description or "", *categories]).lower()
    sport_terms = [
        ("Football", r"football|fútbol|soccer|premier league|laliga|liga de campeones|champions league|ligue 1"),
        ("Formula 1", r"formule 1|formula 1|\bf1\b|grand prix|auto racing|automobilisme"),
        ("Hockey", r"hockey|\bnhl\b"),
        ("Tennis", r"tennis|open de madrid|madrid open|roland-garros|wimbledon|atp|wta"),
        ("Baseball", r"baseball|\bmlb\b"),
        ("Basketball", r"basket-ball|basketball|\bnba\b"),
        ("Golf", r"\bgolf\b"),
        ("Rugby", r"rugby"),
        ("Combat sports", r"boxe|boxing|arts martiaux|sports de combat|mma|ufc"),
        ("Motorsport", r"motocyclisme|motorsport|nascar|indycar"),
        ("Curling", r"curling"),
        ("Watersports", r"sports nautiques|watersports"),
    ]
    for label, pattern in sport_terms:
        if re.search(pattern, haystack, re.I):
            return label
    if any(category.lower() in {"sports", "deportes", "magazine sportif", "programme sportif"} for category in categories):
        return "Sports"
    return None


def infer_competition(title: str, description: str | None, categories: list[str]) -> str | None:
    haystack = " ".join([title, description or "", *categories]).lower()
    competition_terms = [
        ("Champions League", r"champions league|liga de campeones"),
        ("LaLiga Hypermotion", r"laliga hypermotion"),
        ("LaLiga", r"laliga ea sports|\blaliga\b"),
        ("Premier League", r"premier league"),
        ("Formula 1", r"formule 1|formula 1|\bf1\b"),
        ("NHL", r"\bnhl\b"),
        ("MLB", r"\bmlb\b"),
        ("NBA", r"\bnba\b"),
        ("Madrid Open", r"mutua madrid open|madrid open"),
    ]
    for label, pattern in competition_terms:
        if re.search(pattern, haystack, re.I):
            return label
    return None


def channel_display_name(channel: ET.Element) -> str:
    names = [child.text.strip() for child in channel.findall("display-name") if child.text and child.text.strip()]
    return names[0] if names else channel.attrib["id"]


def is_premium_sports_channel(channel_id: str, name: str, premium_sports_ids: set[str]) -> bool:
    return channel_id in premium_sports_ids or bool(PREMIUM_SPORTS_TERMS.search(name)) or bool(PREMIUM_SPORTS_ID_TERMS.search(channel_id))


def program_window(
    programs: list[dict],
    now: datetime,
    hours: int = PROGRAM_WINDOW_HOURS,
    start_offset_hours: int = PROGRAM_WINDOW_START_OFFSET_HOURS,
) -> list[dict]:
    window_start = now - timedelta(hours=start_offset_hours)
    window_end = window_start + timedelta(hours=hours)
    window = []
    for program in programs:
        start_at = parse_iso_time(program["startAt"])
        end_at = parse_iso_time(program["endAt"])
        if end_at <= window_start:
            continue
        if start_at >= window_end:
            continue
        window.append(program)
    return sorted(window, key=lambda program: program["startAt"])


def metadata_score(program: dict) -> int:
    return sum(
        1
        for key in ("subtitle", "description", "imageUrl", "sportType", "competition")
        if program.get(key)
    ) + len(program.get("categories") or [])


def add_program(programs_by_channel: dict, channel_id: str, program: dict) -> None:
    programs = programs_by_channel.setdefault(channel_id, [])
    for index, existing in enumerate(programs):
        same_slot = existing["startAt"] == program["startAt"] and existing["endAt"] == program["endAt"]
        overlapping_duplicate = program_overlap_ratio(existing, program) >= 0.5
        if same_slot or overlapping_duplicate:
            if metadata_score(program) > metadata_score(existing):
                programs[index] = program
            return
    programs.append(program)


def program_overlap_ratio(a: dict, b: dict) -> float:
    start_a = parse_iso_time(a["startAt"])
    end_a = parse_iso_time(a["endAt"])
    start_b = parse_iso_time(b["startAt"])
    end_b = parse_iso_time(b["endAt"])
    overlap = min(end_a, end_b) - max(start_a, start_b)
    if overlap.total_seconds() <= 0:
        return 0
    shorter_duration = min(end_a - start_a, end_b - start_b).total_seconds()
    if shorter_duration <= 0:
        return 0
    return overlap.total_seconds() / shorter_duration


def ingest_xmltv_root(
    root: ET.Element,
    source: str,
    provider: str,
    provider_key: str,
    channels: dict,
    programs_by_channel: dict,
    premium_sports_ids: set[str],
    premium_sports_only: bool,
) -> None:
    included_ids = set()

    for channel in root.findall("channel"):
        raw_id = channel.attrib["id"]
        channel_id = raw_id if premium_sports_only else f"{provider_key}:{raw_id}"
        name = channel_display_name(channel)
        if premium_sports_only and not is_premium_sports_channel(raw_id, name, premium_sports_ids):
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
        channel_id = raw_channel_id if premium_sports_only else f"{provider_key}:{raw_channel_id}"
        title = text(programme, "title") or "Untitled"
        description = text(programme, "desc")
        categories = texts(programme, "category")
        program = {
            "title": title,
            "subtitle": text(programme, "sub-title"),
            "description": description,
            "categories": categories,
            "sportType": infer_sport_type(title, description, categories),
            "competition": infer_competition(title, description, categories),
            "imageUrl": first_image_url(programme),
            "startAt": isoformat(parse_xmltv_time(programme.attrib["start"])),
            "endAt": isoformat(parse_xmltv_time(programme.attrib["stop"])),
        }
        add_program(programs_by_channel, channel_id, program)


def ingest_local_guide(
    guide: LocalGuide,
    channels: dict,
    programs_by_channel: dict,
    root_dir: Path,
    premium_sports_ids: set[str],
    premium_sports_only: bool,
) -> str | None:
    if not guide.path.exists():
        return None
    try:
        source = str(guide.path.relative_to(root_dir))
    except ValueError:
        source = str(guide.path)
    ingest_xmltv_root(
        ET.parse(guide.path).getroot(),
        source,
        guide.provider,
        guide.provider_key,
        channels,
        programs_by_channel,
        premium_sports_ids,
        premium_sports_only,
    )
    return source


def ingest_remote_guide(
    guide: RemoteGuide,
    channels: dict,
    programs_by_channel: dict,
    premium_sports_ids: set[str],
    premium_sports_only: bool,
) -> str | None:
    try:
        root = ET.fromstring(fetch_bytes(guide.url))
    except Exception as error:
        print(f"warning: failed to load {guide.url}: {error}", file=sys.stderr)
        return None
    ingest_xmltv_root(root, guide.url, guide.provider, guide.provider_key, channels, programs_by_channel, premium_sports_ids, premium_sports_only)
    return guide.url


def build_country_payload(
    country_code: str,
    guides: list[LocalGuide | RemoteGuide],
    root_dir: Path,
    now: datetime,
    premium_sports_only: bool = False,
    premium_sports_ids: set[str] | None = None,
) -> dict:
    channels = {}
    programs_by_channel = {}
    source_guides = []
    premium_sports_ids = premium_sports_ids or set()

    for guide in guides:
        source = None
        if isinstance(guide, LocalGuide):
            source = ingest_local_guide(guide, channels, programs_by_channel, root_dir, premium_sports_ids, premium_sports_only)
        else:
            source = ingest_remote_guide(guide, channels, programs_by_channel, premium_sports_ids, premium_sports_only)
        if source:
            source_guides.append(source)

    rows = []
    for channel_id, channel in channels.items():
        programs = program_window(programs_by_channel.get(channel_id, []), now)
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
        "windowHours": PROGRAM_WINDOW_HOURS,
        "windowStartOffsetHours": PROGRAM_WINDOW_START_OFFSET_HOURS,
        "premiumSportsOnly": premium_sports_only,
        "sourceGuides": source_guides,
        "channelCount": len(rows),
        "channels": rows,
    }


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    premium_sports_ids = premium_sports_channel_ids_by_country()

    index = []
    for country_code, guides in GUIDES.items():
        payload = build_country_payload(country_code, guides, ROOT, now, premium_sports_ids=premium_sports_ids[country_code])
        out = WEB_DATA_DIR / f"{country_code}.json"
        write_json(out, payload)

        premium_payload = build_country_payload(
            country_code,
            PREMIUM_SPORTS_GUIDES[country_code],
            ROOT,
            now,
            premium_sports_only=True,
            premium_sports_ids=premium_sports_ids[country_code],
        )
        premium_out = WEB_DATA_DIR / f"premium-{country_code}.json"
        write_json(premium_out, premium_payload)

        index.append(
            {
                "code": country_code,
                "name": COUNTRY_NAMES.get(country_code, country_code),
                "channelCount": payload["channelCount"],
                "premiumChannelCount": premium_payload["channelCount"],
                "dataUrl": f"data/{country_code}.json",
                "premiumDataUrl": f"data/premium-{country_code}.json",
            }
        )

    countries = {"generatedAt": isoformat(now), "countries": index}
    write_json(WEB_DATA_DIR / "countries.json", countries)
    print(json.dumps(countries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
