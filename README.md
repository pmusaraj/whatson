# What's On TV

Spike repo for a TV now-playing app.

MVP target countries:

- France (`FR`)
- Spain (`ES`)
- Canada (`CA`)

The first milestone is data validation: prove that we can get channel metadata and current/near-term program data for at least 10 channels per country before building the full web UI.

## First spike

Run:

```bash
python3 scripts/iptv_org_spike.py
```

This downloads iptv-org metadata, filters it to the MVP countries, generates summary files, creates small custom XMLTV channel files for candidate sources, and writes a spike report.

Outputs:

- `data/sources/iptv-org/countries.json`
- `data/sources/iptv-org/channels-FR.json`
- `data/sources/iptv-org/channels-ES.json`
- `data/sources/iptv-org/channels-CA.json`
- `data/sources/iptv-org/guide-mappings-FR.json`
- `data/sources/iptv-org/guide-mappings-ES.json`
- `data/sources/iptv-org/guide-mappings-CA.json`
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

- France: 12 channels with programs, 12 with current program
- Spain: 18 channels with programs, 18 with current program
- Canada: 20 channels with programs, 11 with current program

## Tests

```bash
python3 -m unittest discover -s tests -v
```
