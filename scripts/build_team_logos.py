#!/usr/bin/env python3
"""Build a team-name -> logo-URL lookup from the frertommy/team-logos manifest.

Output (web/data/team-logos.json) maps normalized team names and common
aliases to small white-disc badge URLs. Renderers fall back to monogram
crests for anything unmapped (NHL, MLS, rugby/cricket nations, ...).
"""

import json
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_URL = "https://raw.githubusercontent.com/frertommy/team-logos/main/manifest.json"
OUTPUT_PATH = ROOT / "web" / "data" / "team-logos.json"
BASE_URL = "https://raw.githubusercontent.com/frertommy/team-logos/main/"

# Hand aliases: normalized short name -> normalized manifest team name.
ALIASES = {
    "man united": "manchester united",
    "man city": "manchester city",
    "spurs": "tottenham",
    "tottenham": "tottenham",
    "west ham": "west ham",
    "wolves": "wolves",
    
    "leeds": "leeds",
    "newcastle": "newcastle",
    "aston villa": "aston villa",
    "nottingham": "nottingham forest",
    "forest": "nottingham forest",
    "brighton": "brighton",
    "bournemouth": "bournemouth",
    "palace": "crystal palace",
    "sunderland": "sunderland",
    "coventry": "coventry",
    "hull": "hull city",
    "ipswich": "ipswich",
    "burnley": "burnley",
    "fulham": "fulham",
    "everton": "everton",
    "barca": "barcelona",
    "fc barcelona": "barcelona",
    "atletico": "atletico madrid",
    "athletic": "athletic club",
    "bilbao": "athletic club",
    "betis": "real betis",
    "sociedad": "real sociedad",
    "celta": "celta vigo",
    "alaves": "alaves",
    "levante": "levante",
    "rayo": "rayo vallecano",
    "vallecano": "rayo vallecano",
    "mallorca": "mallorca",
    "espanyol": "espanyol",
    "osasuna": "osasuna",
    "getafe": "getafe",
    "girona": "girona",
    "sevilla": "sevilla",
    "juve": "juventus",
    "napoli": "napoli",
    "roma": "as roma",
    "lazio": "lazio",
    "milan": "ac milan",
    "inter": "inter",
    "atalanta": "atalanta",
    "torino": "torino",
    "fiorentina": "fiorentina",
    "bologna": "bologna",
    "udinese": "udinese",
    "como": "como",
    "cagliari": "cagliari",
    "verona": "hellas verona",
    "hellas": "hellas verona",
    "sassuolo": "sassuolo",
    "genoa": "genoa",
    "lecce": "lecce",
    "parma": "parma",
    "bayern": "bayern munchen",
    "dortmund": "borussia dortmund",
    "leverkusen": "bayer leverkusen",
    "leipzig": "rb leipzig",
    "stuttgart": "vfb stuttgart",
    "frankfurt": "eintracht frankfurt",
    "wolfsburg": "vfl wolfsburg",
    "gladbach": "borussia monchengladbach",
    "werder": "werder bremen",
    "bremen": "werder bremen",
    "schalke": "fc schalke 04",
    "hamburg": "hamburger sv",
    "koln": "1 fc koln",
    "cologne": "1 fc koln",
    "mainz": "fsv mainz 05",
    "augsburg": "fc augsburg",
    "hoffenheim": "1899 hoffenheim",
    "freiburg": "sc freiburg",
    "st pauli": "fc st pauli",
    "union": "union berlin",
    "heidenheim": "1 fc heidenheim",
    "psg": "paris saint germain",
    "marseille": "marseille",
    "olympique marseille": "marseille",
    "lyon": "lyon",
    "olympique lyon": "lyon",
    "monaco": "monaco",
    "lille": "lille",
    "lens": "lens",
    "nice": "nice",
    "sporting": "sporting cp",
    "celtics": "boston celtics",
    "lakers": "los angeles lakers",
    "knicks": "new york knicks",
    "warriors": "golden state warriors",
    "bulls": "chicago bulls",
    "cowboys": "dallas cowboys",
    "patriots": "new england patriots",
    "chiefs": "kansas city chiefs",
    "eagles": "philadelphia eagles",
    "yankees": "new york yankees",
    "dodgers": "los angeles dodgers",
    "red sox": "boston red sox",
    "cubs": "chicago cubs",
}


def normalize(name):
    text = unicodedata.normalize("NFD", str(name or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def main():
    with urllib.request.urlopen(MANIFEST_URL, timeout=60) as response:
        manifest = json.loads(response.read())
    by_name = {}
    for team in manifest["teams"]:
        badge = next(path for path in team["files"] if "small_circle_badge" in path)
        by_name[normalize(team["team"])] = BASE_URL + urllib.parse.quote(badge)
    missing = sorted(set(ALIASES.values()) - set(by_name))
    if missing:
        raise SystemExit(f"alias targets missing from manifest: {missing}")
    collisions = {}
    for alias, target in ALIASES.items():
        if alias in by_name and by_name[alias] != by_name[target]:
            collisions.setdefault(alias, []).append(target)
    if collisions:
        raise SystemExit(f"alias keys collide with real teams: {collisions}")
    mapping = dict(by_name)
    for alias, target in ALIASES.items():
        mapping.setdefault(alias, by_name[target])
    OUTPUT_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(mapping)} logo keys to {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
