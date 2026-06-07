@echo off
cd /d "%~dp0"
if not exist "logs" mkdir logs
echo Run app; errors go to logs\app.log
".venv\Scripts\python.exe" main.py 2>> logs\console.log
if errorlevel 1 (
    echo.
    echo Failed. See logs\app.log and logs\console.log
    type logs\app.log 2>nul
    pause
)
