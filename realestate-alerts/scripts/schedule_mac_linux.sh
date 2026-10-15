#!/usr/bin/env bash
# Adds two daily runs (08:00 and 18:00) to your crontab. Run again to update; it won't duplicate.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DIR/logs"
LINE="0 8,18 * * * cd \"$DIR\" && .venv/bin/python -m alerts run >> logs/cron.log 2>&1"
{ crontab -l 2>/dev/null | grep -v "python -m alerts run" || true; echo "$LINE"; } | crontab -
echo "Scheduled: $LINE"
