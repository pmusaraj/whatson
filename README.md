# What's On TV

What's On TV is a v0 static TV guide for quickly seeing what is on now and next across a curated set of international channels.

Live app: https://whatson.musaraj.com
Repo: https://github.com/pmusaraj/whatson

## What it does

- Shows a live, time-aligned guide grid for selected channels.
- Groups channels by country in a compact sidebar.
- Includes curated general channels plus premium/pay-TV sports channels.
- Searches across channels and programme titles/events.
- Opens programme details in a modal when metadata is available.
- Saves selected channels in browser `localStorage`.

Countries currently included:

| Country | General channels | Premium sports/pay-TV channels |
| --- | ---: | ---: |
| France | 12 | 25 |
| Spain | 18 | 21 |
| Canada | 20 | 14 |
| United States | 14 | 13 |
| United Kingdom | 19 | 16 |
| Italy | 10 | 8 |
| Germany | 12 | 13 |
| Turkiye | 12 | 6 |
| Portugal | 21 | 17 |
| Mexico | 10 | 10 |
| Brazil | 12 | 9 |

## Architecture

The app is intentionally simple and static:

- `web/` contains the browser app: `index.html`, `app.js`, CSS themes, and generated JSON data.
- `data/sources/iptv-org/` contains curated XMLTV channel files and iptv-org metadata snapshots.
- `data/normalized/` contains XMLTV guide snapshots fetched from validated public guide sources.
- `scripts/refresh_epg.py` refreshes all curated XMLTV snapshots and rebuilds the static JSON payloads.
- `scripts/build_web_data.py` converts XMLTV snapshots into browser-friendly files under `web/data/`.
- `tests/` covers the data-building and normalization logic.

The browser loads `web/data/countries.json`, then country payloads such as `web/data/FR.json` and `web/data/premium-FR.json`. Normal and premium payloads are merged client-side, de-duplicated by channel name, and rendered as schedule columns.

Times are stored in UTC in the generated JSON. The browser renders the current guide window from the user's local time.

## Data refresh and publishing

The live app is served from the `web/` directory at https://whatson.musaraj.com.

A Hermes cron job named `whatsontv EPG refresh` runs every 2 hours (`0 */2 * * *`) from this repository. It runs:

```bash
python3 scripts/refresh_epg.py
```

That script:

1. Runs the iptv-org EPG grabber for each curated channel file.
2. Sets `CURR_DATE` to yesterday and grabs 3 days of guide data.
3. Writes refreshed XMLTV snapshots to `data/normalized/`.
4. Rebuilds `web/data/*.json` with a 24-hour browser payload window: now - 4h through now + 20h.
5. Runs the unit tests and `node --check web/app.js`.

Publishing is file-based: once the refresh updates `web/`, the served site reflects the new data. There is no separate build or deploy step for the live v0 instance.

## Run locally

From the repository root:

```bash
cd /Users/pmusaraj/Projects/whatsontv
python3 -m http.server 8000 --directory web
```

Then open:

```text
http://localhost:8000
```

The committed `web/data/` files are enough to run the app locally without refreshing guide data.

## Rebuild local web data from existing XMLTV snapshots

```bash
python3 scripts/build_web_data.py
```

This reads `data/normalized/*.xml` and rewrites `web/data/*.json`.

## Refresh EPG snapshots locally

Refreshing source guide data requires the upstream iptv-org EPG grabber checkout and Node dependencies:

```bash
git clone --depth 1 https://github.com/iptv-org/epg.git .cache/epg
npm install --prefix .cache/epg
python3 scripts/refresh_epg.py
```

Use a dry run to inspect the grab commands without fetching data:

```bash
python3 scripts/refresh_epg.py --dry-run
```

Some upstream guide sources can fail, block, or return partial data. The refresh script keeps going and uses previous snapshots for failed sources.

## Tests

```bash
python3 -m unittest discover -s tests -v
node --check web/app.js
```

## Notes

This is a schedule/metadata guide only. It does not stream video.

The data comes from public guide sources through the iptv-org EPG tooling and curated channel mappings. Availability and licensing should be reviewed before using this beyond a personal/prototype context.
