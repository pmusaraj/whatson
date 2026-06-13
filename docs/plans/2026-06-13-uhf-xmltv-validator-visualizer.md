# UHF XMLTV Validator and Visualizer Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a repeatable validator and lightweight browser visualization for `https://heywhatson.tv/data/uhf/epg.xml` so we can diagnose why downstream apps sometimes show wrong or stale data.

**Architecture:** Keep the source of truth as the generated UHF XMLTV export under `web/data/uhf/epg.xml`, but add a Python validation/reporting layer that produces machine-readable JSON diagnostics and a compact preview payload. Add a static HTML visualizer under `web/` that reads those generated JSON files, not the 13 MB XML directly, so it works on Cloudflare Pages and locally without a backend.

**Tech Stack:** Python stdlib (`xml.etree.ElementTree`, `csv`, `json`, `datetime`, `argparse`, `gzip`, `unittest`), static HTML/CSS/JS, existing GitHub Actions workflow.

---

## Background and current files

Current relevant files:

- UHF export builder: `scripts/build_uhf_custom_xmltv.py`
- UHF refresh wrapper: `scripts/refresh_uhf_epg.py`
- UHF workflow: `.github/workflows/refresh-uhf-epg.yml`
- Generated XMLTV: `web/data/uhf/epg.xml`
- Generated gzip XMLTV: `web/data/uhf/epg.xml.gz`
- Generated channel join table: `web/data/uhf/channels.json` and `web/data/uhf/channels.csv`
- Generated build summary: `web/data/uhf/summary.json`
- Existing app shell: `web/index.html`, `web/app.js`, `web/styles.css`, `web/sense-theme.css`
- Tests: `tests/`

Current export characteristics from local data on 2026-06-13:

- `web/data/uhf/epg.xml`: about 13.4 MB
- XMLTV channels: 245
- XMLTV programmes: 22,692
- Public URL: `https://heywhatson.tv/data/uhf/epg.xml`

The existing workflow only checks:

- XML parses.
- Gzip parses.
- Programme `channel` refs point to declared `<channel>` ids.

That is not enough to debug downstream guide problems. We need validation around recency, time ranges, channel identity, sparse channels, duplicate/overlapping programmes, suspicious mappings, empty placeholder titles, and a way to inspect channel schedules visually.

---

## Acceptance criteria

1. `python3 scripts/validate_uhf_xmltv.py` validates the committed UHF export and writes:
   - `web/data/uhf/validation.json`
   - `web/data/uhf/preview.json`
2. Validation checks include at least:
   - XML and gzip parse successfully.
   - XML and gzip contain matching channel/programme counts.
   - every programme references a declared channel.
   - channel ids are unique and use `uhf:<uhf_pk>` format.
   - every channel in `web/data/uhf/channels.json` exists in XML and vice versa.
   - programme start/stop times parse and `start < stop`.
   - export `generatedAt`/XML `date` is recent enough for the configured UHF cadence.
   - per-channel coverage stats: current programme, next programme, programme count, first/last programme, biggest gaps, overlaps.
   - warnings for channels with no current programme, no programmes in next 24h, stale last programme, duplicate exact slots, heavy overlaps, empty titles, placeholder/no-event titles.
   - summary counts by severity: `errors`, `warnings`, `info`.
3. `scripts/build_uhf_custom_xmltv.py` or `scripts/refresh_uhf_epg.py` runs the validator after generating `epg.xml`.
4. `.github/workflows/refresh-uhf-epg.yml` uses the new validator instead of the current inline Python smoke test.
5. A static visualizer exists at `web/uhf.html` with supporting `web/uhf.js` and optional `web/uhf.css`.
6. Visualizer lets us inspect:
   - validation health summary.
   - generated time and coverage window.
   - channel list grouped/searchable by country/category/name/custom id/target id.
   - each channel’s current and next programmes.
   - per-channel warnings and raw identifiers needed for UHF/downstream app debugging.
