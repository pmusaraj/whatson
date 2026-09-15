# What's On TV

This is a static TV guide for quickly seeing what is on now and next across a curated set of international channels.

Live app: https://heywhatson.tv

## What it does

- Shows a live, time-aligned guide grid for selected channels.
- Groups channels by country.
- Includes curated general channels plus premium/pay-TV sports channels.
- Searches across channels and programme titles/events.
- Opens programme details in a modal when metadata is available.
- Saves selected channels in browser `localStorage`.

Countries currently included:

| Country        | General channels | Premium sports/pay-TV channels |
| -------------- | ---------------: | -----------------------------: |
| France         |               12 |                             12 |
| Spain          |               19 |                             19 |
| Canada         |               27 |                             14 |
| United States  |               34 |                             12 |
| United Kingdom |               19 |                             16 |
| Italy          |                9 |                              6 |
| Germany        |               12 |                             12 |
| Turkiye        |               12 |                              6 |
| Portugal       |               21 |                             17 |
| Mexico         |               10 |                             10 |
| Brazil         |               12 |                              9 |

## Architecture

The app is intentionally simple and static:

- `web/` contains the browser app: `index.html`, `app.js`, CSS themes, and generated JSON data.
- `data/sources/iptv-org/` contains curated XMLTV channel files and iptv-org metadata snapshots.
- `data/normalized/` contains committed XMLTV snapshots fetched from validated public guide sources; UHF snapshots are generated only during Cloudflare builds.
- `scripts/refresh_epg.py` refreshes all curated XMLTV snapshots and rebuilds the static JSON payloads.
- `scripts/build_web_data.py` converts XMLTV snapshots into browser-friendly files under `web/data/`.
- `tests/` covers the data-building and normalization logic.

The browser loads `web/data/countries.json`, then country payloads such as `web/data/FR.json` and `web/data/premium-FR.json`. Normal and premium payloads are merged client-side, de-duplicated by channel name, and rendered as schedule columns.

Times are stored in UTC in the generated JSON. The browser renders the current guide window from the user's local time.

## Data refresh and publishing

Cloudflare Workers Builds serves the `web/` directory at https://heywhatson.tv.

A GitHub Actions workflow runs every 12 hours (`5 */12 * * *`) and updates the regular guide data. It runs:

```bash
python3 scripts/refresh_epg.py
```

That script:

1. Runs the iptv-org EPG grabber for each curated channel file.
2. Sets `CURR_DATE` to yesterday and grabs 3 days of guide data.
3. Writes refreshed XMLTV snapshots to `data/normalized/`.
4. Rebuilds `web/data/*.json` with a 24-hour browser payload window: now - 4h through now + 20h.
5. Runs the unit tests and `node --check web/app.js`.

## UHF / Xtream XMLTV export

The project also publishes a custom XMLTV-style guide export for approved UHF/Xtream channel mappings:

- XMLTV: https://heywhatson.tv/data/uhf/epg.xml
- Gzipped XMLTV: https://heywhatson.tv/data/uhf/epg.xml.gz
- Stable-ID XMLTV (recommended for new UHF configurations): https://heywhatson.tv/data/uhf/epg-stable.xml
- Gzipped stable-ID XMLTV: https://heywhatson.tv/data/uhf/epg-stable.xml.gz
- Channel mapping index: https://heywhatson.tv/data/uhf/channels.json
- Build summary: https://heywhatson.tv/data/uhf/summary.json
- Validation report: https://heywhatson.tv/data/uhf/validation.json
- Preview data: https://heywhatson.tv/data/uhf/preview.json
- Visual inspector: https://heywhatson.tv/uhf.html

The export includes display-name aliases copied from the UHF playlist row and the matched source guide channel. UHF source snapshots and exports are generated during each Cloudflare build and are not committed.

The original export retains its historical `uhf:<uhf_pk>` IDs for compatibility. These IDs refer to the original playlist export; UHF's database row IDs can change after a playlist is reimported. The new `epg-stable.xml` uses source IDs such as `CA:TSN1.ca` and `ES:La1.es`, groups duplicate playlist variants into one schedule, and keeps their display-name aliases. The same stable feed is also generated at `/data/epg.xml` for older saved provider references. These new URLs become available after deploying this change.

Orange Spain is fetched by `scripts/grab_orange_epg.py`: each of the three daily eight-hour segments contains all channels, so it downloads each segment once rather than repeatedly fetching it for every channel. Downloads retry transient failures and publish the snapshot only after all segments succeed. Canadian grab timeouts scale with the selected channel count.

Prioritized Movistar feeds use `scripts/grab_movistar_epg.py`, which reads the official public daily schedules. Programme times are interpreted in `Europe/Madrid`, including midnight and daylight-saving transitions; the following listing supplies each end time. An extra day provides the final boundary. This avoids the unreliable legacy API and its optional per-programme detail requests. Legacy playlist labels such as Estrenos 2 and Series 2 remain unmapped until a current equivalent is verified.

