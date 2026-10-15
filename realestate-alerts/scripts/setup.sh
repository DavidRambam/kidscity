#!/usr/bin/env bash
# One-time setup on macOS / Linux.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
[ -f .env ] || cp .env.example .env
echo
echo "Done. Next: fill in .env, then run:  scripts/run.sh test-notify"