7. README documents the public XMLTV URL, gzip URL, validation JSON URL, preview URL, and visualizer URL.
8. Tests pass:
   - `python3 -m unittest discover -s tests -v`
   - `node --check web/app.js`
   - `node --check web/uhf.js`
   - `python3 scripts/validate_uhf_xmltv.py --input web/data/uhf/epg.xml --channels web/data/uhf/channels.json --summary web/data/uhf/summary.json --out-validation /tmp/validation.json --out-preview /tmp/preview.json`

---

## Design decisions

### Validator output files

Create two outputs:

- `web/data/uhf/validation.json`: full validation report for tooling and debugging.
- `web/data/uhf/preview.json`: smaller, UI-oriented schedule preview for static visualization.

Do not make the browser parse `epg.xml` directly by default. The XML is large and XML parsing in browser code makes the visualizer slower and harder to use on mobile.

### Validation severity model

Use three levels:

- `error`: should fail CI/workflow because the XMLTV export is structurally invalid or unusable.
- `warning`: should not fail CI by default, but likely explains bad downstream guide behavior.
- `info`: useful debugging facts.

Default CLI behavior:

- Exit `1` if there are any `error` findings.
- Exit `0` if there are only warnings/info.
- Add `--strict-warnings` to exit `1` on warnings later if desired.

### Recency thresholds

The UHF workflow runs every two days (`35 3 */2 * *`). Set default staleness warning threshold to 72 hours, not 6 hours.

CLI defaults:

- `--max-age-hours 72`
- `--current-window-minutes 15` to tolerate small clock/build differences when deciding “current”.
- `--preview-hours-before 4`
- `--preview-hours-after 20`

### Time model

XMLTV times are in the format used by `iptv-org` snapshots, typically `YYYYmmddHHMMSS +0000` or with another offset. Parse to UTC and expose ISO strings ending in `Z`.

### Privacy/safety

Do not include stream URLs, credentials, playlist server names, or raw UHF cache columns. The visualizer should use only existing safe artifacts:

- custom XMLTV ids (`uhf:<pk>`)
- display names
- categories
- public/logo URLs
- target guide ids and countries
- programme metadata already present in the XMLTV export

---

## Proposed JSON shapes

### `web/data/uhf/validation.json`

```json
{
  "generatedAt": "2026-06-13T14:31:30Z",
  "validatedAt": "2026-06-13T17:45:00Z",
  "source": {
    "xml": "web/data/uhf/epg.xml",
    "gzip": "web/data/uhf/epg.xml.gz",
    "channelsJson": "web/data/uhf/channels.json",
    "summaryJson": "web/data/uhf/summary.json"
  },
  "counts": {
    "channels": 245,
    "programmes": 22692,
    "channelsWithCurrent": 238,
    "channelsWithNext24h": 242,
    "errors": 0,
    "warnings": 12,
    "info": 0
  },
  "coverage": {
    "firstProgrammeStartAt": "2026-06-12T00:00:00Z",
    "lastProgrammeEndAt": "2026-06-15T23:30:00Z",
    "now": "2026-06-13T17:45:00Z"
  },
  "findings": [
    {
      "severity": "warning",
      "code": "channel.no_current_programme",
      "message": "Channel has no programme covering validation time",
      "channelId": "uhf:123",
      "channelName": "Example Channel"
    }
  ],
  "channels": [
    {
      "id": "uhf:123",
      "name": "Example Channel",
      "category": "Canada",
      "targetXmltvId": "TSN1.ca",
      "targetCountry": "CA",
      "programmeCount": 93,
      "firstStartAt": "2026-06-12T04:00:00Z",
      "lastEndAt": "2026-06-15T04:00:00Z",
      "currentProgramTitle": "SportsCentre",
      "nextProgramTitle": "FIFA World Cup 2026",
      "warningCount": 0,
      "errorCount": 0
    }
  ]
}
```