Configure the connected Worker's build command as:

```bash
bash scripts/build_cloudflare.sh
```

The scheduled UHF workflow runs every 12 hours and calls a Cloudflare deploy hook stored in the GitHub Actions secret `CLOUDFLARE_DEPLOY_HOOK_URL`. This keeps the yesterday/today/tomorrow guide window from expiring between refreshes.

To generate and validate the export locally:

```bash
bash scripts/build_cloudflare.sh
```

Warnings in `validation.json` are useful for debugging downstream guide clients. Structural errors fail the command and the UHF refresh workflow.

### Test Canada and Spain in local UHF

With the pinned grabber installed, refresh just these countries and serve the result:

```bash
python3 scripts/refresh_uhf_epg.py --countries CA ES
python3 -m http.server 8765 --bind 127.0.0.1 --directory web
```

Set Estv's EPG URL to `http://127.0.0.1:8765/data/uhf/epg-stable.xml` and refresh its EPG in UHF. This address works only on the Mac running the server. Manually assigned channels must refer to the same provider and a channel ID present in the feed; a saved assignment to a removed provider overrides automatic name matching. A country-only refresh exports the available local snapshots, so use a full refresh to include other countries on a fresh checkout.

For similarly named numbered feeds, explicitly assign the EPG channel in UHF. Local UI testing found that automatic matching could show a LaLiga overflow schedule on the main LaLiga row even though the parsed cache contained an exact name alias. TSN uses `CA:TSN1.ca` through `CA:TSN5.ca`; the main LaLiga feed uses `ES:LaLigaTVporMovistarPlusPlus.es`. The target IDs for the other rows are in `data/uhf-channel-mapping.csv`.

To check the actual imported schedules without UI automation, use UHF's local database and its JSON cache under the app container's `Data/Library/Caches/CachedEPGs/` directory:

```bash
python3 scripts/audit_uhf_epg.py --database /path/to/Data/Documents/.uhf.sqlite \
  --cache /path/to/Data/Library/Caches/CachedEPGs/cache-file --playlist Estv
```

The audit is read-only and reports matched rows, current programmes, and next-24-hour coverage for Canada and Spain. It does not print stream URLs or credentials. Missing or obsolete source channels are reported as unmatched rather than assigned fabricated schedules.

## Run locally

From the repository root:

```bash
python3 -m http.server 8000 --directory web
```

Then open:

```text
http://localhost:8000
```

The committed regular-guide files under `web/data/` are enough to run the main app locally without refreshing guide data. UHF pages require `bash scripts/build_cloudflare.sh` first.

## Rebuild local web data from existing XMLTV snapshots

```bash
python3 scripts/build_web_data.py
```

This reads `data/normalized/*.xml` and rewrites `web/data/*.json`.

## Regenerate editor picks

With `OPENCODE_GO_API_KEY` available in the environment, regenerate picks from the current browser payloads:

```bash
python3 scripts/build_editor_picks.py
```

Each Cloudflare build also renders the current sports picks into `web/index.html`, so event titles, UTC times, and channel names are available without JavaScript. The browser replaces that snapshot with local times and interactive channel buttons, and removes expired events. To rebuild just the HTML locally, run `python3 scripts/build_editor_picks_html.py`.

OpenCode Go tries `deepseek-v4.1-flash`, `glm-5.3-flash`, then `kimi-k2.6` in the order defined by `OPENCODE_GO_MODELS` in `scripts/build_editor_picks.py`. Both selection and expansion use this list. HTTP 403/404/429/5xx advance immediately to the next model; network errors advance after three attempts. Authentication, bad-request, and invalid-output errors still fail rather than changing models. No region consent is changed.

The model first selects quality highlights, then makes one semantic grouping pass over nearby broadcasts across all public country feeds. That second pass includes full descriptions and sparse/generic listings, allows up to 90 minutes of start-time variation with overlapping airtime, and cannot add new editorial events. Explicit replays, previously shown and expired entries stay excluded. Both passes must validate before the output is atomically replaced; failures preserve the previous file. If the last model returns HTTP 403, generation is skipped with a warning so the guide refresh can continue; other failures exit nonzero.

The regular refresh workflow already supplies the GitHub Actions secret `OPENCODE_GO_API_KEY` and runs this builder. After publishing code changes, run **Refresh EPG data** manually (or wait for its schedule) to regenerate and publish picks with fresh guide data.

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
node --check web/uhf.js
python3 scripts/validate_uhf_xmltv.py
```

## Notes

This is a schedule/metadata guide only. It does not stream or store video.

### France, Italy and Germany source validation

Country feeds can be refreshed independently without requesting editor picks:

```sh
python3 scripts/refresh_epg.py --countries FR IT DE --skip-editor-picks
```

SFR uses shared daily downloads, Super Guida TV uses its current HTML schedule,
and German sports have MagentaTV mappings. See
[the source validation notes](docs/country-guide-verification.md) for coverage,
channel corrections and remaining unavailable sources.
