#!/usr/bin/env bash
set -euo pipefail

# NOTE (option B history cleanup): guide snapshots are generated, not committed.
# Cloudflare dashboard auto-builds from git must stay OFF and deploys go out
# via `wrangler deploy` from the refresh workflows, which build the full
# web/data tree in CI. This script is for UHF-local work: it aborts rather
# than ship a site with an empty guide when snapshots are absent.
if [[ ! -f web/data/countries.json || ! -f web/data/US.json ]]; then
  echo "error: web/data guide snapshots missing; deploy via the 'Refresh EPG data' workflow (wrangler deploy), not a git build." >&2
  exit 1
fi

EPG_COMMIT=b11f0bb1256f05211aae53143f4f86428557cf07

if [[ ! -d .cache/epg/.git ]]; then
  git init .cache/epg
  git -C .cache/epg remote add origin https://github.com/iptv-org/epg.git
fi
git -C .cache/epg fetch --depth 1 origin "$EPG_COMMIT"
git -C .cache/epg checkout --detach --force "$EPG_COMMIT"
git -C .cache/epg clean -fdx
npm ci --prefix .cache/epg
python3 scripts/refresh_uhf_epg.py
python3 scripts/build_editor_picks_html.py
python3 scripts/build_series_report.py --render-only