### `web/data/uhf/preview.json`

```json
{
  "generatedAt": "2026-06-13T14:31:30Z",
  "previewWindow": {
    "startAt": "2026-06-13T13:45:00Z",
    "endAt": "2026-06-14T13:45:00Z"
  },
  "channels": [
    {
      "id": "uhf:123",
      "name": "Example Channel",
      "displayNames": ["Example Channel", "Target Name"],
      "category": "Canada",
      "targetCountry": "CA",
      "targetXmltvId": "TSN1.ca",
      "logoUrl": "https://example.com/logo.png",
      "warnings": ["channel.no_current_programme"],
      "programs": [
        {
          "title": "SportsCentre",
          "subtitle": null,
          "description": "Sports news and highlights.",
          "categories": ["Sports", "News"],
          "startAt": "2026-06-13T17:00:00Z",
          "endAt": "2026-06-13T18:00:00Z"
        }
      ]
    }
  ]
}
```

---

## Implementation tasks

### Task 1: Add a tiny XMLTV parsing helper module

**Objective:** Create reusable parsing utilities so validator tests do not depend on `build_web_data.py` internals.

**Files:**

- Create: `scripts/xmltv_utils.py`
- Test: `tests/test_validate_uhf_xmltv.py`

**Step 1: Write failing tests**

Create `tests/test_validate_uhf_xmltv.py` with initial tests for time parsing and ISO formatting:

```python
import importlib.util
import unittest
from datetime import timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "xmltv_utils.py"
spec = importlib.util.spec_from_file_location("xmltv_utils", MODULE_PATH)
xmltv_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xmltv_utils)


class XmltvUtilsTest(unittest.TestCase):
    def test_parse_xmltv_time_returns_utc(self):
        value = "20260613123000 -0400"
        parsed = xmltv_utils.parse_xmltv_time(value)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(xmltv_utils.iso_z(parsed), "2026-06-13T16:30:00Z")

    def test_parse_xmltv_time_rejects_empty_value(self):
        with self.assertRaises(ValueError):
            xmltv_utils.parse_xmltv_time("")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify failure**

Run:

```bash
python3 -m unittest tests.test_validate_uhf_xmltv -v
```

Expected: FAIL because `scripts/xmltv_utils.py` does not exist.

**Step 3: Implement helper**

Create `scripts/xmltv_utils.py`:

```python
#!/usr/bin/env python3
"""Small XMLTV parsing helpers shared by UHF validation/reporting scripts."""

from __future__ import annotations

from datetime import datetime, timezone

XMLTV_TIME_FORMAT = "%Y%m%d%H%M%S %z"


def parse_xmltv_time(value: str) -> datetime:
    if not value:
        raise ValueError("missing XMLTV time")
    return datetime.strptime(value, XMLTV_TIME_FORMAT).astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

**Step 4: Verify pass**

Run:

```bash
python3 -m unittest tests.test_validate_uhf_xmltv -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/xmltv_utils.py tests/test_validate_uhf_xmltv.py
git commit -m "test: add XMLTV time utility coverage"
```

---

### Task 2: Add validator CLI skeleton and structural checks

**Objective:** Add `scripts/validate_uhf_xmltv.py` that parses XML, gzip, channels JSON, and summary JSON; emits validation JSON; and fails on structural errors.

**Files:**

- Create: `scripts/validate_uhf_xmltv.py`
- Modify: `tests/test_validate_uhf_xmltv.py`

**Step 1: Add failing test for structural validation**

Append to `tests/test_validate_uhf_xmltv.py`:

