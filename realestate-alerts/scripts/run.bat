@echo off
rem Run a scan (extra options are passed through, e.g. --headed, --dry-run, --debug).
cd /d "%~dp0\.."
.venv\Scripts\python -m alerts %*
