#!/usr/bin/env python3
"""Build a synthetic XMLTV feed for MLS matches available on Apple TV.

The source is the public schedule data used by mlssoccer.com:

- stats-api.mlssoccer.com for competitions, seasons, and match schedules
- sportapi.mlssoccer.com for match details, Apple TV URLs, and broadcaster metadata

The output models MLS Season Pass as one virtual channel. MLS often has
simultaneous kickoffs, so the app/data builder treats this synthetic source as an
event feed and preserves concurrent programmes.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "normalized" / "guide-premium-US-mls-apple.xml"
STATS_API = "https://stats-api.mlssoccer.com"
SPORT_API = "https://sportapi.mlssoccer.com/api"
USER_AGENT = "Mozilla/5.0"
DEFAULT_DAYS_BACK = 1
DEFAULT_DAYS_AHEAD = 14
DEFAULT_MATCH_DURATION_MINUTES = 150
APPLE_TV_ICON = "https://images.mlssoccer.com/image/private/w_250,h_250,c_thumb,g_auto,q_auto,f_png/mls/snffj82ru8ziiotyvipr"
APPLE_TV_CHANNEL_URL = "https://tv.apple.com/channel/tvs.sbd.7000"

# MLS first-team competitions we want surfaced in the premium sports guide.
INCLUDED_COMPETITION_IDS = {
    "MLS-COM-000001",  # Major League Soccer - Regular Season
    "MLS-COM-000002",  # Major League Soccer - Cup Playoffs
    "MLS-COM-000005",  # MLS All-Star Game
    "MLS-COM-000006",  # Leagues Cup
    "MLS-COM-000007",  # Campeones Cup
}
PRIMARY_COMPETITION_ID = "MLS-COM-000001"


@dataclass(frozen=True)
class Match:
    match_id: str
    title: str
    competition: str
    start: datetime
    stop: datetime
    description: str
    apple_url: str | None = None
    image_url: str | None = None


def fetch_json(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Referer": "https://www.mlssoccer.com/schedule/scores",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def parse_iso_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def xmltv_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000")


def current_mls_season_id(year: int) -> str:
    url = f"{STATS_API}/competitions/{PRIMARY_COMPETITION_ID}/seasons"
    seasons = fetch_json(url).get("seasons", [])
    for season in seasons:
        if int(season.get("season", 0)) == year:
            return season["season_id"]
    if seasons:
        return seasons[0]["season_id"]
    raise RuntimeError("MLS seasons endpoint returned no seasons")


def schedule_url(season_id: str, start_date: datetime, end_date: datetime) -> str:
    params = {
        "match_date[gte]": start_date.date().isoformat(),
        "match_date[lte]": end_date.date().isoformat(),
        "per_page": "200",
        "sort": "planned_kickoff_time:asc,home_team_name:asc",
    }
    return f"{STATS_API}/matches/seasons/{season_id}?{urllib.parse.urlencode(params)}"


def fetch_schedule(season_id: str, start_date: datetime, end_date: datetime) -> list[dict]:
    data = fetch_json(schedule_url(season_id, start_date, end_date))
    rows = data.get("schedule", [])
    return [row for row in rows if row.get("competition_id") in INCLUDED_COMPETITION_IDS and row.get("match_scheduled")]


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def fetch_match_details(match_ids: list[str]) -> dict[str, dict]:
    details: dict[str, dict] = {}
    for batch in chunks(match_ids, 25):
        url = f"{SPORT_API}/matches/bySportecIds/{','.join(batch)}"
        try:
            rows = fetch_json(url)
        except Exception as error:
            print(f"warning: failed to fetch MLS match details for {batch[0]}…: {error}", file=sys.stderr)
            continue
        for row in rows:
            match_id = row.get("sportecId")
            if match_id:
                details[match_id] = row
    return details


def is_apple_match(detail: dict | None) -> bool:
    if not detail:
        return False
    if detail.get("appleStreamURL"):
        return True
    for broadcaster in detail.get("broadcasters") or []:
        if "apple" in (broadcaster.get("broadcasterName") or "").lower():
            return True
    return False


def first_logo_url(detail: dict | None) -> str | None:
    if not detail:
        return None
    for side in ("home", "away"):
        url = (detail.get(side) or {}).get("logoColorUrl")
        if url:
            return url.replace("{formatInstructions}", "w_400,h_400,c_fit,q_auto,f_png")
    return None


def normalize_matches(schedule_rows: list[dict], details: dict[str, dict]) -> list[Match]:
    matches: list[Match] = []
    for row in schedule_rows:
        match_id = row.get("match_id")
        if not isinstance(match_id, str) or not match_id:
            continue
        detail = details.get(match_id, {})
        if not is_apple_match(detail):
            continue

        start_value = row.get("planned_kickoff_time") or detail.get("matchDate")
        if not start_value:
            continue
        start = parse_iso_time(start_value)
        stop = start + timedelta(minutes=DEFAULT_MATCH_DURATION_MINUTES)
        home = row.get("home_team_name") or (detail.get("home") or {}).get("fullName") or "Home"
        away = row.get("away_team_name") or (detail.get("away") or {}).get("fullName") or "Away"
        competition = row.get("competition_label") or row.get("competition_name") or (detail.get("competition") or {}).get("name") or "MLS"
        venue_parts = [row.get("stadium_name"), row.get("stadium_city") or row.get("stadium_country")]
        venue = ", ".join(part for part in venue_parts if part)
        broadcasters = ", ".join(
            broadcaster.get("broadcasterName")
            for broadcaster in detail.get("broadcasters") or []
            if broadcaster.get("broadcasterName")
        )
        apple_url = detail.get("appleStreamURL") or APPLE_TV_CHANNEL_URL
        desc_parts = [competition, venue, f"Watch on Apple TV: {apple_url}"]
        if broadcasters:
            desc_parts.append(f"Broadcasters: {broadcasters}")
        matches.append(
            Match(
                match_id=match_id,
                title=f"{home} vs {away}",
                competition=competition,
                start=start,
                stop=stop,
                description=" · ".join(part for part in desc_parts if part),
                apple_url=apple_url,
                image_url=first_logo_url(detail),
            )
        )
    return sorted(matches, key=lambda match: (match.start, match.title))


def pack_lanes(matches: list[Match]) -> list[list[Match]]:
    lanes: list[list[Match]] = []
    lane_end_times: list[datetime] = []
    for match in matches:
        for index, end_time in enumerate(lane_end_times):
            if end_time <= match.start:
                lanes[index].append(match)
                lane_end_times[index] = match.stop
                break
        else:
            lanes.append([match])
            lane_end_times.append(match.stop)
    return lanes


def build_xml(matches: list[Match], generated_at: datetime) -> ET.ElementTree:
    tv = ET.Element(
        "tv",
        {
            "generator-info-name": "whatsontv MLS Apple TV builder",
            "source-info-name": "MLS public schedule APIs",
            "source-data-url": "https://www.mlssoccer.com/schedule/scores",
            "date": generated_at.date().isoformat(),
        },
    )
    channel = ET.SubElement(tv, "channel", {"id": "MLSSeasonPass.us"})
    ET.SubElement(channel, "display-name").text = "MLS Season Pass"
    ET.SubElement(channel, "display-name").text = "Apple TV MLS"
    ET.SubElement(channel, "icon", {"src": APPLE_TV_ICON})

    for match in matches:
        programme = ET.SubElement(
            tv,
            "programme",
            {
                "start": xmltv_time(match.start),
                "stop": xmltv_time(match.stop),
                "channel": "MLSSeasonPass.us",
            },
        )
        ET.SubElement(programme, "title", {"lang": "en"}).text = match.title
        ET.SubElement(programme, "sub-title", {"lang": "en"}).text = match.competition
        ET.SubElement(programme, "desc", {"lang": "en"}).text = match.description
        for category in ("Sports", "Soccer", "MLS", "Apple TV"):
            ET.SubElement(programme, "category", {"lang": "en"}).text = category
        if match.image_url:
            ET.SubElement(programme, "icon", {"src": match.image_url})
        if match.apple_url:
            ET.SubElement(programme, "url").text = match.apple_url
    ET.indent(tv, space="  ")
    return ET.ElementTree(tv)


def write_xml(path: Path, tree: ET.ElementTree) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build synthetic MLS Season Pass XMLTV from MLS public schedule APIs.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help=f"Output XMLTV path (default: {OUTPUT_PATH})")
    parser.add_argument("--days-back", type=int, default=DEFAULT_DAYS_BACK)
    parser.add_argument("--days-ahead", type=int, default=DEFAULT_DAYS_AHEAD)
    parser.add_argument("--now", help="Override current UTC time, ISO-8601. Useful for tests.")
    args = parser.parse_args()

    now = parse_iso_time(args.now) if args.now else datetime.now(timezone.utc)
    start_date = now - timedelta(days=args.days_back)
    end_date = now + timedelta(days=args.days_ahead)
    season_id = current_mls_season_id(now.year)
    schedule_rows = fetch_schedule(season_id, start_date, end_date)
    match_ids = [row["match_id"] for row in schedule_rows if row.get("match_id")]
    details = fetch_match_details(match_ids)
    matches = normalize_matches(schedule_rows, details)
    write_xml(args.output, build_xml(matches, now))
    print(f"Wrote {len(matches)} MLS Apple TV match programmes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
