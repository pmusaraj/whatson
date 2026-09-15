#!/usr/bin/env python3
"""Read-only comparison of Estv playlist selections with UHF's imported EPG cache.

Reports channel names and schedule coverage, never stream URLs or credentials.
Pass the .uhf.sqlite database and a JSON file from Library/Caches/CachedEPGs.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def audit(rows: list[tuple], cache: dict, now: datetime) -> dict:
    timestamp = (now - APPLE_EPOCH).total_seconds()
    names = cache.get("resolvedNameIds", {})
    programmes = cache.get("programmes", {})
    countries = defaultdict(lambda: {"playlistRows": 0, "matched": 0, "current": 0, "next24h": 0})
    results = []
    for category, name, explicit_id in rows:
        channel_id = explicit_id.split("!$!")[-1] if explicit_id else names.get(name)
        schedule = programmes.get(channel_id, [])
        current = next((p for p in schedule if p["start"] <= timestamp < p["end"]), None)
        next_day = any(p["end"] > timestamp and p["start"] < timestamp + 86400 for p in schedule)
        counts = countries[category]
        counts["playlistRows"] += 1
        counts["matched"] += bool(schedule)
        counts["current"] += current is not None
        counts["next24h"] += next_day
        results.append({"category": category, "name": name, "channelId": channel_id,
                        "matched": bool(schedule), "currentTitle": current.get("title") if current else None,
                        "next24h": next_day, "manualSelection": bool(explicit_id)})
    return {"checkedAt": now.isoformat(), "countries": dict(countries), "channels": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--playlist", default="Estv")
    parser.add_argument("--categories", nargs="+", default=["Canada", "Spain"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        playlists = connection.execute("SELECT ZID FROM ZPLAYLIST WHERE ZNAME=?", (args.playlist,)).fetchall()
        if len(playlists) != 1:
            parser.error("Expected exactly one matching playlist")
        rows = connection.execute(
            "SELECT ZCATEGORYNAME,ZNAME,ZEPGCHANNELID FROM ZPLAYLISTITEM WHERE ZPLAYLISTID=? AND ZTYPE=0",
            (playlists[0][0],),
        ).fetchall()
    rows = [row for row in rows if row[0] in args.categories]
    cache = json.loads(args.cache.read_text())["object"]
    report = audit(rows, cache, datetime.now(timezone.utc))
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["countries"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
