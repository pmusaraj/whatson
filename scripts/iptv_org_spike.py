#!/usr/bin/env python3
"""First data-source spike for What's On TV.

Downloads public iptv-org API metadata for France, Spain, and Canada, then:
- stores country/channel/guide mapping fixtures
- computes coverage by source site
- creates small custom *.channels.xml files for actual schedule-grabber validation
- writes normalized sample channel JSON and a spike README verdict

This intentionally uses only the Python standard library so the spike has no setup cost.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "iptv-org"
NORMALIZED_DIR = ROOT / "data" / "normalized"
SPIKE_DIR = ROOT / "spikes" / "001-iptv-org-data-source"

API = {
    "countries": "https://iptv-org.github.io/api/countries.json",
    "channels": "https://iptv-org.github.io/api/channels.json",
    "guides": "https://iptv-org.github.io/api/guides.json",
}

COUNTRIES = {
    "FR": {"name": "France", "timezone": "Europe/Paris"},
    "ES": {"name": "Spain", "timezone": "Europe/Madrid"},
    "CA": {"name": "Canada", "timezone": "America/Toronto"},
}

# Candidate source sites chosen from observed guide-mapping coverage and likely usefulness.
CANDIDATE_SITES = {
    "FR": ["tv.sfr.fr", "chaines-tv.orange.fr", "programme-tv.net", "canalplus.com"],
    "ES": ["orangetv.orange.es", "programacion-tv.elpais.com", "gatotv.com"],
    "CA": ["i.mjh.nz", "tvhebdo.com", "tvpassport.com", "ontvtonight.com"],
}

CURATED_NAME_PATTERNS = {
    "FR": ["TF1", "France 2", "France 3", "Canal+", "M6", "Arte", "France 5", "C8", "W9", "TMC"],
    "ES": ["La 1", "La 2", "Antena 3", "Cuatro", "Telecinco", "laSexta", "24 Horas", "Movistar"],
    "CA": ["CBC", "CTV", "Global", "Citytv", "TVO", "TVA", "Télé-Québec", "Radio-Canada", "Sportsnet", "TSN"],
}


def fetch_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def fetch_text(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_xmltv_id(value: str | None) -> str | None:
    if not value:
        return None
    # iptv-org site channel files sometimes include feed suffixes like France2.fr@SD.
    return value.split("@", 1)[0]


def parse_site_channels(site: str) -> list[dict[str, str]]:
    url = f"https://raw.githubusercontent.com/iptv-org/epg/master/sites/{site}/{site}.channels.xml"
    xml = fetch_text(url)
    if not xml:
        return []

    root = ET.fromstring(xml)
    rows: list[dict[str, str]] = []
    for element in root.findall("channel"):
        rows.append(
            {
                "site": element.attrib.get("site", site),
                "site_id": element.attrib.get("site_id", ""),
                "lang": element.attrib.get("lang", ""),
                "xmltv_id": normalize_xmltv_id(element.attrib.get("xmltv_id")) or "",
                "name": "".join(element.itertext()).strip(),
            }
        )
    return rows


def site_channel_matches(country_code: str, site: str, channel_ids: set[str], limit: int = 12) -> list[dict[str, str]]:
    site_channels = parse_site_channels(site)
    direct = [row for row in site_channels if row["xmltv_id"] in channel_ids]

    if len(direct) >= limit:
        return direct[:limit]

    # Some sources, notably Orange Spain, have blank xmltv_id values. Fall back to curated names.
    patterns = [re.compile(re.escape(p), re.I) for p in CURATED_NAME_PATTERNS[country_code]]
    fallback = []
    seen = {row["site_id"] for row in direct}
    for row in site_channels:
        if row["site_id"] in seen:
            continue
        if any(pattern.search(row["name"]) for pattern in patterns):
            fallback.append(row)
            seen.add(row["site_id"])
        if len(direct) + len(fallback) >= limit:
            break
    return (direct + fallback)[:limit]


def write_custom_channels_xml(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<channels>"]
    for row in rows:
        xmltv_id = row["xmltv_id"] or ""
        name = html.escape(row["name"] or row["site_id"])
        site_id = html.escape(row["site_id"])
        site = html.escape(row["site"])
        lang = html.escape(row["lang"] or "")
        lines.append(
            f'  <channel site="{site}" site_id="{site_id}" lang="{lang}" xmltv_id="{html.escape(xmltv_id)}">{name}</channel>'
        )
    lines.append("</channels>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_active_channel(channel: dict[str, Any]) -> bool:
    return not channel.get("closed") and not channel.get("replaced_by")


def display_channel(channel: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": channel["id"],
        "name": channel["name"],
        "country": channel["country"],
        "categories": channel.get("categories") or [],
        "network": channel.get("network"),
        "website": channel.get("website"),
    }


def normalized_sample(country_code: str, channels: list[dict[str, Any]], guide_ids: set[str]) -> dict[str, Any]:
    selected = []
    patterns = [re.compile(re.escape(p), re.I) for p in CURATED_NAME_PATTERNS[country_code]]
    for channel in channels:
        if channel["id"] not in guide_ids:
            continue
        if any(pattern.search(channel["name"]) for pattern in patterns):
            selected.append(channel)
        if len(selected) >= 10:
            break

    if len(selected) < 10:
        for channel in channels:
            if channel["id"] in guide_ids and channel not in selected:
                selected.append(channel)
            if len(selected) >= 10:
                break

    return {
        "country": {
            "code": country_code,
            "name": COUNTRIES[country_code]["name"],
        },
        "channels": [
            {
                "provider": "iptv_org",
                "providerChannelId": channel["id"],
                "name": channel["name"],
                "logoUrl": None,
                "timezone": COUNTRIES[country_code]["timezone"],
                "currentProgram": None,
            }
            for channel in selected
        ],
    }


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Spike 001: iptv-org data source for France, Spain, Canada",
        "",
        "## Question",
        "",
        "Given the MVP countries France, Spain, and Canada, can public iptv-org metadata provide enough channel and guide mapping coverage to justify building the first ingestion adapter?",
        "",
        "## Approach",
        "",
        "- Downloaded `countries.json`, `channels.json`, and `guides.json` from iptv-org public APIs.",
        "- Filtered channels to `FR`, `ES`, and `CA`.",
        "- Counted channels with guide mappings.",
        "- Identified strongest guide-source sites per country.",
        "- Generated custom channel XML files that can be passed to the upstream `iptv-org/epg` grabber for the next schedule-fetch validation.",
        "- Wrote normalized sample JSON skeletons for app/API design.",
        "",
        "## Results",
        "",
        "| Country | Active channels | Channels with guide mappings | Best source candidates |",
        "| --- | ---: | ---: | --- |",
    ]

    for code in COUNTRIES:
        country = summary["countries"][code]
        sources = ", ".join(f"{name} ({count})" for name, count in country["top_sites"][:4])
        lines.append(
            f"| {code} | {country['active_channels']} | {country['channels_with_guides']} | {sources} |"
        )

    lines.extend(
        [
            "",
            "## Generated files",
            "",
            "- `data/sources/iptv-org/spike-summary.json`",
            "- `data/sources/iptv-org/channels-FR.json`",
            "- `data/sources/iptv-org/channels-ES.json`",
            "- `data/sources/iptv-org/channels-CA.json`",
            "- `data/sources/iptv-org/guide-mappings-FR.json`",
            "- `data/sources/iptv-org/guide-mappings-ES.json`",
            "- `data/sources/iptv-org/guide-mappings-CA.json`",
            "- `data/sources/iptv-org/custom-FR-tv.sfr.fr.channels.xml`",
            "- `data/sources/iptv-org/custom-ES-orangetv.orange.es.channels.xml`",
            "- `data/sources/iptv-org/custom-CA-tvhebdo.com.channels.xml`",
            "- `data/normalized/sample-FR.json`",
            "- `data/normalized/sample-ES.json`",
            "- `data/normalized/sample-CA.json`",
            "",
            "## What worked",
            "",
            "- Public APIs are reachable and have substantial metadata coverage for all three MVP countries.",
            "- France and Canada have strong guide mappings; Spain has fewer but still enough for an MVP spike.",
            "- Upstream site channel XML files are available and can be used to build limited custom channel lists for schedule-grabber validation.",
            "",
            "## What did not work yet",
            "",
            "- The public iptv-org API gives guide mappings but not ready-to-use current-program data for these countries.",
            "- Stable country-level XMLTV files were not found at simple `iptv-org.github.io/epg/guides/<country>.xml` URLs.",
            "- The next step must run or integrate a schedule grabber for candidate sources, then normalize actual program entries.",
            "",
            "## Surprises",
            "",
            "- Spain's strongest Orange source has many blank `xmltv_id` values in the source channel XML, so matching may require name/site-id based mapping.",
            "- Canada has the broadest channel count and multiple strong sources, but timezone and regional feed handling will likely be the trickiest.",
            "",
            "## Verdict: PARTIAL",
            "",
            "iptv-org is validated for channel metadata and guide-source discovery, but actual current-program data is not validated yet. Continue with a second spike that runs the upstream `iptv-org/epg` grabber on the generated custom channel XML files and checks whether each country can produce at least 10 current-program rows.",
            "",
            "## Recommendation for the real build",
            "",
            "- Keep `iptv_org` as the first provider adapter.",
            "- Use SQLite for normalized app storage.",
            "- Do not build the full UI until schedule fetching is validated for at least 10 channels per country.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    SPIKE_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading iptv-org API metadata...")
    countries = fetch_json(API["countries"])
    channels = fetch_json(API["channels"])
    guides = fetch_json(API["guides"])

    write_json(SOURCE_DIR / "countries.json", [c for c in countries if c.get("code") in COUNTRIES])

    guides_by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for guide in guides:
        if guide.get("channel"):
            guides_by_channel[guide["channel"]].append(guide)

    summary: dict[str, Any] = {"provider": "iptv_org", "countries": {}}

    for code in COUNTRIES:
        country_channels = [c for c in channels if c.get("country") == code and is_active_channel(c)]
        guide_ids = {c["id"] for c in country_channels if c.get("id") in guides_by_channel}
        country_guides = [g for g in guides if g.get("channel") in guide_ids]
        site_counts = Counter(g.get("site") for g in country_guides if g.get("site"))

        write_json(SOURCE_DIR / f"channels-{code}.json", [display_channel(c) for c in country_channels])
        write_json(SOURCE_DIR / f"guide-mappings-{code}.json", country_guides)
        write_json(NORMALIZED_DIR / f"sample-{code}.json", normalized_sample(code, country_channels, guide_ids))

        generated_custom_files = []
        for site in CANDIDATE_SITES[code][:3]:
            matches = site_channel_matches(code, site, guide_ids)
            if not matches:
                continue
            path = SOURCE_DIR / f"custom-{code}-{site}.channels.xml"
            write_custom_channels_xml(path, matches)
            generated_custom_files.append(str(path.relative_to(ROOT)))

        summary["countries"][code] = {
            "name": COUNTRIES[code]["name"],
            "active_channels": len(country_channels),
            "channels_with_guides": len(guide_ids),
            "guide_mappings": len(country_guides),
            "top_sites": site_counts.most_common(10),
            "candidate_sites": CANDIDATE_SITES[code],
            "custom_channel_files": generated_custom_files,
        }

    write_json(SOURCE_DIR / "spike-summary.json", summary)
    spike_readme = SPIKE_DIR / "README.md"
    if not spike_readme.exists() or "Schedule-grabber validation" not in spike_readme.read_text(encoding="utf-8"):
        spike_readme.write_text(markdown_summary(summary), encoding="utf-8")
        report_action = "Wrote"
    else:
        report_action = "Preserved existing validated"

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n{report_action} spike report: {spike_readme}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