```python
import json
import tempfile
from xml.etree import ElementTree as ET

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_uhf_xmltv.py"
validator_spec = importlib.util.spec_from_file_location("validate_uhf_xmltv", VALIDATOR_PATH)
validate_uhf_xmltv = importlib.util.module_from_spec(validator_spec)
validator_spec.loader.exec_module(validate_uhf_xmltv)


class UhfXmltvValidatorTest(unittest.TestCase):
    def test_validate_minimal_xmltv_reports_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xml_path = root / "epg.xml"
            xml_path.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>News</title></programme>
</tv>
""",
                encoding="utf-8",
            )
            channels_path = root / "channels.json"
            channels_path.write_text(json.dumps([{
                "custom_xmltv_id": "uhf:1",
                "name": "One",
                "category": "News",
                "target_xmltv_id": "One.us",
                "target_country": "US"
            }]), encoding="utf-8")
            summary_path = root / "summary.json"
            summary_path.write_text(json.dumps({"generatedAt": "2026-06-13T12:00:00Z"}), encoding="utf-8")

            report, preview = validate_uhf_xmltv.validate(
                xml_path=xml_path,
                gzip_path=None,
                channels_path=channels_path,
                summary_path=summary_path,
                now=validate_uhf_xmltv.parse_iso_datetime("2026-06-13T12:30:00Z"),
            )

        self.assertEqual(report["counts"]["channels"], 1)
        self.assertEqual(report["counts"]["programmes"], 1)
        self.assertEqual(report["counts"]["errors"], 0)
        self.assertEqual(preview["channels"][0]["programs"][0]["title"], "News")
```

**Step 2: Run test to verify failure**

```bash
python3 -m unittest tests.test_validate_uhf_xmltv -v
```

Expected: FAIL because validator script does not exist.

**Step 3: Implement validator skeleton**

Create `scripts/validate_uhf_xmltv.py` with:

- `argparse` CLI arguments:
  - `--input`, default `web/data/uhf/epg.xml`
  - `--gzip`, default `web/data/uhf/epg.xml.gz`
  - `--channels`, default `web/data/uhf/channels.json`
  - `--summary`, default `web/data/uhf/summary.json`
  - `--out-validation`, default `web/data/uhf/validation.json`
  - `--out-preview`, default `web/data/uhf/preview.json`
  - `--max-age-hours`, default `72`
  - `--preview-hours-before`, default `4`
  - `--preview-hours-after`, default `20`
  - `--strict-warnings`, action `store_true`
- `validate(...) -> tuple[dict, dict]`
- `parse_iso_datetime(value: str) -> datetime`
- `finding(severity, code, message, **extra) -> dict`
- parse XML root with `ElementTree.parse`
- collect channels and programmes
- check duplicate channel ids
- check bad programme refs
- write JSON outputs from `main()`
- exit non-zero if errors exist, or if `--strict-warnings` and warnings exist

Use `scripts/xmltv_utils.py` for XMLTV time parsing. Since scripts are imported by tests using `spec_from_file_location`, add this import fallback pattern:

```python
try:
    from xmltv_utils import iso_z, parse_xmltv_time
except ModuleNotFoundError:
    import importlib.util
    _UTILS_PATH = Path(__file__).resolve().parent / "xmltv_utils.py"
    _spec = importlib.util.spec_from_file_location("xmltv_utils", _UTILS_PATH)
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    iso_z = _module.iso_z
    parse_xmltv_time = _module.parse_xmltv_time
```

**Step 4: Verify pass**

```bash
python3 -m unittest tests.test_validate_uhf_xmltv -v
```

Expected: PASS.

**Step 5: Smoke test current export**

```bash
python3 scripts/validate_uhf_xmltv.py --out-validation /tmp/uhf-validation.json --out-preview /tmp/uhf-preview.json
```

Expected: exits 0 unless structural errors are found. Warnings are acceptable.

**Step 6: Commit**

```bash
git add scripts/validate_uhf_xmltv.py tests/test_validate_uhf_xmltv.py
git commit -m "feat: add UHF XMLTV validator skeleton"
```

---

### Task 3: Add semantic per-channel validation checks

