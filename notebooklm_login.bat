@echo off
title WorkHive — NotebookLM Login

echo ============================================================
echo  WorkHive NotebookLM — Interactive Login
echo ============================================================
echo.
echo This will:
echo   1. Open a Chromium browser to NotebookLM
echo   2. You sign in with your Google account
echo   3. After NotebookLM loads, come back here and press ENTER
echo   4. The session is saved and this window closes
echo.
echo ============================================================
echo.

notebooklm login

echo.
echo ============================================================
if exist "%USERPROFILE%\.notebooklm\profiles\default\storage_state.json" (
    echo  Session saved successfully.
) else (
    echo  WARNING: Session file was NOT created. Try again.
)
echo ============================================================
echo.
pause
