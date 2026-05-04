# What's On TV

Spike repo for a TV now-playing app.

MVP target countries:

- France (`FR`)
- Spain (`ES`)
- Canada (`CA`)
- United States (`US`)
- United Kingdom (`UK`)
- Italy (`IT`)
- Germany (`DE`)
- Turkiye (`TR`)
- Portugal (`PT`)
- Mexico (`MX`)
- Brazil (`BR`)

The first milestone is data validation: prove that we can get channel metadata and current/near-term program data for at least 10 channels per country before building the full web UI.

## First spike

Run:

```bash
python3 scripts/iptv_org_spike.py
```

This downloads iptv-org metadata, filters it to the MVP countries, generates summary files, creates small custom XMLTV channel files for candidate sources, and writes a spike report.

Outputs:

- `data/sources/iptv-org/countries.json`
- `data/sources/iptv-org/channels-*.json`
- `data/sources/iptv-org/guide-mappings-*.json`
- `data/sources/iptv-org/spike-summary.json`
- `data/sources/iptv-org/custom-*.channels.xml`
- `spikes/001-iptv-org-data-source/README.md`

## Schedule validation

The first spike also validated actual schedule grabs using the upstream `iptv-org/epg` grabber. To reproduce:

```bash
git clone --depth 1 https://github.com/iptv-org/epg.git .cache/epg
npm install --prefix .cache/epg

npm run grab --prefix .cache/epg --- \
  --channels=$(pwd)/data/sources/iptv-org/custom-FR-tv.sfr.fr.channels.xml \
  --output=$(pwd)/data/normalized/guide-FR-tv.sfr.fr.xml \
  --days=1 --maxConnections=2 --timeout=20000

npm run grab --prefix .cache/epg --- \
  --channels=$(pwd)/data/sources/iptv-org/custom-ES-programacion-tv.elpais.com.channels.xml \
  --output=$(pwd)/data/normalized/guide-ES-programacion-tv.elpais.com.xml \
  --days=1 --maxConnections=2 --timeout=20000

npm run grab --prefix .cache/epg --- \
  --channels=$(pwd)/data/sources/iptv-org/custom-ES-orangetv.orange.es.channels.xml \
  --output=$(pwd)/data/normalized/guide-ES-orangetv.orange.es.xml \
  --days=1 --maxConnections=2 --timeout=20000

npm run grab --prefix .cache/epg --- \
  --channels=$(pwd)/data/sources/iptv-org/custom-CA-tvpassport.com.channels.xml \
  --output=$(pwd)/data/normalized/guide-CA-tvpassport.com.xml \
  --days=1 --maxConnections=2 --timeout=20000

npm run grab --prefix .cache/epg --- \
  --channels=$(pwd)/data/sources/iptv-org/custom-CA-tvhebdo.com.channels.xml \
  --output=$(pwd)/data/normalized/guide-CA-tvhebdo.com.xml \
  --days=1 --maxConnections=2 --timeout=20000

python3 scripts/normalize_guides.py
```

Latest validation result:

- France: 12 channels; 25 premium sports/pay-TV channels
- Spain: 18 channels; 21 premium sports/pay-TV channels
- Canada: 20 channels; 14 premium sports/pay-TV channels
- United States: 14 channels; 13 premium sports/pay-TV channels
- United Kingdom: 19 channels; 9 premium sports/pay-TV channels
- Italy: 10 channels; 8 premium sports/pay-TV channels
- Germany: 12 channels; 12 premium sports/pay-TV channels
- Turkiye: 12 channels; 6 premium sports/pay-TV channels
- Portugal: 21 channels; 17 premium sports/pay-TV channels
- Mexico: 10 channels; 10 premium sports/pay-TV channels
- Brazil: 12 channels; 9 premium sports/pay-TV channels

## Run the web prototype

Build browser-friendly JSON from the validated XMLTV snapshots:

```bash
python3 scripts/build_web_data.py
```

Serve the static app:

```bash
cd web
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

The prototype shows France, Spain, Canada, United States, United Kingdom, Italy, Germany, Turkiye, Portugal, Mexico, and Brazil channels grouped by country. Users can select channels and the guide renders those selected channels as aligned schedule columns. The browser computes the visible current/next-three-hours window from a longer generated schedule, shows a current-time line across every selected channel column, and refreshes that line every minute. Sidebar rows show only channel names; selected programme cells show genre/type tags when the source provides enough metadata, with descriptions collapsed by default. Selections are saved in browser `localStorage`.

The premium channel view focuses on pay-TV / premium guide sources:

- France: Canal+, Canal+ Sport/Foot/Premier League/Sport 360, Eurosport, RMC Sport, Infosport+
- Spain: Movistar Deportes, LaLiga, and Liga de Campeones channels
- Canada: TSN, Sportsnet, RDS, TVA Sports
- United States: ESPN, Fox Sports, NFL/MLB/NBA networks, Golf Channel, Tennis Channel, TNT/TBS
- United Kingdom: Sky Sports, TNT Sports, Premier Sports
- Italy: Sky Sport, DAZN, Eurosport, Rai Sport, Sportitalia
- Germany: Sky Sport, DAZN, Eurosport, Sportdigital
- Turkiye: S Sport, TRT Spor, Eurosport; Digiturk/beIN is mapped but currently returns 403 from the grabber
- Portugal: Sport TV, DAZN, Eurosport, Benfica TV, Sporting TV
- Mexico: TUDN, Sky Sports, Fox Sports, ESPN, Claro Sports mappings where schedules are available
- Brazil: SporTV, ESPN, BandSports, Premiere Clubes, Fox Sports via `mi.tv`

Current premium-channel counts:

- France: 25
- Spain: 21
- Canada: 14
- United States: 13
- United Kingdom: 9
- Italy: 8
- Germany: 12
- Turkiye: 6
- Portugal: 17
- Mexico: 10
- Brazil: 9

## Tests

```bash
python3 -m unittest discover -s tests -v
```