**Objective:** Expand the validator to explain “wrong data” symptoms, not just structural XML validity.

**Files:**

- Modify: `scripts/validate_uhf_xmltv.py`
- Modify: `tests/test_validate_uhf_xmltv.py`

**Step 1: Add failing tests**

Add tests for:

1. programme with stop before start -> `error: programme.invalid_time_range`
2. programme references missing channel -> `error: programme.unknown_channel`
3. channel with no current programme at `now` -> `warning: channel.no_current_programme`
4. exact duplicate programme slot -> `warning: programme.duplicate_exact_slot`
5. placeholder title -> `warning: programme.placeholder_title`

Example test style:

```python
def test_channel_without_current_programme_warns(self):
    # Build XML with a channel and only yesterday's programme.
    # Validate with now set to 2026-06-13T12:30:00Z.
    # Assert a finding with code "channel.no_current_programme" exists.
```

Keep each fixture tiny: one or two channels and one to three programmes.

**Step 2: Implement checks**

Add these functions to `scripts/validate_uhf_xmltv.py`:

- `programme_title(programme: ET.Element) -> str`
- `programme_categories(programme: ET.Element) -> list[str]`
- `channel_display_names(channel: ET.Element) -> list[str]`
- `programme_to_preview(programme: ET.Element) -> dict`
- `build_channel_reports(...) -> list[dict]`
- `detect_channel_gaps(programmes: list[ParsedProgramme]) -> list[dict]`

Checks to implement:

- channel ids:
  - missing `id`
  - duplicate id
  - not matching `^uhf:\d+$`
- programme attrs:
  - missing `channel`, `start`, `stop`
  - unknown channel ref
  - invalid time parse
  - `start >= stop`
- title quality:
  - empty `<title>`
  - placeholder titles case-insensitive:
    - `no events`
    - `no upcoming events`
    - `nessun evento`
    - `nessun evento in programma`
    - `sin eventos`
    - `aucun événement`
- duplicate/overlap checks per channel:
  - exact duplicate key `(start, stop, title)`
  - same time slot with different title
  - overlap where `overlap / shorter_duration >= 0.5`
- coverage checks per channel:
  - no current programme at `now`
  - no programme starting or airing in next 24 hours
  - last programme ended before `now`
  - first programme starts more than 12 hours after `now`

Important: warnings should include `channelId` and `channelName` where possible.

**Step 3: Verify tests**

```bash
python3 -m unittest tests.test_validate_uhf_xmltv -v
```

Expected: PASS.

**Step 4: Run against real export**

```bash
python3 scripts/validate_uhf_xmltv.py --out-validation /tmp/uhf-validation.json --out-preview /tmp/uhf-preview.json
python3 - <<'PY'
import json
report = json.load(open('/tmp/uhf-validation.json'))
print(report['counts'])
for finding in report['findings'][:20]:
    print(finding)
PY
```

Expected: structural errors should be zero. Warnings should be reviewed; they are useful signal.

**Step 5: Commit**

```bash
git add scripts/validate_uhf_xmltv.py tests/test_validate_uhf_xmltv.py
git commit -m "feat: validate UHF XMLTV channel coverage"
```

---

### Task 4: Generate committed validation and preview JSON during UHF export

**Objective:** Make validation outputs part of the normal generated artifacts under `web/data/uhf/`.

**Files:**

- Modify: `scripts/refresh_uhf_epg.py`
- Possibly modify: `scripts/build_uhf_custom_xmltv.py`
- Generated: `web/data/uhf/validation.json`
- Generated: `web/data/uhf/preview.json`

**Step 1: Add integration call**

Prefer adding the call in `scripts/refresh_uhf_epg.py` after line 90:

```python
run(["python3", "scripts/build_uhf_custom_xmltv.py"])
run(["python3", "scripts/validate_uhf_xmltv.py"])
print("UHF EPG refresh complete", flush=True)
```

