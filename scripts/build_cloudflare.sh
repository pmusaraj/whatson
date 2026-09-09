#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d .cache/epg/.git ]]; then
  git clone --depth 1 https://github.com/iptv-org/epg.git .cache/epg
fi
npm install --prefix .cache/epg
python3 scripts/refresh_uhf_epg.py
