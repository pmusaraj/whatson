# Spike 001: iptv-org data source for France, Spain, Canada

## Question

Given the MVP countries France, Spain, and Canada, can public iptv-org metadata provide enough channel and guide mapping coverage to justify building the first ingestion adapter?

## Approach

- Downloaded `countries.json`, `channels.json`, and `guides.json` from iptv-org public APIs.
- Filtered channels to `FR`, `ES`, and `CA`.
- Counted channels with guide mappings.
- Identified strongest guide-source sites per country.
- Generated custom channel XML files that can be passed to the upstream `iptv-org/epg` grabber for the next schedule-fetch validation.
- Wrote normalized sample JSON skeletons for app/API design.

## Results

| Country | Active channels | Channels with guide mappings | Best source candidates |
| --- | ---: | ---: | --- |
| FR | 543 | 297 | tv.sfr.fr (205), chaines-tv.orange.fr (172), tv-programme.telecablesat.fr (150), canalplus.com (131) |
| ES | 645 | 167 | orangetv.orange.es (117), programacion-tv.elpais.com (63), gatotv.com (49), plex.tv (29) |
| CA | 1001 | 318 | i.mjh.nz (211), tvhebdo.com (144), tvpassport.com (124), ontvtonight.com (115) |

## Generated files

- `data/sources/iptv-org/spike-summary.json`
- `data/sources/iptv-org/channels-FR.json`
- `data/sources/iptv-org/channels-ES.json`
- `data/sources/iptv-org/channels-CA.json`
- `data/sources/iptv-org/guide-mappings-FR.json`
- `data/sources/iptv-org/guide-mappings-ES.json`
- `data/sources/iptv-org/guide-mappings-CA.json`
- `data/sources/iptv-org/custom-FR-tv.sfr.fr.channels.xml`
- `data/sources/iptv-org/custom-ES-orangetv.orange.es.channels.xml`
- `data/sources/iptv-org/custom-CA-tvhebdo.com.channels.xml`
- `data/normalized/sample-FR.json`
- `data/normalized/sample-ES.json`
- `data/normalized/sample-CA.json`

## What worked

- Public APIs are reachable and have substantial metadata coverage for all three MVP countries.
- France and Canada have strong guide mappings; Spain has fewer but still enough for an MVP spike.
- Upstream site channel XML files are available and can be used to build limited custom channel lists for schedule-grabber validation.

## Schedule-grabber validation

After generating the custom channel XML files, I cloned the upstream `iptv-org/epg` grabber into `.cache/epg` and ran limited 1-day grabs for the best candidate sources:

- France: `tv.sfr.fr`
- Spain: `programacion-tv.elpais.com` plus `orangetv.orange.es`
- Canada: `tvpassport.com` plus `tvhebdo.com`

Normalized current-program samples were written to:

- `data/normalized/current-sample-FR.json`
- `data/normalized/current-sample-ES.json`
- `data/normalized/current-sample-CA.json`
- `data/normalized/current-sample-summary.json`

Current-program coverage at run time:

| Country | Channels in normalized sample | Channels with programs | Channels with current program |
| --- | ---: | ---: | ---: |
| FR | 12 | 12 | 12 |
| ES | 22 | 18 | 18 |
| CA | 21 | 20 | 11 |

## What did not work yet

- The public iptv-org API gives guide mappings but not ready-to-use current-program data; we need the `iptv-org/epg` grabber or equivalent provider adapters.
- Stable country-level XMLTV files were not found at simple `iptv-org.github.io/epg/guides/<country>.xml` URLs.
- Orange Spain had one transient socket hangup during the grab, though it still produced useful data.

## Surprises

- Spain's strongest Orange source has many blank `xmltv_id` values in the source channel XML, so matching may require name/site-id based mapping.
- Canada has the broadest channel count and multiple strong sources, but timezone and regional feed handling will likely be the trickiest.
- Combining two sources per country is useful: Spain and Canada both improved materially when a second source was added.

## Verdict: VALIDATED

iptv-org is validated as the first provider path for the MVP spike. It provides enough metadata, source mappings, and actual schedule data to produce current-program rows for at least 10 channels in France, Spain, and Canada.

This is not production-ready yet: the real build should wrap the upstream grabber or reimplement provider-specific fetchers behind our own `Provider` interface, then store normalized results in SQLite.

## Recommendation for the real build

- Keep `iptv_org` as the first provider adapter.
- Use SQLite for normalized app storage.
- Start the app with a curated channel subset per country, backed by the validated sources above.
- Build ingestion as a script/worker that can run the selected source grabs, parse XMLTV output, and upsert current/future programs.
- Add source health tracking because provider requests can partially fail.
