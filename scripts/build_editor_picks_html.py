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

SPORT_EMOJI = [
    ("🏎️", r"formula 1|\bf1\b|grand prix|motogp|superbikes|nascar|rally|sailgp|supercars|cyclo-cross"),
    ("🏈", r"nfl|american football|arena football|college football"),
    ("🏉", r"australian football|australian rules|\bafl\b|rugby|nrl"),
    ("🏏", r"cricket|\bt20\b"),
    ("🥊", r"boxing|mma|\bufc\b|combat"),
    ("🏒", r"hockey|\bnhl\b"),
    ("🏀", r"basketball|\bnba\b"),
    ("⚾", r"baseball|\bmlb\b"),
    ("🎾", r"tennis|atp|wta|us open|wimbledon"),
    ("⛳", r"golf|pga|ryder cup"),
    ("🚴", r"cycling|tour de|giro|vuelta"),
    ("⚽", r"football|soccer|league|liga|serie|cup|derby|fc |united|city|real |barcelona|chelsea|arsenal"),
]


def pick_league(pick):
    import re
    text = " ".join(str(pick.get(key) or "") for key in ("title", "subtitle", "competition", "sportType"))
    for label, cls, pattern in LEAGUE_CHIPS:
        if re.search(pattern, text, re.I):
            return label, cls
    if pick.get("competition"):
        return pick["competition"], "generic"
    return None


def display_title(pick):
    league = pick_league(pick)
    if not league:
        return pick["title"]
    import re
    label = re.escape(league[0])
    return re.sub(r"\s*(?:\u2014|\u2013|-)\s*" + label + r"$|\s*\(" + label + r"\)$", "", pick["title"], flags=re.I)


def sport_emoji(pick):
    import re
    text = " ".join(str(pick.get(key) or "") for key in ("title", "subtitle", "competition", "sportType", "description"))
    for emoji, pattern in SPORT_EMOJI:
        if re.search(pattern, text, re.I):
            return emoji
    return "🏅"


def flag_emoji(country):
    return "".join(chr(127397 + ord(char)) for char in str(country or "").upper() if char.isalpha())


def pick_status(pick, now, fallback_end=None):
    start = parse_time(pick["startAt"])
    end = parse_time(pick["endAt"]) if pick.get("endAt") else fallback_end
    if start <= now and (end is None or now < end):
        return "live", "Live"
    mins = max(0, round((start - now).total_seconds() / 60))
    if mins < 360:
        if mins < 60:
            return "soon", f"in {mins}m"
        hours, rest = divmod(mins, 60)
        return ("soon", f"in {hours}h {rest}m" if rest else f"in {hours}h")
    time = f"{start:%b %d, %H:%M} UTC"
    if (start.date() - now.date()).days <= 1:
        return "later", f"Tomorrow \u00b7 {time}"
    return "later", f"{start:%a} \u00b7 {time}"


def render_picks(picks, now, generated_at=None):
    events = []
    for pick in picks:
        if pick.get("highlightType") != "liveSport" or league_rank(pick) < 0:
            continue
        airings = [airing for airing in pick.get("channels", [pick]) if parse_time(airing["endAt"]) > now]
        if not airings:
            continue
        start = parse_time(pick["startAt"])
        ends = [parse_time(airing["endAt"]) for airing in airings]
        end = parse_time(pick["endAt"]) if pick.get("endAt") else max(ends)
        channels = []
        countries = {}
        seen = set()
        for airing in airings:
            country = airing.get("country", "")
            key = (country, airing["channelName"])
            if key in seen or countries.get(country, 0) >= 3:
                continue
            seen.add(key)
            countries[country] = countries.get(country, 0) + 1
            channels.append((country, f'<span class="editor-pick-channel">{escape(airing["channelName"])}</span>'))
        def render_groups(items):
            grouped = []
            for country, html in items:
                if grouped and grouped[-1][0] == country:
                    grouped[-1][1].append(html)
                else:
                    grouped.append((country, [html]))
            return "".join(
                f'<span class="editor-pick-country-group">'
                f'<span class="editor-pick-flag">{flag_emoji(country)}</span>{"".join(chunk)}</span>'
                for country, chunk in grouped
            )
        # The fold applies to broadcasts (as in the browser); grouping is display-only.
        channel_html = render_groups(channels[:6])
        if len(channels) > 6:
            channel_html += ('<details class="editor-pick-more"><summary>more</summary>'
                             '<div class="editor-pick-channels">' + render_groups(channels[6:]) + '</div></details>')
        kind, label = pick_status(pick, now, end)
        league = pick_league(pick)
        league_html = (f'<span class="editor-pick-league editor-pick-league-{league[1]}">{escape(league[0])}</span>'
                       if league else "")
        dot = '<span class="editor-pick-live-dot"></span>' if kind == "live" else ""
        if kind == "later":
            time_html = ""
        elif start.date() == end.date():
            time_html = f"{start:%b %d, %H:%M} \u2013 {end:%H:%M} UTC"
        else:
            time_html = f"{start:%b %d, %H:%M} \u2013 {end:%b %d, %H:%M} UTC"
        time_row = (f'    <time class="show-result-time" datetime="{escape(start.isoformat(), quote=True)}">{time_html}</time>\n' if time_html else '')
        events.append(((league_rank(pick), start), (
            '<article class="editor-pick-result"{HERO}>\n'
            '  <div class="editor-pick-status-row">\n'
            f'    <span class="editor-pick-badge editor-pick-badge-{kind}">{dot}{escape(label)}</span>\n'
            f'    {league_html}\n'
            f'{time_row}'
            '  </div>\n'
            '  <div class="editor-pick-heading">\n'
            f'    <span class="editor-pick-sport">{sport_emoji(pick)}</span>\n'
            f'    <strong class="show-result-title">{escape(display_title(pick))}</strong>\n'
            '  </div>\n'
            f'  <div class="editor-pick-channels">{channel_html}</div>\n'
            '</article>'
        )))
    ordered = sorted(events, key=lambda event: event[0])
    rows = []
    for position, (_, html) in enumerate(ordered):
        rows.append(html.replace("{HERO}", ' data-hero="true"' if position == 0 else ""))
    if rows:
        count = f"{len(rows)} pick" + ("" if len(rows) == 1 else "s")
        updated = f" \u00b7 updated {parse_time(generated_at):%b %d, %H:%M} UTC" if generated_at else ""
        meta = f'<p class="editor-picks-meta">{escape(count + updated + " \u00b7 refreshes throughout the day")}</p>'
    else:
        updated = f" Last updated {parse_time(generated_at):%b %d, %H:%M} UTC \u00b7 picks refresh throughout the day." if generated_at else ""
        meta = ("<p class=\"empty-program\">No upcoming editor’s picks right now \u2014 "
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
