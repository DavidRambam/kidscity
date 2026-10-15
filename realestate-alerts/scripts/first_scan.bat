@echo off
rem First scan with the browser window visible. If Yad2 or Madlan asks you to
rem prove you're human ("press and hold"), do it in that window - it's remembered.
cd /d "%~dp0\.."
.venv\Scripts\python -m alerts run --headed
echo.
echo Done. The full list is in reports\latest.html
start "" "reports\latest.html"
echo Next: double-click scripts\schedule_windows.bat to run it every day at 08:00 and 18:00.
pause
