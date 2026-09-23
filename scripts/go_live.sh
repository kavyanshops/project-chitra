#!/usr/bin/env bash
# Point the hosted Vercel page at a running CHITRA engine, then redeploy the same Vercel project.
#   scripts/go_live.sh https://xxxx.trycloudflare.com   -> page becomes live (uploads, live runs)
#   scripts/go_live.sh off                               -> back to static results
# The page falls back to static results by itself whenever the engine stops answering.
set -euo pipefail
cd "$(dirname "$0")/.."
url="${1:?usage: scripts/go_live.sh https://xxxx.trycloudflare.com | off}"
if [ "$url" = off ]; then
  rm -f site/live.json
else
  url="${url%/}"
  curl -sf --max-time 10 "$url/api/runs" >/dev/null || { echo "No CHITRA engine answering at $url/api/runs"; exit 1; }
  printf '{"api": "%s"}\n' "$url" > site/live.json
fi
npx vercel deploy site --prod --yes
