#!/usr/bin/env python3
"""Prerender editor picks for readers that have not run JavaScript."""

import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_editor_picks import league_rank
START = "<!-- editor-picks:start -->"
END = "<!-- editor-picks:end -->"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


LEAGUE_CHIPS = [
    ("Premier League", "pl", r"\bpremier league\b"),
    ("La Liga", "laliga", r"\bla\s*liga\b"),
    ("Serie A", "seriea", r"\bserie a\b"),
    ("Ligue 1", "ligue1", r"\bligue 1\b"),
    ("Bundesliga", "buli", r"\bbundesliga\b"),
    ("Champions League", "ucl", r"\bchampions league\b"),
    ("Europa League", "uel", r"\beuropa league\b"),
    ("Formula 1", "f1", r"\bformula 1\b|\bf1\b"),
    ("MotoGP", "motogp", r"\bmotogp\b"),
    ("NFL", "nfl", r"\bnfl\b"),
    ("NBA", "nba", r"\bnba\b"),
    ("NHL", "nhl", r"\bnhl\b"),
    ("MLB", "mlb", r"\bmlb\b"),
    ("MLS", "mls", r"\bmls\b"),
    ("UFC", "ufc", r"\bufc\b"),
]

def pick_league(pick):
    import re
    text = " ".join(str(pick.get(key) or "") for key in ("title", "subtitle", "competition", "sportType"))
    for label, cls, pattern in LEAGUE_CHIPS:
        if re.search(pattern, text, re.I):
            return label, cls
    if pick.get("competition"):
        return pick["competition"], "generic"
    if pick.get("sportType"):
        return pick["sportType"], "generic"
    return None


def display_title(pick):
    league = pick_league(pick)
    if not league:
        return pick["title"]
    import re
    label = re.escape(league[0])
    return re.sub(r"\s*(?:\u2014|\u2013|-)\s*" + label + r"$|\s*\(" + label + r"\)$", "", pick["title"], flags=re.I)


CREST_COLORS = ["#126e5a", "#1d4fa3", "#a32323", "#8a4b00", "#4a2d8a", "#0e6e8c", "#7a3b00"]


def crest(name):
    import re
    words = [word for word in re.split(r"\s+", name) if word]
    initials = (words[0][0] + words[1][0]).upper() if len(words) > 1 else name[:3].upper()
    hashed = 0
    for char in name:
        hashed = (hashed * 31 + ord(char)) % (2 ** 32)
    return f'<span class="editor-pick-crest">{escape(initials)}</span>'.replace(
        'class="editor-pick-crest"', f'class="editor-pick-crest" style="background:{CREST_COLORS[hashed % len(CREST_COLORS)]}"')


def split_teams(pick):
    import re
    parts = re.split(r"\s+vs\.?\s+|\s+v\s+", display_title(pick), flags=re.I)
    if len(parts) != 2:
        return None
    home, away = (part.strip() for part in parts)
    return (home, away) if home and away else None


def day_label(start, now):
    diff = (start.date() - now.date()).days
    if diff <= 0:
        return "Tonight"
    if diff == 1:
        return "Tomorrow"
    return start.strftime("%A")


def render_picks(picks, now, generated_at=None):
    events = []
    for pick in picks:
        if pick.get("highlightType") != "liveSport" or league_rank(pick) < 0:
            continue
        airings = [airing for airing in pick.get("channels", [pick]) if parse_time(airing["endAt"]) > now]
        if not airings:
            continue
        start = parse_time(pick["startAt"])
        names = []
        seen = set()
        countries = {}
        for airing in airings:
            key = (airing.get("country", ""), airing["channelName"])
            if key in seen or countries.get(key[0], 0) >= 3:
                continue
            seen.add(key)
            countries[key[0]] = countries.get(key[0], 0) + 1
            names.append(airing["channelName"])
        league = pick_league(pick)
        league_html = (f'<span class="editor-pick-league editor-pick-league-{league[1]}">{escape(league[0])}</span>'
                       if league else "")
        teams = split_teams(pick)
        if teams:
            home, away = teams
            team_rows = (
                f'<div class="editor-pick-team">{crest(home)}<span class="editor-pick-team-name">{escape(home)}</span></div>'
                f'<div class="editor-pick-team">{crest(away)}<span class="editor-pick-team-name">{escape(away)}</span></div>')
        else:
            team_rows = f'<div class="editor-pick-team"><span class="editor-pick-team-name">{escape(display_title(pick))}</span></div>'
        extra = f" +{len(names) - 1} more" if len(names) > 1 else ""
        events.append(((start, league_rank(pick)), day_label(start, now), (
            '<article class="editor-pick-result">\n'
            f'  <div class="editor-pick-context">{league_html + " \u00b7 " if league else ""}{len(names)} broadcaster{"s" if len(names) != 1 else ""}</div>\n'
            '  <div class="editor-pick-fixture">\n'
            f'    <div class="editor-pick-teams">{team_rows}</div>\n'
            f'    <div class="editor-pick-kickoff">{start:%H:%M}</div>\n'
            '  </div>\n'
            f'  <span class="editor-pick-watch">Catch it live on <strong>{escape(names[0])}</strong>{extra}</span>\n'
            '</article>'
        )))
    groups = []
    for (_, _rank), label, html in sorted(events, key=lambda event: event[0]):
        if groups and groups[-1][0] == label:
            groups[-1][1].append(html)
        else:
            groups.append((label, [html]))
    rows = []
    for label, htmls in groups:
        rows.append(
            f'<section class="editor-pick-day-group">'
            f'<div class="editor-pick-day-head">{escape(label)}<span class="editor-pick-day-count">{len(htmls)} match{"es" if len(htmls) != 1 else ""}</span></div>'
            + "".join(htmls) + '</section>')
    if rows:
        count = f"{sum(len(htmls) for _, htmls in groups)} pick" + ("" if sum(len(htmls) for _, htmls in groups) == 1 else "s")
        updated = f" \u00b7 updated {parse_time(generated_at):%b %d, %H:%M} UTC" if generated_at else ""
        meta = f'<p class="editor-picks-meta">{escape(count + updated + " \u00b7 refreshes throughout the day")}</p>'
    else:
        updated = f" Last updated {parse_time(generated_at):%b %d, %H:%M} UTC \u00b7 picks refresh throughout the day." if generated_at else ""
        meta = ("<p class=\"empty-program\">No upcoming editor\u2019s picks right now \u2014 "
                f"the next slate lands soon.{escape(updated)}</p>")
    visibility = "" if rows else " hidden"
    return (
        f'<section id="editor-picks" class="editor-picks" aria-label="Editor\'s Picks"{visibility}>\n'
        f'  <div id="editor-picks-list" class="show-results-list">{meta}' + "".join(rows) + '</div>\n'
        '</section>'
    )


def build_html(template, picks, now, generated_at=None):
    before, section = template.split(START)
    _, after = section.split(END)
    return before + START + "\n" + render_picks(picks, now, generated_at) + "\n" + END + after


if __name__ == "__main__":
    path = ROOT / "web" / "index.html"
    data = json.loads((ROOT / "web" / "data" / "editors-picks.json").read_text())
    path.write_text(build_html(path.read_text(), data.get("picks", []), datetime.now(timezone.utc), data.get("generatedAt")))
    print("Prerendered editor picks in web/index.html")
