#!/usr/bin/env bash
set -euo pipefail

PORT=8000
echo "Starting localtunnel on port ${PORT}..." >&2
echo "After it prints 'your url is: https://xyz.loca.lt' run:" >&2
echo "  export STRAVA_WEBHOOK_URL=https://xyz.loca.lt/strava/webhook" >&2
echo "(substitute the printed host)." >&2
echo "Optionally add to your shell or .envrc manually." >&2

lt --port "${PORT}" --print-requests
