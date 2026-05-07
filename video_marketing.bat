@echo off
title WorkHive Video Marketing

:: Map project root to Z: -- the & in the folder name breaks cmd.exe without this
subst Z: "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st" >nul 2>&1

:: If Flask is already running, just open the browser
netstat -ano | findstr ":5001 " | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
    echo Already running -- opening browser...
    start "" "http://localhost:5001"
    exit /b
)

:: Start Flask from the clean Z: drive
start "WorkHive Video Marketing (server)" cmd /k "Z: && cd \ && python video_marketing_app/app.py"

:: Wait for Flask to start, then open browser
echo Starting WorkHive Video Marketing...
timeout /t 4 /nobreak >nul
start "" "http://localhost:5001"
echo Done. Dashboard is open in your browser.
