@echo off
setlocal
title WorkHive Video Marketing

:: ============================================================
:: WorkHive Video Marketing — one-click launcher
::   1. Map project root to Z: (the & in the path breaks cmd.exe)
::   2. If Flask is already running on :5001, just open the browser
::   3. Otherwise: verify NotebookLM session, re-login if needed,
::      then start Flask and open the browser
:: ============================================================

set "PROJ=c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"

:: Map project root to Z: -- the & in the folder name breaks cmd.exe without this
subst Z: "%PROJ%" >nul 2>&1

:: ── Already running? Just pop the browser. ──────────────────
netstat -ano | findstr ":5001 " | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
    echo Dashboard already running -- opening browser...
    start "" "http://localhost:5001"
    exit /b
)

:: ── NotebookLM session check ───────────────────────────────
:: Exits: 0=OK, 1=missing, 2=expired, 3=lib not installed
echo.
echo Checking NotebookLM session...
pushd "%PROJ%" >nul 2>&1
python tools\notebooklm_session_check.py
set NLM_STATUS=%errorlevel%
popd >nul 2>&1

if %NLM_STATUS%==0 (
    echo  NotebookLM session is valid -- skipping login.
    goto :start_flask
)

if %NLM_STATUS%==3 (
    echo  WARNING: notebooklm-py library not installed.
    echo  NotebookLM features will be unavailable, but the dashboard will still work.
    echo  To install: run notebooklm_setup.bat
    goto :start_flask
)

:: Session missing (1) or expired (2) -- launch interactive login
echo.
echo ============================================================
if %NLM_STATUS%==1 (
    echo  NotebookLM: no saved session found.
) else (
    echo  NotebookLM: session expired -- re-authentication required.
)
echo  Launching login flow now...
echo ============================================================
echo.
echo  In the next window:
echo    1. A Chromium browser will open NotebookLM
echo    2. Sign in with your Google account
echo    3. After NotebookLM loads, return to the login window
echo    4. Press ENTER to save the session
echo.
echo  After login completes, the dashboard will start automatically.
echo.
pause

:: Run login synchronously (same console) and wait for it to finish.
:: IMPORTANT: do NOT use `call notebooklm login` here. There's a local
:: `notebooklm.bat` in this folder that intercepts the call and routes it
:: to `notebooklm_campaign.py login`, which doesn't have a `login` command
:: (argparse error: "invalid choice: 'login'"). Bypass the shim by
:: calling the Python module directly — `python -m notebooklm login`
:: imports the lib's CLI module and runs it with no PATH lookup.
pushd "%PROJ%" >nul 2>&1
python -m notebooklm login
popd >nul 2>&1

:: Verify it actually worked
pushd "%PROJ%" >nul 2>&1
python tools\notebooklm_session_check.py
set NLM_STATUS=%errorlevel%
popd >nul 2>&1

if not %NLM_STATUS%==0 (
    echo.
    echo  WARNING: NotebookLM session is still not valid after login.
    echo  Starting dashboard anyway -- NotebookLM features may not work.
    echo  You can retry by closing this and running video_marketing.bat again.
    echo.
    timeout /t 4 /nobreak >nul
)

:start_flask
:: Start Flask from the clean Z: drive
start "WorkHive Video Marketing (server)" cmd /k "Z: && cd \ && python video_marketing_app/app.py"

:: Wait for Flask to start, then open browser
echo.
echo Starting dashboard...
timeout /t 4 /nobreak >nul
start "" "http://localhost:5001"
echo Done. Dashboard is open in your browser.
endlocal