This keeps `build_uhf_custom_xmltv.py` focused on building XMLTV and lets validation remain a separate tool.

**Step 2: Run local generator without refreshing upstream sources**

Use existing snapshots only:

```bash
python3 scripts/build_uhf_custom_xmltv.py
python3 scripts/validate_uhf_xmltv.py
```

Expected:

- `web/data/uhf/validation.json` exists.
- `web/data/uhf/preview.json` exists.
- command exits 0 unless structural errors exist.

**Step 3: Inspect output size**

```bash
python3 - <<'PY'
from pathlib import Path
for path in ['web/data/uhf/validation.json', 'web/data/uhf/preview.json']:
    p = Path(path)
    print(path, p.stat().st_size)
PY
```

If `preview.json` is too large, cap preview programmes per channel to the 24-hour window only and omit long descriptions by default. Include full descriptions only in `validation.json` if needed; the UI can link to XML/channel ids rather than storing everything twice.

**Step 4: Commit**

```bash
git add scripts/refresh_uhf_epg.py web/data/uhf/validation.json web/data/uhf/preview.json
git commit -m "feat: publish UHF validation outputs"
```

---

### Task 5: Replace inline workflow smoke test with validator

**Objective:** Make GitHub Actions run the same validator used locally.

**Files:**

- Modify: `.github/workflows/refresh-uhf-epg.yml`

**Step 1: Edit workflow**

Replace the current `Verify UHF XMLTV export` inline Python block at lines 41-65 with:

```yaml
      - name: Validate UHF XMLTV export
        run: python3 scripts/validate_uhf_xmltv.py
```

Update the commit step at line 71 to include validation artifacts explicitly. Current `web/data/uhf` already catches them, so no path change is strictly required.

**Step 2: Validate YAML visually**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
path = Path('.github/workflows/refresh-uhf-epg.yml')
text = path.read_text()
assert 'Validate UHF XMLTV export' in text
assert 'scripts/validate_uhf_xmltv.py' in text
print('workflow validation step present')
PY
```

**Step 3: Commit**

```bash
git add .github/workflows/refresh-uhf-epg.yml
git commit -m "ci: validate UHF XMLTV export with shared script"
```

---

### Task 6: Add static visualizer page shell

**Objective:** Add a separate UHF visualizer route without disturbing the main guide UI.

**Files:**

- Create: `web/uhf.html`
- Create: `web/uhf.css`
- Create: `web/uhf.js`

**Step 1: Create `web/uhf.html`**

Use a minimal static shell:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>UHF XMLTV inspector -- heywhatson.tv</title>
    <meta name="description" content="Inspect the generated UHF XMLTV guide feed, validation warnings, channels, and programme coverage." />
    <link rel="stylesheet" href="uhf.css?v=uhf-validator-v1" />
  </head>
  <body>
    <header class="page-header">
      <a class="brand" href="/">heywhatson.tv</a>
      <div>
        <h1>UHF XMLTV inspector</h1>
        <p id="status">Loading UHF validation data…</p>
      </div>
    </header>

    <main>
      <section id="summary" class="summary-grid" aria-label="Validation summary"></section>
      <section class="controls" aria-label="Filters">
        <input id="search" type="search" placeholder="Search channel, id, target, programme…" autocomplete="off" />
        <select id="severity-filter" aria-label="Severity">
          <option value="all">All channels</option>
          <option value="errors">Channels with errors</option>
          <option value="warnings">Channels with warnings</option>
          <option value="clean">Clean channels</option>
        </select>
      </section>
      <section class="workspace">
        <aside id="channel-list" class="channel-list" aria-label="Channels"></aside>
        <section id="channel-detail" class="channel-detail" aria-label="Selected channel"></section>
      </section>
    </main>

    <script src="uhf.js?v=uhf-validator-v1"></script>
  </body>
</html>
```

**Step 2: Create simple CSS**

