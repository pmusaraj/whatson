#!/usr/bin/env python3
"""Prerender editor picks for readers that have not run JavaScript."""

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- editor-picks:start -->"
END = "<!-- editor-picks:end -->"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def render_picks(picks, now):
    events = []
    for pick in picks:
        if pick.get("highlightType") != "liveSport":
            continue
        airings = [airing for airing in pick.get("channels", [pick]) if parse_time(airing["endAt"]) > now]
        if not airings:
            continue
        start = parse_time(pick["startAt"])
        channels = dict.fromkeys(airing["channelName"] for airing in airings)
        events.append((start, (
            '<article class="editor-pick-result">\n'
            '  <div class="editor-pick-heading">\n'
            f'    <time class="show-result-time" datetime="{escape(start.isoformat(), quote=True)}">{start:%b %d, %H:%M} UTC</time>\n'
            f'    <strong class="show-result-title">{escape(pick["title"])}</strong>\n'
            '  </div>\n'
            f'  <div class="editor-pick-channels">{escape(" · ".join(channels))}</div>\n'
            '</article>'
        )))
    rows = "\n".join(html for _, html in sorted(events, key=lambda event: event[0]))
    visibility = "" if rows else " hidden"
    return (
        f'<section id="editor-picks" class="editor-picks" aria-label="Editor\'s Picks"{visibility}>\n'
        f'  <div id="editor-picks-list" class="show-results-list">{rows}</div>\n'
        '</section>'
    )


def build_html(template, picks, now):
    before, section = template.split(START)
    _, after = section.split(END)
    return before + START + "\n" + render_picks(picks, now) + "\n" + END + after


if __name__ == "__main__":
    path = ROOT / "web" / "index.html"
    picks = json.loads((ROOT / "web" / "data" / "editors-picks.json").read_text())["picks"]
    path.write_text(build_html(path.read_text(), picks, datetime.now(timezone.utc)))
    print("Prerendered editor picks in web/index.html")
