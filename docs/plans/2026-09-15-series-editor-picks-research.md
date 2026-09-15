# Series editor picks: research and proposed implementation

Date: 2026-09-15. Status: research only; no implementation or publishing enabled.

Implementation follow-up: the user subsequently approved an unlisted `/series`
page with weekly top-five reports by production country and added Canadian
originals in English/French. See [the implemented scope and maintenance guide](../series-report.md).
The proposal below is retained as research history; its research-only status and
artifact-only trial are superseded. Initial delivery uses a reviewed catalogue
and weekly LLM ranking; automated publisher ingestion and EPG joins remain future
work rather than dependencies of the weekly watchlist.

## Recommendation

Build a separate catalogue of critically recommended non-US series/seasons, backed by
French, Italian, Spanish and UK editorial sources. Use the existing OpenCode Go
integration to extract recommendations, interpret multilingual titles and explain
selections. Join that catalogue to Whatson's schedules using validated identities.
Trial the results as CI artifacts before considering any website integration.

Confirmed scope: both the editorial sources and the series must be non-US.
Use editorial sources from France, Italy, Spain and the UK. Series from other
non-US countries remain eligible; the source-country list does not itself restrict
production origin to those four countries.

Keep `sourceCountry`, `productionCountries`, and `broadcastCountry` separate.
Require sourced production-country evidence before selecting a series. Unknown
or conflicting origin remains pending review, not eligible by default; language,
cast nationality, distributor and channel country cannot establish it.
Proposed conservative default: exclude co-productions listing the US as a
production country. A US platform distributing a series does not alone make it
a US production. Record the evidence and exclusion reason for each decision.

Start with scripted series and miniseries. Treat documentaries, reality shows and
children's programming as separate future editorial decisions. These are proposed
defaults, not existing requirements.

## What the repository already provides

- `.github/workflows/refresh-epg.yml` runs every 12 hours, passes
  `OPENCODE_GO_API_KEY`, and commits `data/normalized` and `web/data`.
- `scripts/build_editor_picks.py` calls OpenCode Go's chat-completions endpoint
  with JSON output, temperature zero, response validation and atomic file writes.
  The configured fallback order is `deepseek-v4.1-flash`, `glm-5.3-flash`, then
  `kimi-k2.6`. This is repository configuration, not a verification of current
  provider availability or pricing.
- Despite some series eligibility helpers, candidate collection discards
  non-sports candidates and the selection prompt explicitly excludes series.
- Sports grouping requires overlapping airtime within 90 minutes. That is not
  suitable for grouping a series with multiple episodes or broadcasts on different
  days. The repeat filter is also too aggressive for worthwhile series reruns.
- `scripts/build_web_data.py` preserves episode/new/premiere/date metadata when
  present, but many upstream listings do not supply it.
- `scripts/build_cloudflare.sh` renders sports picks into `web/index.html`.
  Writing experimental series output into the existing picks file would therefore
  risk publishing it through both data and HTML paths.
- The LLM request contains supplied candidate text, with no browsing/search tool.
  A prompt asking it to research reviews would not supply current evidence.

### Observed metadata gaps

Read-only audit of the regular country JSON files in this checkout on the research
date. Counts cover all programme entries, not unique series; premium files were
not included. This is one snapshot, not a long-term coverage measurement.

| Feed | Programme entries | Description present | Episode field present | New / premiere / original date present |
| --- | ---: | ---: | ---: | --- |
| FR | 428 | 400 | 0 | None |
| IT | 610 | 282 | 129 | None |
| ES | 499 | 499 | 333 | None |
| UK | 350 | 0 | 0 | None |

UK programme categories were also absent. Italy sometimes embeds season and
episode in the title, such as `(St. 1 - Ep. 21)`; Spain sometimes combines series,
episode numbering and episode title. Thus a strict “must be new” or category-only
filter would silently exclude much of the catalogue. Missing metadata is not
evidence that a broadcast is a premiere, repeat, or even a series.

The repository uses `UK`, not `GB`, for its country feed. Normalize external
country codes at the boundary. Existing browser payloads cover now minus four
hours through now plus twenty hours; use normalized XMLTV for a longer research
window only where the actual snapshot contains that coverage.

