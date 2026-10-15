@echo off
rem Creates two Windows Task Scheduler jobs: every day at 08:00 and 18:00.
rem The computer must be on (and you logged in) at those times.
set RUNNER=%~dp0run.bat
schtasks /Create /F /SC DAILY /ST 08:00 /TN "RealEstateAlerts-Morning" /TR "\"%RUNNER%\" run"
schtasks /Create /F /SC DAILY /ST 18:00 /TN "RealEstateAlerts-Evening" /TR "\"%RUNNER%\" run"
echo.
echo Scheduled. To remove:  schtasks /Delete /TN RealEstateAlerts-Morning /F  (and -Evening)
pause
