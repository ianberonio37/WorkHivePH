@echo off
title WorkHive — NotebookLM Setup

:: Map project root to Z: — the & in the folder name breaks cmd.exe without this.
subst Z: "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st" >nul 2>&1
Z:
cd \

echo.
echo ============================================================
echo   WorkHive NotebookLM lane — one-time setup
echo ============================================================
echo.
echo Step 1/3: Installing notebooklm-py (unofficial Python SDK)...
python -m pip install --upgrade notebooklm-py
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed. Check your Python + internet connection.
    pause
    exit /b 1
)

echo.
echo Step 2/3: Installing Playwright Chromium (notebooklm-py uses it for auth)...
python -m playwright install chromium
if errorlevel 1 (
    echo.
    echo [WARN] Playwright install reported a problem — usually OK if Chromium was already installed.
)

echo.
echo Step 3/3: Verifying with `doctor`...
python tools\notebooklm_campaign.py doctor
echo.

echo ============================================================
echo   Next: run `python -m notebooklm_py login` to authenticate.
echo   The session lands in .tmp\notebooklm\_session\storage_state.json
echo ============================================================
pause