## Editorial source shortlist

These are editorial candidates, not approved automated integrations. Publisher
pages were inspected through web research; unattended fetching from GitHub Actions,
complete article extraction, permissions and sustained coverage remain untested.

| Country | Primary candidates | Useful evidence | Access findings / next check |
| --- | --- | --- | --- |
| France | [Télérama series](https://www.telerama.fr/series-tv/), [Le Monde series](https://www.lemonde.fr/series/) | Reviews, weekly selections and curated lists; distinguish critic selections from reader votes. | Télérama documents dedicated review feeds but restricts reuse; Le Monde is a secondary candidate whose extractable article coverage needs testing. |
| Italy | [Comingsoon reviews](https://www.comingsoon.it/serietv/recensioni/), [Movieplayer TV articles](https://movieplayer.it/tv/articoli/) | Comingsoon provides a focused, dated review index; Movieplayer combines reviews and broader TV coverage. | Both indexes were readable. Test article bodies and permitted automation; filter Movieplayer's interviews, news, films and episode recaps. |
| Spain | [EL PAÍS TV criticism](https://elpais.com/noticias/critica-television/), [Vertele analysis](https://www.eldiario.es/vertele/analisis/) | Signed criticism and editorial recommendations. | EL PAÍS documents a TV RSS feed. Vertele analysis also covers industry and programmes; classify each article rather than treating the whole section as recommendations. |
| UK | [The Guardian TV & radio](https://www.theguardian.com/uk/tv-and-radio) | Review coverage. | Assess API eligibility before ingestion. |

Additional options: [MYmovies series](https://www.mymovies.it/serietv/) for Italian
review/identity enrichment, with editorial and audience ratings kept separate.
[Radio Times drama](https://www.radiotimes.com/tv/drama/) redirected to a TollBit
host during this research; [Fotogramas series](https://www.fotogramas.es/series-tv/)
could not be retrieved by the research browser. Neither is a first dependency;
these observations do not establish that all clients will be blocked.

### Concrete acquisition constraints

- Télérama's [RSS documentation](https://www.telerama.fr/ecrans/les-flux-rss-de-telerama-pour-suivre-nos-critiques-et-nos-articles-sur-l-actualite-de-la-culture-3041-81284.php)
  lists series, review and free-article feeds. It explicitly reserves RSS use for
  personal, non-professional, non-collective purposes, with authorization and
  payment for other exploitation. Treat it as a valuable editorial reference,
  with an unresolved integration dependency. Feed retrieval itself did not
  succeed through the research browser.
- The Guardian's [API access page](https://open-platform.theguardian.com/access/)
  offers a non-commercial developer tier at one request/second and 500/day.
  Its commercial category includes text/data mining, sentiment analysis and
  derived products. Do not assume that a free key or unpublished trial settles
  the intended use. Its [RSS help](https://www.theguardian.com/help/feeds)
  documents adding `/rss` to index URLs.
- EL PAÍS's [RSS directory](https://elpais.com/info/rss/) links a Televisión feed.
  Feed discovery does not establish full-article access or LLM-processing rights.
- For other candidates, automated access and use terms are unresolved. Before
  enabling an adapter, check its actual feed/article response, applicable access
  conditions and whether the intended external model processing is supported.
  Do not bypass subscriptions or access blocks.

These findings favor a small, explicitly configured source registry rather than
open-ended web search on every CI run. RSS/API availability is useful for discovery;
it is not by itself an editorial endorsement or permission to reuse article text.

## Proposed pipeline

```text
Configured editorial sources
          |
Fetch changed, permitted material + retain source provenance
          |
LLM: classify articles and extract series/season recommendations
          |
Validate evidence and resolve series identities
          |
Persistent series/season catalogue
          |                         Current XMLTV / country JSON
          +-----------------------------------+
                              |
                Match and validate scheduled airings
                              |
                  Rank eligible recommendations
                              |
              CI JSON + Markdown review artifacts
```

### 1. Acquire and retain evidence

Maintain a source registry with publisher, country, language, discovery URL,
adapter, access status, and enabled flag. Start with at most two sources per
country, subject to access validation. Fetch daily; use conditional requests,
bounded retries, response-size limits, caching and content hashes. Fetch only
allowlisted hosts, including after redirects.

Save canonical article URL, publisher, author, publication/update dates, retrieval
time, content hash and the permitted evidence used. Keep fetched text as untrusted
data. Do not include navigation, ads, embedded instructions or reader comments in
the extraction prompt. A search-result snippet or headline alone can nominate a
candidate, but should not establish a confident positive review.

### 2. Use the existing LLM transport, with a new task/schema

Reuse the authentication, model fallback and bounded-response patterns. A future
implementation could extract a shared client while preserving sports behavior.
Do not reuse the sports selection prompt or output file.

For each changed article, ask for:

- Supplied article ID and exact evidence span/offset references.
- Article type: review, critics' list, preview, recap, interview, news or promotion.
- Series title as written, stated aliases, year, season/episode scope when known.
- Verdict: strong recommendation, positive, mixed, negative or unclear.
- Original rating and scale if explicitly present; no fabricated numerical score.
- A brief English rationale grounded in the cited evidence, without spoilers.
- Explicit uncertainties, including partial article access.

Validate IDs and that evidence spans occur in the supplied input. Semantic support
still requires sampling/manual review; a valid substring alone does not prove the
model interpreted it correctly. Reject invalid output and quarantine that article.
Evidence URLs come from the fetcher, never newly invented by the model.

Extract in the original language, preserving titles; translate the short rationale
afterwards. Cache by source hash, prompt/schema version and model. Model changes
must be visible in evaluation reports. The model should abstain when evidence is
insufficient rather than fill gaps from its training memory.

### 3. Resolve series, seasons and airings separately

Use a persistent internal series ID and a reviewed alias table first. Add an
external metadata provider later only if title ambiguity justifies its access and
maintenance cost. Title normalization alone is insufficient for remakes and
same-name series. Evidence may establish a series without establishing a season.

Prefer exact known aliases plus corroborating year, cast, season or description.
Use the LLM to propose uncertain multilingual matches from a bounded candidate
list, then route ambiguity to review. Preserve original schedule titles.

Parse episode suffixes while retaining the raw text. Normalize episode numbering
with awareness of its source convention; XMLTV numbering can be zero-based.
An endorsement of season one must not become evidence for season three.

Resolve production origin from attributable production credits, official
broadcaster/producer information or a verified metadata record. Retain the source
URL and scope (series or season); investigate conflicts and season-specific
co-production changes. The LLM may extract this evidence but cannot establish
origin from memory. Apply the non-US production filter before ranking.

Join to schedules separately. Every matched airing retains country, channel ID,
start/end time and original title from actual EPG input. A series can have many
airings; those airings need not overlap. Keep unmatched recommendations in the
catalogue and label them as having no verified airing in the available window.
An editorial article naming a streaming service does not establish current
availability in the viewer's country.

### 4. Rank with a transparent policy

Suggested trial policy:

- Require editorial evidence from the configured FR/IT/ES/UK publications and
  verified non-US production origin. Exclude US productions and, under the
  proposed conservative rule, US co-productions; hold unknown origins for review.
- Require one clear positive editorial review/list endorsement for eligibility.
  Prefer corroboration from a second independent publication, but do not require
  cross-country coverage that would penalize smaller domestic productions.
- Treat “most anticipated,” trailers, popularity charts, audience votes and
  broadcaster promotion as discovery, not critical approval.
- Count each publisher once per series/season; syndicated duplicates do not add
  votes. Keep mixed/negative evidence and expose disagreements to reviewers.
- Prefer strong, relevant evidence, then independently supported recommendations,
  then near-term verified airings. Do not average incomparable publisher scales.
- Permit critically supported reruns as rediscoveries. “Premiere,” “new season,”
  and “starts at episode one” require their own evidence.
- Begin with up to eight series, a soft target of two supported by sources in each
  country. A series appears once even if several countries cover it. Report source
  coverage without padding weak or unknown entries to meet the target.
- Separate evidence age from availability: seed a durable back catalogue, check
  fresh reviews daily, and prioritize recent evidence for new-season claims.
  Old reviews remain usable for the season they actually discuss.

Code should enforce eligibility, evidence membership, identity and airing validity.
Use the LLM for extraction and short explanations; deterministic ranking makes
changes and disagreements easier to inspect.

## Proposed data contract

Keep three distinct record types:

1. **Editorial evidence:** evidence ID, article URL, source country/language,
   publisher/author, dates, hash, access completeness, verdict, original rating,
   series/season scope and evidence references.
2. **Series/season:** stable internal ID, display/original titles, verified aliases,
   production countries or unknown, origin evidence URLs and scope, origin
   eligibility/exclusion reason, year/season or unknown, linked evidence IDs,
   match status and editorial rationale.
3. **Airing:** series/season ID, episode or unknown, original EPG title,
   country/channel, UTC start/end, snapshot identity and match method/status.

Each run records generated time, input hashes, source health, model/prompt versions,
token usage when available, proposed picks and rejection reasons. Keep identity
certainty, editorial strength and schedule certainty separate; one model confidence
number should not hide missing evidence.

## CI trial design — future work only

Propose a separate `research-series-picks.yml` workflow, initially manual-only:

- Reuse `OPENCODE_GO_API_KEY` on trusted workflow runs; do not expose it to
  untrusted pull-request code. Use `contents: read`, a timeout and bounded requests.
- Write to a research output directory outside `web/`; upload JSON and a Markdown
  report with short retention. Artifacts are not necessarily private in a public
  repository: include derived review results and links, not restricted article
  bodies or credentials.
- No commits, pushes, deploy hooks, website rendering or production picks writes.
  A trial failure must not block normal EPG refreshes.
- Persist the permitted evidence catalogue/cache between runs; a fresh Actions
  runner cannot otherwise maintain historical recommendations. Version cache keys
  and distinguish a cache miss from “no recommendations.”
- On source failure, label coverage degraded; preserve earlier evidence with its
  original timestamps. Revalidate airings against fresh schedules. Never pass an
  old availability claim off as current because the previous run succeeded.
- After reviewing manual runs, consider a daily research schedule. Rejoin the
  catalogue to EPG on its 12-hour refresh cadence without re-extracting unchanged
  reviews. Publishing remains a separate future change.

Suggested initial bounds: 10 new/changed articles per source/day, up to eight
sources, short evidence inputs and a hard run token/request ceiling. At a planning
allowance of 2,000 input and 500 output tokens per article, a maximum 80-article
day is roughly 160k input + 40k output tokens before retries or matching. This is
a sizing estimate, not a price or provider entitlement; measure actual usage and
confirm the existing plan's limits before choosing a schedule.

## Validation and decision gates

Before building a scheduled integration:

1. Validate usable access for at least one editorial source in each country.
2. Assemble about 40 manually checked examples, balanced across languages and
   including negative reviews, previews, partial access, translated titles,
   remakes, season-specific reviews and duplicate articles. Include US productions
   praised by European critics, US co-productions, non-US productions distributed
   by US platforms, and unknown/conflicting production origins.
3. Compare LLM extraction against those labels. Suggested targets: at least 95%
   precision for positive editorial claims and accepted identity matches; report
   abstention/coverage too. These are proposed goals, not measured results.
4. Require all selected evidence IDs/URLs to trace to inputs and every accepted
   airing/time/channel to exist in the current schedule. Reject wrong seasons,
   invented premieres, expired airings and unverified streaming availability.
   Require traceable non-US origin evidence for every selected series; no US or
   unknown-origin series may pass the proposed eligibility rules.
5. Review several days of artifacts: source-country balance, unsupported claims,
   catalogue-to-EPG match rate, source failures, latency and model usage. UK sparse
   metadata is a specific coverage risk to measure rather than guess around.

Future tests should cover those failure cases and confirm research output never
touches production files. No application tests or LLM runs were needed for this
documentation-only research.

## Suggested implementation sequence

1. Source access spike and reviewed multilingual evaluation fixtures.
2. Separate evidence extractor using the existing OpenCode Go transport.
3. Series/season catalogue, alias resolution and read-only EPG join.
4. Manual CI artifact workflow and several days of evaluation.
5. Decide whether the evidence and coverage justify a product feature.

This research does not implement any of these stages. The main unknowns are
source access for automated processing, quality of multilingual identity matching,
and how often critically recommended series occur in Whatson's curated channels.
