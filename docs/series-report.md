# Weekly series report

## Scope

`/series` redirects to the static `/series/` page. The report is fully readable
without JavaScript, contains up to five ranked series per country, and links each pick
to editorial coverage and production information. France, Italy, Spain, the UK,
and Canada are **production-country sections**, not the critics' locations.
Canada is limited to Canadian originals with English or French as an original
language. A dub, Canadian filming location or Canadian distributor is insufficient.

The page is unlisted, not private. It has no incoming link from the guide UI;
the HTML robots meta tag and Cloudflare `_headers` request `noindex, nofollow`.
Do not put confidential material in the page, JSON or CI artifacts.

Only series first released in the current calendar year qualify (2026 for the
September 2026 edition). A new season or rerun does not make a pre-2026 series
eligible. Season numbers must be verified: seasons 6 and above are excluded,
and seasons 1–2 are selected and ranked before seasons 3–5. All picks must be
produced in their country section; imported shows cannot fill empty slots.
Countries with fewer than five eligible candidates show fewer picks, and empty
countries show an empty state. Rendering suppresses prior-year picks at rollover.

Cards include the broadcaster/platform or production company, plus source-linked
airing information where verified. Past broadcast runs are explicitly labelled;
streaming release dates do not imply a recurring linear-TV slot. Times use the
broadcaster's local country time. The compact heading has no introductory copy.

## Data and generation

- `data/series/catalogue.json`: reviewed titles, original languages, production
  countries, origin notes, review scope, original short copy and source links.
  The published catalogue contains the four approved picks from the expanded-source discovery pass: three recent broadcasts and one older fallback. Streaming-only, pending and unfavorable candidates are omitted. It is intentionally small; expand it
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
  After a changed report is pushed, the workflow calls the existing
  `CLOUDFLARE_DEPLOY_HOOK_URL` secret: bot pushes do not trigger Workers Builds
  automatically in this setup. A failed hook is a failed workflow, with the
  generated report still committed for a deploy retry.
- `scripts/build_cloudflare.sh`: renders the committed edition without calling
  the API. The initial report is checked in, so the page works before the first
  scheduled run.

The revised September 2026 edition has `selection.method = reviewed-discovery`. Subsequent
successful LLM runs use `llm` and record the actual model. Missing credentials,
authentication errors or invalid model output fail
the command without replacing the previous report. Availability errors use the
configured model fallback. There are at most nine requests (three network-error
attempts per configured model), each with a 120-second timeout; output is bounded
to 2,000 tokens and 64 KiB. CI has a 20-minute timeout.

## Add or update a candidate

1. Confirm the original series identity, first television/streaming release year
   (`year`) and numeric `season` being reviewed. Only the current year and seasons
   1–5 qualify. Festival previews do not set the television release year.
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
7. Add `broadcaster` and/or `productionCompany`. When verified, add `airing`
   with local day/time and dated run or streaming release, plus an HTTPS
   `airingSource`. Never imply a past run is airing this week.
8. Run `python3 -m unittest discover -s tests -p 'test_build_series_report.py' -v`.
   Then regenerate with `--force` locally with the key, or dispatch the workflow
   after publishing the catalogue change.

The initial British review summaries are particularly short; links point to the
original articles. No automated Guardian API or Télérama RSS ingestion is enabled.
A local discovery prototype now collects approved-source links and evaluates
reviewed candidates; see [discovery v1](series-discovery.md). It is not wired into CI.
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
without the model. Browser checks cover desktop/mobile overflow, the rendered picks and
source links, country anchors and the page with JavaScript disabled.
