#!/usr/bin/env bash
# Run a scan (extra options are passed through, e.g. --headed, --dry-run, --debug).
cd "$(dirname "$0")/.."
exec .venv/bin/python -m alerts "$@"
