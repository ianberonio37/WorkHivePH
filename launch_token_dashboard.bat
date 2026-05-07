@echo off
title Claude Token Dashboard

:: Check if Flask is already running on port 5000
netstat -ano | findstr ":5000 " | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
    echo Flask already running — opening dashboard...
    timeout /t 1 /nobreak >nul
    start "" "http://localhost:5000/token-stats"
    exit /b
)

:: Start Flask in a new window
echo Starting Flask test-data-seeder...
start "WorkHive Tester" cmd /k "cd /d ""%~dp0test-data-seeder"" && python app.py"

:: Wait for Flask to be ready
echo Waiting for server to start...
timeout /t 4 /nobreak >nul

:: Open the dashboard
start "" "http://localhost:5000/token-stats"

echo Done. Dashboard should be open in your browser.
