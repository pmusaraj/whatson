#!/usr/bin/env python3
"""Build a best-effort UHF/XTream channel-to-custom-XMLTV mapping.

Inputs come from UHF's local Core Data export. Outputs avoid stream URLs and
only contain channel metadata/mapping IDs.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "uhf-live-channels-target-categories.csv"
IPTV_ORG_DIR = ROOT / "data" / "sources" / "iptv-org"
OUT_CSV = ROOT / "data" / "uhf-channel-mapping.csv"
OUT_JSON = ROOT / "data" / "uhf-channel-mapping.json"
SUMMARY_JSON = ROOT / "data" / "uhf-channel-mapping-summary.json"

IGNORED_CATEGORIES = {
    "Canal + Africa",
    "French-SD",
    "French-FHD",
    "beIN SD",
    "beIN FHD",
    "beIN HD",
}

CATEGORY_COUNTRY = {
    "French-HD": "FR",
    "French Sports": "FR",
    "Spain": "ES",
    "Canada": "CA",
    "USA": "US",
    "UK": "UK",
}

# Hand aliases for common IPTV naming variants that fuzzy matching either misses
# or maps to a weaker duplicate.
MANUAL_ALIASES = {
    # France
    ("FR", "CANAL+FOOT"): "FR:CanalPlusFoot.fr",
    ("FR", "FR-SP:Canal+ Foot"): "FR:CanalPlusFoot.fr",
    ("FR", "FR-SP:Canal+Sport"): "FR:CanalPlusSport360.fr",
    ("FR", "FR-SP:Canal+ Sport 360"): "FR:CanalPlusSport360.fr",
    ("FR", "FR-SP:AutoMoto"): "FR:Automotolachaine.fr",
    ("FR", "FR-SP:EUROSPORT 1"): "FR:Eurosport1.fr",
    ("FR", "FR-SP:EUROSPORT 2"): "FR:Eurosport2.fr",
    ("FR", "FR-SP:EQUIDIA"): "FR:EquidiaLive.fr",
    # Canada
    ("CA", "Sportsnet (Ontario)"): "CA:Sportsnet.ca",
    ("CA", "Canada- Sports Net 360 FHD"): "CA:Sportsnet360.ca",
    ("CA", "Canada- Sports Net One HD"): "CA:SportsnetOne.ca",
    ("CA", "Canada- Sports Net World HD"): "CA:SportsnetWorld.ca",
    ("CA", "Canada- TSN 1 HD CA"): "CA:TSN1.ca",
    ("CA", "Canada- TSN 2 HD CA"): "CA:TSN2.ca",
    ("CA", "Canada- TSN 3 HD CA"): "CA:TSN3.ca",
    ("CA", "Canada- TSN 4 HD CA"): "CA:TSN4.ca",
    ("CA", "Canada- TSN 5 HD CA"): "CA:TSN5.ca",
    ("CA", "Canada- RDS QC"): "CA:RDS.ca",
    ("CA", "Canada- RDS 2 QC"): "CA:RDS2.ca",
    ("CA", "Canada- RDS INFO QC"): "CA:RDSInfo.ca",
    ("CA", "Canada- RDS Info CA-FR"): "CA:RDSInfo.ca",
    ("CA", "Canada- TVA SPORTS QC"): "CA:TVASports.ca",
    ("CA", "Canada- BEIN SPORTS CANADA"): "CA:beINSportsCanada.ca",
    ("CA", "Canada- beIN Sports HD CA"): "CA:beINSportsCanada.ca",
    # UK
    ("UK", "UK| Sky Sports Main Event"): "UK:SkySportsMainEvent.uk",
    ("UK", "UK| Sky Sports Premier League"): "UK:SkySportsPremierLeague.uk",
    ("UK", "UK| Sky Sports Football"): "UK:SkySportsFootball.uk",
    ("UK", "UK| Sky Sports Cricket"): "UK:SkySportsCricket.uk",
    ("UK", "UK| Sky Sports F1"): "UK:SkySportsF1.uk",
    ("UK", "UK| Sky Sports Golf"): "UK:SkySportsGolf.uk",
    ("UK", "UK| Sky Sports News"): "UK:SkySportsNews.uk",
    ("UK", "UK| Sky Sports NFL"): "UK:SkySportsNFL.uk",
    ("UK", "UK| TNT Sports 1"): "UK:TNTSports1.uk",
    ("UK", "UK| TNT Sports 2"): "UK:TNTSports2.uk",
    ("UK", "UK| TNT Sports 3"): "UK:TNTSports3.uk",
    ("UK", "UK| TNT Sports 4"): "UK:TNTSports4.uk",
    ("UK", "UK| Premier Sports 1"): "UK:PremierSports1.ie",
    ("UK", "UK| Premier Sports 2"): "UK:PremierSports2.ie",
    # US
    ("US", "USA- ESPN"): "US:ESPN.us",
    ("US", "USA- ESPN 2"): "US:ESPN2.us",
    ("US", "USA- ESPNEWS"): "US:ESPNews.us",
    ("US", "USA- ESPNU"): "US:ESPNU.us",
    ("US", "USA- FOX SPORTS 1"): "US:FoxSports1.us",
    ("US", "USA- FOX SPORTS 2"): "US:FoxSports2.us",
    ("US", "USA- MLB NETWORK"): "US:MLBNetwork.us",
    ("US", "USA- NBA TV"): "US:NBATV.us",
    ("US", "USA- NFL NETWORK"): "US:NFLNetwork.us",
}

FIELDNAMES = [
    "uhf_pk",
    "category",
    "name",
    "original_name",
    "source_epg_channel_id",
    "source_country",
    "target_xmltv_id",
    "target_name",
    "target_country",
    "target_guide_sites",
    "match_method",
    "confidence",
    "review",
    "notes",
    "logo_url",
]


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def normalize(value: str | None) -> str:
    if not value:
        return ""
    value = strip_accents(value).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"!\$![^!]+!\$!", " ", value)
    value = re.sub(r"\b(fr|sp|uk|usa|us|canada|ca|qc|hd|fhd|sd|uhd|4k|live|channel|tv)\b", " ", value)
    value = re.sub(r"\b(sp|fr)[-:|]+", " ", value)
    value = re.sub(r"\b(sports net)\b", "sportsnet", value)
    value = value.replace("canal plus", "canal+")
    value = value.replace("canalplus", "canal+")
    value = value.replace("t n t", "tnt")
    value = re.sub(r"[^a-z0-9+]+", " ", value)
    value = re.sub(r"\b(the|la|le|de|por)\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def clean_source_epg_id(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    # UHF sometimes prefixes provider/playlist info as !$!PLAYLIST!$!CA:Sportsnet.ca
    if "!$!" in value:
        value = value.split("!$!")[-1]
    return value.strip()


def guide_sites_by_channel(country: str) -> dict[str, list[str]]:
    path = IPTV_ORG_DIR / f"guide-mappings-{country}.json"
    if not path.exists():
        return {}
    guides = json.loads(path.read_text(encoding="utf-8"))
    sites: dict[str, set[str]] = {}
    for guide in guides:
        channel_id = guide.get("channel")
        site = guide.get("site")
        if channel_id and site:
            sites.setdefault(channel_id, set()).add(site)
    return {channel_id: sorted(values) for channel_id, values in sites.items()}


def load_targets() -> tuple[dict[str, dict], dict[str, str], dict[str, list[str]]]:
    """Load all iptv-org mapped channels for target countries.

    This mapping should cover the UHF playlist broadly, so match against
    iptv-org channel metadata with guide mappings rather than the smaller
    browser guide payload.
    """
    targets: dict[str, dict] = {}
    raw_to_target: dict[str, str] = {}
    norm_to_targets: dict[str, list[str]] = {}
    for country in ["FR", "ES", "UK", "CA", "US"]:
        guide_sites = guide_sites_by_channel(country)
        channels_path = IPTV_ORG_DIR / f"channels-{country}.json"
        channels = json.loads(channels_path.read_text(encoding="utf-8"))
        for channel in channels:
            raw_id = channel["id"]
            # Prefer channels that actually have guide mappings.
            target_id = f"{country}:{raw_id}"
            if raw_id not in guide_sites:
                continue
            name = channel.get("name") or raw_id
            targets[target_id] = {
                "id": target_id,
                "name": name,
                "country": country,
                "raw_id": raw_id,
                "guide_sites": guide_sites.get(raw_id, []),
            }
            raw_to_target[raw_id.lower()] = target_id
            raw_to_target[target_id.lower()] = target_id
            norm_to_targets.setdefault(normalize(name), []).append(target_id)
            norm_to_targets.setdefault(normalize(raw_id), []).append(target_id)
    return targets, raw_to_target, norm_to_targets


def country_targets(targets: dict[str, dict], country: str | None) -> list[dict]:
    if not country:
        return []
    return [target for target in targets.values() if target["country"] == country]


def skip_fuzzy_name(name: str) -> bool:
    """Avoid mapping pop-up/event feeds onto a parent linear channel."""
    lowered = strip_accents(name).lower()
    event_patterns = [
        r"canal\+\s*live\s*\d+",
        r"dazn\s+betclic\s+elite\s+\d+",
        r"tennis\s+plus\s+\d+",
        r"eurosport\s+(?:360|[3-9])\b",
        r"canal\+\s+sports?\s+(?:fhd\s*)?\d+",
        r"canal\+\s+sport\s+[2-9]\b",
        r"be?in[-_ ]sports[-_ ]max[-_ ]\d+",
    ]
    return any(re.search(pattern, lowered) for pattern in event_patterns)


def best_fuzzy(name: str, targets_for_country: list[dict]) -> tuple[str, float]:
    norm_name = normalize(name)
    best_id = ""
    best_score = 0.0
    for target in targets_for_country:
        candidates = {normalize(target["name"]), normalize(target["raw_id"])}
        for candidate in candidates:
            if not candidate:
                continue
            score = SequenceMatcher(None, norm_name, candidate).ratio()
            # Reward containment after normalization, useful for "Canada- TSN 1 HD CA" -> "TSN1".
            compact_a = norm_name.replace(" ", "")
            compact_b = candidate.replace(" ", "")
            if compact_a and compact_b and (compact_a in compact_b or compact_b in compact_a):
                score = max(score, 0.92 if min(len(compact_a), len(compact_b)) >= 4 else score)
            if score > best_score:
                best_score = score
                best_id = target["id"]
    return best_id, best_score


def map_row(row: dict, targets: dict[str, dict], raw_to_target: dict[str, str]) -> dict:
    category = row["category"]
    source_country = CATEGORY_COUNTRY.get(category)
    name = row["name"] or row["original_name"] or ""
    clean_epg = clean_source_epg_id(row.get("epg_channel_id"))

    target_id = ""
    method = "unmapped"
    confidence = 0.0
    notes = ""

    manual_key = (source_country or "", name)
    if manual_key in MANUAL_ALIASES:
        candidate = MANUAL_ALIASES[manual_key]
        if candidate in targets:
            target_id = candidate
            method = "manual_alias"
            confidence = 1.0
        else:
            notes = f"manual alias target not in target guide metadata: {candidate}"

    if not target_id and clean_epg:
        candidate = raw_to_target.get(clean_epg.lower())
        if candidate and (not source_country or candidate.startswith(source_country + ":")):
            target_id = candidate
            method = "source_epg_id_exact"
            confidence = 1.0
        elif ":" in clean_epg:
            candidate_country = clean_epg.split(":", 1)[0]
            notes = f"source EPG id present but no target-country guide channel: {clean_epg}"
            if source_country and candidate_country != source_country:
                notes += f"; category implies {source_country}"
        else:
            notes = f"source EPG id present but no target-country guide channel: {clean_epg}"

    if not target_id:
        if skip_fuzzy_name(name):
            notes = notes or "event/pop-up channel; not mapped to parent linear EPG channel"
        else:
            scoped = country_targets(targets, source_country)
            candidate, score = best_fuzzy(name, scoped)
            if candidate and score >= 0.90:
                target_id = candidate
                method = "fuzzy_name_high"
                confidence = round(score, 3)
            elif candidate and score >= 0.82:
                target_id = candidate
                method = "fuzzy_name_review"
                confidence = round(score, 3)
            else:
                confidence = round(score, 3)
                if not notes:
                    notes = "no reliable match in target-country guide channel set"

    target = targets.get(target_id, {})
    review = "ok" if confidence >= 0.90 else ("review" if target_id else "unmapped")
    if category == "Bein Channels" and not target_id:
        notes = notes or "Arabic/MENA beIN package; outside current FR/ES/UK/CA/US guide set"

    return {
        "uhf_pk": row["uhf_pk"],
        "category": category,
        "name": name,
        "original_name": row.get("original_name") or "",
        "source_epg_channel_id": clean_epg,
        "source_country": source_country or "",
        "target_xmltv_id": target_id,
        "target_name": target.get("name", ""),
        "target_country": target.get("country", ""),
        "target_guide_sites": ";".join(target.get("guide_sites", [])),
        "match_method": method,
        "confidence": f"{confidence:.3f}",
        "review": review,
        "notes": notes,
        "logo_url": row.get("logo_url") or "",
    }


def main() -> int:
    targets, raw_to_target, _ = load_targets()
    with INPUT.open(newline="", encoding="utf-8") as infile:
        source_rows = list(csv.DictReader(infile))

    kept_rows = [row for row in source_rows if row["category"] not in IGNORED_CATEGORIES]
    mapped_rows = [map_row(row, targets, raw_to_target) for row in kept_rows]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(mapped_rows)

    OUT_JSON.write_text(json.dumps(mapped_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "input": str(INPUT.relative_to(ROOT)),
        "targetMetadata": str(IPTV_ORG_DIR.relative_to(ROOT)),
        "ignoredCategories": sorted(IGNORED_CATEGORIES),
        "sourceRows": len(source_rows),
        "mappedRows": len(mapped_rows),
        "byCategory": Counter(row["category"] for row in mapped_rows),
        "byReview": Counter(row["review"] for row in mapped_rows),
        "byMethod": Counter(row["match_method"] for row in mapped_rows),
        "matchedTargetCount": len({row["target_xmltv_id"] for row in mapped_rows if row["target_xmltv_id"]}),
        "unmappedSamples": [
            {"category": row["category"], "name": row["name"], "sourceEpgId": row["source_epg_channel_id"], "notes": row["notes"]}
            for row in mapped_rows
            if row["review"] == "unmapped"
        ][:50],
        "reviewSamples": [
            {"category": row["category"], "name": row["name"], "target": row["target_xmltv_id"], "confidence": row["confidence"]}
            for row in mapped_rows
            if row["review"] == "review"
        ][:50],
    }
    # Convert Counters to plain dicts for stable JSON.
    summary = {key: (dict(value) if isinstance(value, Counter) else value) for key, value in summary.items()}
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_CSV.relative_to(ROOT)}")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {SUMMARY_JSON.relative_to(ROOT)}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
