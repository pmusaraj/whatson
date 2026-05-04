#!/usr/bin/env python3
"""Generate iptv-org metadata and custom grabber channel lists for expanded countries."""

from __future__ import annotations

import html
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "iptv-org"
EPG_SITES_DIR = ROOT / ".cache" / "epg" / "sites"

API = {
    "countries": "https://iptv-org.github.io/api/countries.json",
    "channels": "https://iptv-org.github.io/api/channels.json",
    "guides": "https://iptv-org.github.io/api/guides.json",
}

COUNTRIES = {
    "US": {"name": "United States", "timezone": "America/New_York"},
    "UK": {"name": "United Kingdom", "timezone": "Europe/London"},
    "IT": {"name": "Italy", "timezone": "Europe/Rome"},
    "DE": {"name": "Germany", "timezone": "Europe/Berlin"},
    "TR": {"name": "Turkiye", "timezone": "Europe/Istanbul"},
    "PT": {"name": "Portugal", "timezone": "Europe/Lisbon"},
    "MX": {"name": "Mexico", "timezone": "America/Mexico_City"},
    "BR": {"name": "Brazil", "timezone": "America/Sao_Paulo"},
}

CANDIDATE_SITES = {
    "US": ["tvtv.us", "tvguide.com"],
    "UK": ["mytelly.co.uk", "sky.com", "virgintvgo.virginmedia.com"],
    "IT": ["guidatv.sky.it", "superguidatv.it"],
    "DE": ["web.magentatv.de", "sky.de"],
    "TR": ["tvplus.com.tr", "digiturk.com.tr"],
    "PT": ["meo.pt", "nostv.pt", "vodafone.pt"],
    "MX": ["gatotv.com"],
    "BR": ["mi.tv_br"],
}

NORMAL_PATTERNS = {
    "US": [
        "ABC East",
        "CBS East",
        "NBC East",
        "Fox East",
        "PBS East",
        "CNN",
        "ESPN",
        "USA Network East",
        "TNT East",
        "TBS East",
        "HBO East",
        "Discovery Channel",
    ],
    "UK": [
        "BBC One",
        "BBC Two",
        "ITV1",
        "Channel 4",
        "Channel 5",
        "Sky News",
        "Sky Sports Main Event",
        "Sky Sports Football",
        "TNT Sports 1",
        "Eurosport 1",
        "Dave",
        "E4",
    ],
    "IT": [
        "Rai 1",
        "Rai 2",
        "Rai 3",
        "Canale 5",
        "Italia 1",
        "Rete 4",
        "LA7",
        "TV8",
        "Nove",
        "Rai Sport",
        "Sky Sport Uno",
        "Sky Sport Football",
    ],
    "DE": [
        "name:Das Erste",
        "name:ZDF",
        "name:RTL",
        "name:SAT.1",
        "name:ProSieben",
        "name:VOX",
        "name:Kabel Eins",
        "name:RTLZWEI",
        "name:WELT",
        "name:BBC News",
        "name:Eurosport 1",
        "name:Sky Sport Premier League",
    ],
    "TR": [
        "name:TRT1",
        "name:KANAL D",
        "name:SHOW TV",
        "name:STAR TV",
        "name:ATV",
        "name:TV8",
        "name:CNN TÜRK",
        "name:NTV",
        "name:TRT HABER",
        "name:TRT SPOR",
        "name:S SPORT",
        "name:EUROSPORT 1",
    ],
    "PT": [
        "name:RTP1",
        "name:RTP2",
        "name:SIC",
        "name:TVI",
        "name:CNN Portugal",
        "name:RTP Notícias",
        "name:SIC Notícias",
        "name:Sport TV1",
        "name:Sport TV2",
        "name:DAZN 1",
        "name:Eurosport 1",
        "name:BTV",
    ],
    "MX": [
        "site_id:de_las_estrellas_-1h_mexico",
        "site_id:5_mexico",
        "site_id:azteca_uno",
        "site_id:azteca_7",
        "site_id:foro_tv",
        "site_id:tv_azteca_noticias",
        "site_id:distrito_comedia",
        "site_id:tudn_mexico",
        "site_id:claro_sports",
        "site_id:sky_sports_1_mexico",
        "site_id:fox_sports",
        "site_id:golden_mexico",
    ],
    "BR": [
        "site_id:br#globo-hd",
        "site_id:br#sbt",
        "site_id:br#record",
        "site_id:br#band",
        "site_id:br#rede-tv",
        "site_id:br#globo-news",
        "site_id:br#band-news",
        "site_id:br#sportv",
        "site_id:br#sportv2",
        "site_id:br#espn",
        "site_id:br#bandsports",
        "site_id:br#premiere-clubes",
    ],
}

