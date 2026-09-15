# Weekly series report

## Scope

`/series` redirects to the static `/series/` page. The report is fully readable
without JavaScript, contains five ranked series per country, and links each pick
to editorial coverage and production information. France, Italy, Spain, the UK,
and Canada are **production-country sections**, not the critics' locations.
Canada is limited to Canadian originals with English or French as an original
language. A dub, Canadian filming location or Canadian distributor is insufficient.

The page is unlisted, not private. It has no incoming link from the guide UI;
the HTML robots meta tag and Cloudflare `_headers` request `noindex, nofollow`.
Do not put confidential material in the page, JSON or CI artifacts.

The first edition contains researched recommendations and explicitly scoped
season reviews. Older series are intentional rediscoveries. The report does not
claim that a title is premiering, airing this week, or currently available from a
particular streaming provider. It is independent of the short EPG window.

## Data and generation

- `data/series/catalogue.json`: reviewed titles, original languages, production
  countries, origin notes, review scope, original short copy and source links.
  The initial catalogue has 30 candidates, six per country. It is intentionally small; expand it
  through research rather than asking a model to invent new recommendations.
- `scripts/build_series_report.py`: validates the catalogue, calls the same
  OpenCode Go endpoint/model order as sports picks, accepts only ranked catalogue
  IDs, and renders the report. The model receives concise catalogue facts, not
  scraped publisher article bodies. Copy, source URLs and origin are never taken
  from model output.
- `web/data/series.json`: complete latest edition, including provenance, catalogue
  hash, generation timestamp and model/token usage when supplied by the provider.
- `web/series/index.html`: prerendered page; `/series/series.js` only shows a notice
  if the edition's UTC week has expired.
- `data/series/reports/YYYY-MM-DD.json`: the last successful edition for the week
  beginning that Monday. `--force` replaces that week's archive, not older weeks.
- `.github/workflows/refresh-series.yml`: Monday 08:25 UTC and manual dispatch.
  Shares the EPG workflow's concurrency lock, checks out the latest branch, runs
  report tests, generates, uploads an artifact and commits only series outputs.
  A normal repeated run in the same week makes no model request. Use the `force`
  dispatch input to re-rank after editing the catalogue.
- `scripts/build_cloudflare.sh`: renders the committed edition without calling
  the API. The initial report is checked in, so the page works before the first
  scheduled run.

The initial edition has `selection.method = researched-bootstrap`. Subsequent
successful LLM runs use `llm` and record the actual model. Missing credentials,
authentication errors, invalid model output or insufficient country coverage fail
the command without replacing the previous report. Availability errors use the
configured model fallback. There are at most nine requests (three network-error
attempts per configured model), each with a 120-second timeout; output is bounded
to 2,000 tokens and 64 KiB. CI has a 20-minute timeout.

## Add or update a candidate

1. Confirm the original series identity, release year and season being reviewed.
   Distinguish remakes and similarly named series. Use one catalogue ID per series,
   even if several reviews discuss it. Use `scope` to narrow an endorsement to the
   season/episodes actually covered, rather than extending it to all seasons.
2. Check production-country evidence from a producer, broadcaster, festival or
   reliable production record. Record all known production countries and explain
   the basis in `originNote`. A domestic production commissioned/distributed by a
   US platform is not automatically a US co-production. If US participation as a
   production country is present, or the record is conflicting, do not approve it.
3. Choose a report country actually present in `productionCountries`. Non-US
   co-productions can appear once, in the primary editorial country section.
   The repository uses `UK`, not `GB`.
4. Link genuine non-US critical coverage. A review based on a preview screening is
   valid with its limited scope labelled; a release announcement alone is not.
   Critics' awards are labelled as such. Publisher pages may be subscription-only;
   do not imply that access is free or circumvent restrictions.
5. Write brief original copy, preserving qualifications in mixed reviews. Retain
   a separate production source. Set `checkedAt` to the actual research date, and
   `originVerified` only after reviewing the origin evidence. Do not simply advance
   source-check dates when generating a new weekly edition.
6. Include original-language codes (English `en`, French `fr`, etc.). For Canadian
   picks, at least English or French must be an original language.
7. Run `python3 -m unittest discover -s tests -p 'test_build_series_report.py' -v`.
   Then regenerate with `--force` locally with the key, or dispatch the workflow
   after publishing the catalogue change.

The initial British review summaries are particularly short; links point to the
original articles. No automated Guardian API or Télérama RSS ingestion is enabled.
Source discovery/extraction remains a separate future integration subject to the
access findings in the [research proposal](plans/2026-09-15-series-editor-picks-research.md).
Weekly CI currently refreshes selections from the reviewed catalogue; **new titles
and fresh reviews require a catalogue update**. It does not claim to crawl the
latest reviews or compute a comprehensive critics' consensus.

## Local preview and verification

```sh
python3 scripts/build_series_report.py --render-only
python3 -m http.server 8000 --directory web
# Open http://localhost:8000/series
```

Routing uses Cloudflare's default directory-index handling; no application router
or rewrite is needed. See [Cloudflare HTML handling](https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/)
and [static asset headers](https://developers.cloudflare.com/workers/static-assets/headers/).

Tests exercise country/origin/language restrictions, missing evidence, invented
or repeated model IDs, date boundaries, HTML escaping, unsafe links, preserved
outputs on failure, weekly idempotence, archives, network fallback and rendering
without the model. Browser checks cover desktop/mobile overflow, all 25 picks and
50 links, country anchors and the page with JavaScript disabled.
