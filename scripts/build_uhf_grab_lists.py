#!/usr/bin/env python3
"""Build iptv-org grabber channel lists for OK UHF mappings.

The output files are named custom-uhf-<country>-<site>.channels.xml so the
existing scripts/refresh_epg.py job automatically picks them up and refreshes
fresh XMLTV snapshots into data/normalized/guide-uhf-*.xml.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MAPPING_CSV = ROOT / "data" / "uhf-channel-mapping.csv"
IPTV_ORG_DIR = ROOT / "data" / "sources" / "iptv-org"
OUT_PLAN = ROOT / "data" / "uhf" / "grab-plan.json"

PREFERRED_SITES = {
    "FR": ["canalplus.com", "tv.sfr.fr", "programme-tv.net", "chaines-tv.orange.fr"],
    "ES": ["orangetv.orange.es", "programacion-tv.elpais.com", "gatotv.com"],
    "UK": ["virgintvgo.virginmedia.com", "sky.com", "mytelly.co.uk", "freeview.co.uk"],
    "CA": ["tvpassport.com", "tvhebdo.com", "tvtv.us", "ontvtonight.com"],
    "US": ["tvtv.us", "tvguide.com", "tvpassport.com"],
}


def safe_site_name(site: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", site)


def load_ok_target_ids() -> dict[str, set[str]]:
    targets: dict[str, set[str]] = defaultdict(set)
    with MAPPING_CSV.open(newline="", encoding="utf-8") as infile:
        for row in csv.DictReader(infile):
            if row.get("review") != "ok" or not row.get("target_xmltv_id"):
                continue
            country, raw_id = row["target_xmltv_id"].split(":", 1)
            targets[country].add(raw_id)
    return targets


def load_guide_mappings(country: str) -> dict[str, list[dict]]:
    path = IPTV_ORG_DIR / f"guide-mappings-{country}.json"
    mappings = json.loads(path.read_text(encoding="utf-8"))
    by_channel: dict[str, list[dict]] = defaultdict(list)
    for mapping in mappings:
        if mapping.get("channel"):
            by_channel[mapping["channel"]].append(mapping)
    return by_channel


def choose_mapping(country: str, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    preferred = PREFERRED_SITES.get(country, [])
    by_site = {candidate.get("site"): candidate for candidate in candidates}
    for site in preferred:
        if site in by_site:
            return by_site[site]
    return sorted(candidates, key=lambda item: (item.get("site") or "", item.get("site_name") or ""))[0]


def write_channels_file(country: str, site: str, mappings: list[dict]) -> Path:
    output = IPTV_ORG_DIR / f"custom-uhf-{country}-{safe_site_name(site)}.channels.xml"
    root = ET.Element("channels")
    for mapping in sorted(mappings, key=lambda item: (item.get("site_name") or "", item["channel"])):
        attrs = {
            "site": mapping["site"],
            "site_id": str(mapping["site_id"]),
            "lang": mapping.get("lang") or "en",
            "xmltv_id": mapping["channel"],
        }
        if mapping.get("feed"):
            attrs["feed"] = str(mapping["feed"])
        element = ET.SubElement(root, "channel", attrs)
        element.text = mapping.get("site_name") or mapping["channel"]
    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output


def main() -> int:
    target_ids_by_country = load_ok_target_ids()
    selected_by_site: dict[tuple[str, str], list[dict]] = defaultdict(list)
    missing = []
    for country, raw_ids in sorted(target_ids_by_country.items()):
        guide_mappings = load_guide_mappings(country)
        for raw_id in sorted(raw_ids):
            selected = choose_mapping(country, guide_mappings.get(raw_id, []))
            if not selected:
                missing.append(f"{country}:{raw_id}")
                continue
            selected_by_site[(country, selected["site"])].append(selected)

    written = []
    for (country, site), mappings in sorted(selected_by_site.items()):
        path = write_channels_file(country, site, mappings)
        written.append({"country": country, "site": site, "path": str(path.relative_to(ROOT)), "channels": len(mappings)})

    plan = {
        "mappingCsv": str(MAPPING_CSV.relative_to(ROOT)),
        "outputPattern": "data/sources/iptv-org/custom-uhf-<country>-<site>.channels.xml",
        "refreshScript": "python3 scripts/refresh_epg.py",
        "okUniqueTargets": sum(len(values) for values in target_ids_by_country.values()),
        "writtenFiles": written,
        "channelsByCountry": dict(Counter(item["country"] for item in written for _ in range(item["channels"]))),
        "missingGuideMappings": missing,
    }
    OUT_PLAN.parent.mkdir(parents=True, exist_ok=True)
    OUT_PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
