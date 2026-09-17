# Series discovery — local v1

Keep the source list in `data/series/discovery/sources.json`: the five countries'
broadcasters and review publications. No Netflix, Prime Video, Apple TV, Disney+
or other internet streaming services. Broadcaster websites remain useful as
sources, but a title needs a dated linear-channel broadcast to qualify.

The registry contains 47 sources. Expansion adds:

| Country | Added broadcasters | Added review publications |
| --- | --- | --- |
| France | M6 | CinéSérie, AlloCiné |
| Italy | — | TvBlog, ComingSoon |
| Spain | Mediaset España, 3Cat / TV3 | El País |
| UK | UKTV | — |
| Canada | Corus / Global, Rogers / Citytv, Télé-Québec | Showbizz.net |

A publication's news article or audience rating is not a critical review. Only
an actual editorial assessment can supply a review verdict. Broadcaster indexes
also contain imports, older shows and streaming exclusives; collecting a link
does not establish eligibility. Blocked or empty indexes need manual research
within the approved publications.

Run locally:

```sh
python3 scripts/discover_series.py --collect --output-dir /tmp/whatson-discovery-preview
python3 -m http.server 8002 --bind 127.0.0.1 --directory /tmp/whatson-discovery-preview
```

1. `--collect` fetches the approved indexes and saves article links in `leads.json`.
   It records inaccessible sources and empty results; these are not proof that a
   country has no eligible series. It does not archive article bodies.
2. Review leads or search those same publications. Add checked facts to
   `first-pass.json`, with a source URL for each fact. The initial snapshot is an
   agent-assisted research pass dated 16 September 2026, not exhaustive coverage.
3. The script applies current-year, domestic-origin, season <6, linear-broadcast
   and review requirements. Unverified facts stay pending. Unfavorable reviews
   are labelled, not converted into recommendations.
4. Rank broadcasts aged 0–13 days, then 14–20 days, then older fallbacks. Within
   each group favor seasons 1–2, then positive over mixed reviews. Keep up to five
   per country; don't fill missing countries with imports or earlier-year series.
5. Open `http://127.0.0.1:8002/`. `result.json` includes every decision and source.

This version automates link collection, filtering and the preview. Fact extraction
and review assessment are still reviewed research, not an unattended LLM step.
The approved four-pick snapshot has been promoted to the production catalogue,
current report and weekly archive. Discovery remains a local research process;
weekly CI ranks only the reviewed catalogue and does not discover new titles.

## Expanded-source research pass — 16 September 2026

The reviewed dataset now contains 13 candidates: three recent recommendations,
one older fallback, two pending, two unfavorable reviews and five exclusions.
Sur le fil moved from pending to recommended after locating Showbizz.net's
editorial review through targeted search (the index did not expose it).

New decisions:

- Le Mystère de la chambre jaune: TF1 confirms 10 September airing; accessible
  Télérama assessment is unfavorable.
- Pénélope partout: Télé-Québec confirms season 1, Canadian origin and Thursday
  21:30 broadcasts starting 10 September. Production company and editorial
  review remain unverified. Its 2025 production year is distinct from release.
- Hit Point: UKTV confirms the channel and producer; Guardian listings show a
  recent airing and favorable assessment. Still pending official dated airing,
  numeric season and complete production-country evidence.
- Gènesi: TV3 premiere is 21 September, after the snapshot date.
- Il metodo Paraldi: ComingSoon confirms a 2027 Paramount+ release; excluded.

Evidence URLs are attached to each candidate in `first-pass.json`. Index links
still include navigation, older titles and unrelated programmes: the 476 links
collected are not 476 distinct shows. For example, 3Cat's Cronos announcement
is for a film, so it was not added to the series dataset. This remains a partial
research pass; empty country sections do not establish that no eligible series exist.
