#!/bin/sh
# Local backup for election night: update the live count every 10 minutes and push it.
# Run from the repo root: sh src/election_night.sh
while true; do
  python3 src/nowcast.py live && python3 src/build_site.py
  git add outputs docs
  git diff --cached --quiet || { git commit -qm "Live count update ($(date -u +%H:%M) UTC)"; git pull -q --rebase; git push -q; }
  sleep 600
done