Keep the visualizer utilitarian and readable. Do not import the main app’s complex responsive sidebar rules initially. Use CSS grid/flex and `min-height: 0` for scroll regions.

**Step 3: Create JS skeleton**

`web/uhf.js` should:

- fetch `data/uhf/validation.json`
- fetch `data/uhf/preview.json`
- render summary cards
- render channel list
- render first channel details
- show fetch errors clearly

**Step 4: Syntax check**

```bash
node --check web/uhf.js
```

Expected: no output / exit 0.

**Step 5: Commit**

```bash
git add web/uhf.html web/uhf.css web/uhf.js
git commit -m "feat: add UHF XMLTV inspector shell"
```

---

### Task 7: Implement visualizer channel details and filters

**Objective:** Make the inspector genuinely useful for debugging downstream-guide mismatches.

**Files:**

- Modify: `web/uhf.js`
- Modify: `web/uhf.css`

**Step 1: Implement data join**

In `web/uhf.js`, build maps:

```js
const validationByChannel = new Map(validation.channels.map((channel) => [channel.id, channel]));
const findingsByChannel = new Map();
for (const finding of validation.findings || []) {
  if (!finding.channelId) continue;
  if (!findingsByChannel.has(finding.channelId)) findingsByChannel.set(finding.channelId, []);
  findingsByChannel.get(finding.channelId).push(finding);
}
```

Merge each preview channel with its validation stats.

**Step 2: Channel list row contents**

Each row should show:

- channel display name
- `uhf:<pk>` id
- category and target country
- target XMLTV id
- badges: error/warning counts, current/no-current, programme count

**Step 3: Channel detail contents**

Selected channel detail should show:

- header with logo, name, id
- raw mapping facts:
  - `custom_xmltv_id`
  - `target_xmltv_id`
  - `target_country`
  - `category`
  - all display names
- validation findings for that channel
- current/next status
- programme list in local time and UTC
- programme categories and description if present

**Step 4: Search behavior**

Search should match:

- channel name
- custom id
- target XMLTV id
- target country
- category
- programme title in preview window

**Step 5: Severity filter**

Implement:

- `all`
- `errors`
- `warnings`
- `clean`

**Step 6: Verify in local browser server**

Run:

```bash
python3 -m http.server 8000 --directory web
```

Open:

```text
http://localhost:8000/uhf.html
```

Manual checks:

- summary loads
- channel count matches validation JSON
- searching `TSN` filters to TSN-like channels
- selecting a channel shows current/next programmes
- a channel warning appears in both row and detail

**Step 7: Syntax check**

```bash
node --check web/uhf.js
```

Expected: exit 0.

**Step 8: Commit**

```bash
git add web/uhf.js web/uhf.css
git commit -m "feat: inspect UHF channel validation details"
```

---

### Task 8: Add README documentation and links

**Objective:** Document how to use the validator/visualizer and what each public artifact means.

**Files:**

- Modify: `README.md`

**Step 1: Add section after “Data refresh and publishing”**

Add:

```markdown
## UHF / Xtream XMLTV export

The project also publishes a private/custom XMLTV-style guide export for approved UHF/Xtream channel mappings:

- XMLTV: https://heywhatson.tv/data/uhf/epg.xml
- Gzipped XMLTV: https://heywhatson.tv/data/uhf/epg.xml.gz
- Channel mapping index: https://heywhatson.tv/data/uhf/channels.json
- Build summary: https://heywhatson.tv/data/uhf/summary.json
- Validation report: https://heywhatson.tv/data/uhf/validation.json
- Visual inspector: https://heywhatson.tv/uhf.html

The export uses stable custom channel ids in the form `uhf:<uhf_pk>`, with display-name aliases copied from the UHF playlist row and the matched source guide channel.

To validate the committed export locally:

```bash
python3 scripts/validate_uhf_xmltv.py
```

Warnings in `validation.json` are useful for debugging downstream guide clients. Structural errors fail the command and the UHF refresh workflow.
```

