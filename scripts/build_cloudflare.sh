#!/usr/bin/env bash
set -euo pipefail

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
