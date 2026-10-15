@echo off
rem One-time setup on Windows. Needs Python 3.10+ from https://www.python.org (tick "Add to PATH").
cd /d "%~dp0\.."
python -m venv .venv || goto :error
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt || goto :error
.venv\Scripts\python -m playwright install chromium || goto :error
if not exist .env copy .env.example .env
echo.
echo Done. Next: open .env in Notepad, fill it in, then run:  scripts\run.bat test-notify
pause
exit /b 0
:error
echo Setup failed - see the message above.
pause
exit /b 1
