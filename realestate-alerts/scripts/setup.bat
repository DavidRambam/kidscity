@echo off
rem One-time setup on Windows. Needs Python 3.10+ from https://www.python.org (tick "Add python.exe to PATH").
cd /d "%~dp0\.."
echo Installing... (a few minutes)
python -m venv .venv || goto :error
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt || goto :error
.venv\Scripts\python -m playwright install chromium || goto :error
if not exist .env copy .env.example .env >nul
echo.
echo Installed. Now enter where the alerts should go:
.venv\Scripts\python -m alerts setup
echo.
echo Next: double-click scripts\first_scan.bat
pause
exit /b 0
:error
echo Setup failed - see the message above.
pause
exit /b 1