PREMIUM_PATTERNS = {
    "US": [
        "ESPN",
        "ESPN2",
        "ESPNews",
        "ESPNU",
        "Fox Sports 1",
        "FOX Sports 1",
        "Fox Sports 2",
        "FOX Sports 2",
        "CBS Sports Network USA",
        "NFL Network",
        "MLB Network",
        "NBA TV",
        "Golf Channel",
        "Tennis Channel",
        "TNT East",
        "TBS East",
    ],
    "UK": [
        "Sky Sports Main Event",
        "Sky Sports Premier League",
        "Sky Sports Football",
        "Sky Sports Cricket",
        "Sky Sports Golf",
        "Sky Sports F1",
        "Sky Sports NFL",
        "Sky Sports News",
        "TNT Sports 1",
        "TNT Sports 2",
        "TNT Sports 3",
        "TNT Sports 4",
        "Eurosport 1",
        "Eurosport 2",
        "Premier Sports 1",
        "Premier Sports 2",
    ],
    "IT": [
        "Sky Sport Uno",
        "Sky Sport Calcio",
        "Sky Sport Football",
        "Sky Sport F1",
        "Sky Sport MotoGP",
        "Sky Sport Tennis",
        "Sky Sport Arena",
        "Sky Sport Basket",
        "Sky Sport Golf",
        "Eurosport HD",
        "Eurosport 2HD",
        "DAZN",
        "Rai Sport",
        "Sportitalia",
    ],
    "DE": [
        "name:Sky Sport 1 HD",
        "name:Sky Sport 2 HD",
        "name:Sky Sport Bundesliga 1 HD",
        "name:Sky Sport F1 HD",
        "name:Sky Sport Premier League HD",
        "name:Sky Sport Tennis HD",
        "name:Sky Sport Golf HD",
        "name:Sky Sport News HD",
        "name:Sky Sport Top Event HD",
        "name:DAZN 1 HD",
        "name:DAZN 2 HD",
        "name:Eurosport 1",
        "name:Eurosport 2",
        "name:SPORTDIGITAL FUSSBALL",
    ],
    "TR": [
        "name:beIN SPORTS 1",
        "name:beIN SPORTS 2",
        "name:beIN SPORTS 3",
        "name:beIN SPORTS 4",
        "name:beIN SPORTS 5",
        "name:beIN SPORTS MAX 1",
        "name:beIN SPORTS MAX 2",
        "name:beIN SPORTS HABER",
        "name:S SPORT",
        "name:S SPORT 2",
        "name:EUROSPORT 1",
        "name:EUROSPORT 2",
        "name:TRT SPOR",
        "name:TRT SPOR YILDIZ",
        "name:NBA TV",
        "name:SPORTS TV",
    ],
    "PT": [
        "name:Sport TV1",
        "name:Sport TV2",
        "name:Sport TV3",
        "name:Sport TV4",
        "name:Sport TV5",
        "name:Sport TV6",
        "name:Sport TV7",
        "name:Sport TV +",
        "name:DAZN 1",
        "name:DAZN 2",
        "name:DAZN 3",
        "name:DAZN 4",
        "name:DAZN 5",
        "name:Eurosport 1",
        "name:Eurosport 2",
        "name:BTV",
        "name:Sporting TV HD",
        "name:Fight Sports",
    ],
    "MX": [
        "site_id:tudn_mexico",
        "site_id:claro_sports",
        "site_id:sky_sports_1_mexico",
        "site_id:sky_sports_16",
        "site_id:sky_sports_24",
        "site_id:fox_sports",
        "site_id:fox_sports_2",
        "site_id:fox_sports_3",
        "site_id:espn_2_mexico",
        "site_id:espn_3_mexico",
        "site_id:espn_4_mexico",
        "site_id:golden_mexico",
    ],
    "BR": [
        "site_id:br#sportv",
        "site_id:br#sportv2",
        "site_id:br#sportv3",
        "site_id:br#espn",
        "site_id:br#espn-2",
        "site_id:br#bandsports",
        "site_id:br#combate",
        "site_id:br#premiere-clubes",
        "site_id:br#fox-sports",
        "site_id:br#fox-sports-2",
    ],
}


def fetch_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_xmltv_id(value: str | None) -> str:
    if not value:
        return ""
    return value.split("@", 1)[0]


