@echo off
title WorkHive Platform Guardian
cd /d "C:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"
echo.
echo   WorkHive Platform Guardian starting...
echo   Opening http://localhost:8080
echo.
start "" http://localhost:8080
py guardian_server.py
pause