**Step 2: Update tests section**

Add:

```bash
node --check web/uhf.js
python3 scripts/validate_uhf_xmltv.py
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document UHF XMLTV validation tools"
```

---

### Task 9: End-to-end verification before opening/deploying

**Objective:** Verify all code, generated artifacts, and live-static assumptions before push/deploy.

**Files:**

- No new files expected.

**Step 1: Run full local checks**

```bash
python3 scripts/build_uhf_custom_xmltv.py
python3 scripts/validate_uhf_xmltv.py
python3 -m unittest discover -s tests -v
node --check web/app.js
node --check web/uhf.js
```

Expected:

- validator exits 0
- tests pass
- node checks pass

**Step 2: Inspect generated validation summary**

```bash
python3 - <<'PY'
import json
report = json.load(open('web/data/uhf/validation.json'))
print(report['counts'])
print('first findings:')
for finding in report.get('findings', [])[:10]:
    print(finding)
PY
```

Expected:

- `errors` should be `0`.
- warnings should be understandable and actionable.

**Step 3: Serve locally**

```bash
python3 -m http.server 8000 --directory web
```

Open:

```text
http://localhost:8000/uhf.html
```

Verify:

- visualizer loads without console errors.
- summary counts match `validation.json`.
- channel detail shows current/next programmes.
- search/filter works.

**Step 4: Commit generated files if changed**

```bash
git status --short
```

If expected generated files changed:

```bash
git add web/data/uhf/validation.json web/data/uhf/preview.json
git commit -m "chore: update UHF validation artifacts"
```

**Step 5: Push and verify live URLs**

After push/Pages deploy:

```bash
curl -fsSL https://heywhatson.tv/data/uhf/validation.json -o /tmp/live-uhf-validation.json
curl -fsSL https://heywhatson.tv/data/uhf/preview.json -o /tmp/live-uhf-preview.json
curl -I -L https://heywhatson.tv/uhf.html
python3 - <<'PY'
import json
report = json.load(open('/tmp/live-uhf-validation.json'))
print(report['generatedAt'], report['counts'])
PY
```

Expected:

- `uhf.html` returns HTTP 200.
- validation and preview JSON parse.
- live generatedAt matches committed data.

---

## Later enhancements, not required for v1

Do not build these in the first pass unless the first validator/visualizer is already working:

1. Add downloadable per-channel mini XMLTV files for debugging a single downstream mapping.
2. Add an XMLTV client compatibility report for specific apps if we identify exact client expectations.
3. Add history tracking across refreshes to detect channel ids whose target mapping changed.
4. Add a GitHub Actions artifact with the full validation report diff from the previous run.
5. Add a browser-side XMLTV file upload mode for comparing another app’s imported file.

---

## Open questions for implementation review

1. Should warnings ever fail the UHF workflow, or should only structural errors fail CI?
   - Proposed v1: only errors fail; warnings are published.
2. Should `preview.json` include descriptions?
   - Proposed v1: include short descriptions only if size stays reasonable; otherwise title/subtitle/categories/times are enough.
3. Should `uhf.html` be linked from the main app UI?
   - Proposed v1: no visible main-app link until it feels polished; direct URL is enough.
4. Is the downstream app sensitive to channel id format (`uhf:<pk>`) or display-name matching?
   - Validator should expose both id and aliases so we can diagnose once we know the other app’s matching behavior.

---

## Definition of done

- Local validator exists and catches real bad XMLTV cases in unit tests.
- Validator generates `web/data/uhf/validation.json` and `web/data/uhf/preview.json`.
- UHF refresh workflow runs the validator.
- Static inspector at `/uhf.html` displays validation status and channel schedules.
- README documents URLs and commands.
- Full test/check suite passes.
- Live URLs parse and match committed generated data after deploy.