def parse_site_channels(site: str) -> list[dict[str, str]]:
    site_name = site.split("_", 1)[0]
    local_path = EPG_SITES_DIR / site_name / f"{site}.channels.xml"
    if not local_path.exists():
        local_path = EPG_SITES_DIR / site_name / f"{site_name}.channels.xml"
    if local_path.exists():
        xml = local_path.read_text(encoding="utf-8")
    else:
        filename = f"{site}.channels.xml" if "_" in site else f"{site_name}.channels.xml"
        url = f"https://raw.githubusercontent.com/iptv-org/epg/master/sites/{site_name}/{filename}"
        with urllib.request.urlopen(url, timeout=60) as response:
            xml = response.read().decode("utf-8")
    root = ET.fromstring(xml)
    rows = []
    for element in root.findall("channel"):
        rows.append(
            {
                "site": element.attrib.get("site", site),
                "site_id": element.attrib.get("site_id", ""),
                "lang": element.attrib.get("lang", ""),
                "xmltv_id": normalize_xmltv_id(element.attrib.get("xmltv_id")),
                "name": "".join(element.itertext()).strip(),
            }
        )
    return rows


def pattern_matches(row: dict[str, str], pattern: str) -> bool:
    name = row["name"]
    xmltv_id = row["xmltv_id"]
    site_id = row["site_id"]
    if pattern.startswith("name:"):
        return name.casefold() == pattern.removeprefix("name:").casefold()
    if pattern.startswith("id:"):
        return xmltv_id.casefold() == pattern.removeprefix("id:").casefold()
    if pattern.startswith("site_id:"):
        return site_id.casefold() == pattern.removeprefix("site_id:").casefold()
    haystack = f"{name} {xmltv_id} {site_id}".lower()
    return pattern.lower() in haystack


def select_rows(site: str, patterns: list[str], limit: int | None = None) -> list[dict[str, str]]:
    site_rows = parse_site_channels(site)
    selected = []
    seen = set()
    for pattern in patterns:
        for row in site_rows:
            key = (row["site"], row["site_id"])
            if key in seen:
                continue
            if pattern_matches(row, pattern):
                selected.append(row)
                seen.add(key)
                break
    if limit is not None:
        return selected[:limit]
    return selected


def write_custom_channels_xml(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<channels>"]
    for row in rows:
        lines.append(
            f'  <channel site="{html.escape(row["site"])}" site_id="{html.escape(row["site_id"])}" '
            f'lang="{html.escape(row["lang"])}" xmltv_id="{html.escape(row["xmltv_id"])}">'
            f'{html.escape(row["name"] or row["site_id"])}</channel>'
        )
    lines.append("</channels>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_active_channel(channel: dict[str, Any]) -> bool:
    return not channel.get("closed") and not channel.get("replaced_by")


def main() -> int:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    countries = fetch_json(API["countries"])
    channels = fetch_json(API["channels"])
    guides = fetch_json(API["guides"])

    existing_countries = SOURCE_DIR / "countries.json"
    if existing_countries.exists():
        stored_countries = {row["code"]: row for row in json.loads(existing_countries.read_text(encoding="utf-8"))}
    else:
        stored_countries = {}
    for row in countries:
        if row.get("code") in COUNTRIES:
            stored_countries[row["code"]] = row
    write_json(existing_countries, [stored_countries[code] for code in sorted(stored_countries)])

    summary = {}
    existing_summary_path = SOURCE_DIR / "expanded-country-summary.json"
    for code in COUNTRIES:
        active_channels = [channel for channel in channels if channel.get("country") == code and is_active_channel(channel)]
        channel_ids = {channel["id"] for channel in active_channels}
        guide_rows = [guide for guide in guides if guide.get("channel") in channel_ids]
        guide_ids = {guide["channel"] for guide in guide_rows}
        top_sites = Counter(guide.get("site") for guide in guide_rows).most_common(12)
        write_json(SOURCE_DIR / f"channels-{code}.json", active_channels)
        write_json(SOURCE_DIR / f"guide-mappings-{code}.json", guide_rows)

        custom_files = []
        for site in CANDIDATE_SITES[code]:
            rows = select_rows(site, NORMAL_PATTERNS[code], limit=12)
            path = SOURCE_DIR / f"custom-{code}-{site}.channels.xml"
            write_custom_channels_xml(path, rows)
            custom_files.append(str(path.relative_to(ROOT)))

            premium_rows = select_rows(site, PREMIUM_PATTERNS[code], limit=20)
            premium_path = SOURCE_DIR / f"custom-premium-{code}-{site}.channels.xml"
            write_custom_channels_xml(premium_path, premium_rows)
            custom_files.append(str(premium_path.relative_to(ROOT)))

        summary[code] = {
            "name": COUNTRIES[code]["name"],
            "activeChannels": len(active_channels),
            "channelsWithGuideMappings": len(guide_ids),
            "guideRows": len(guide_rows),
            "topSites": top_sites,
            "customFiles": custom_files,
        }

    write_json(existing_summary_path, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
