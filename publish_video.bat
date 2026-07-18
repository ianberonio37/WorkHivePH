@echo off
setlocal enabledelayedexpansion
title WorkHive - Publish Video

:: ============================================================
:: WorkHive - Publish a produced video to your social accounts
::   1. Make sure social_accounts.env exists (paste-once setup)
::   2. List produced videos + show which accounts are armed
::   3. Pick an idea, pick dry-run or live, publish
:: The & in the folder path breaks cmd.exe, so map to Z: first.
:: ============================================================

set "PROJ=c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"
subst Z: "%PROJ%" >nul 2>&1

:: -- First-run social setup: the ONE file you paste your accounts into -------
if not exist "%PROJ%\social_accounts.env" (
    echo.
    echo ============================================================
    echo  FIRST-TIME SETUP -- your social media accounts
    echo ============================================================
    echo  Paste whatever account tokens you have into the file that is
    echo  about to open. Fill in what you have, LEAVE THE REST BLANK,
    echo  then SAVE and close it.
    echo.
    copy /Y "%PROJ%\social_accounts.env.example" "%PROJ%\social_accounts.env" >nul
    echo  Opening social_accounts.env in Notepad...
    start "" /wait notepad "%PROJ%\social_accounts.env"
    echo.
)

:: Run everything from the clean Z: drive (no & in the path).
Z:
cd \

echo.
echo ============================================================
echo  PRODUCED VIDEOS
echo ============================================================
python tools\social_publisher.py --list
echo.
echo ============================================================
echo  YOUR ARMED ACCOUNTS
echo ============================================================
python tools\social_publisher.py --check
echo.

set "IDEA="
set /p IDEA="Which idea id to publish (e.g. idea_020), or blank to cancel: "
if "%IDEA%"=="" goto :done

echo.
echo  How do you want to publish "%IDEA%"?
echo    [1] DRY-RUN  (safe preview -- shows what WOULD post, nothing goes live)
echo    [2] LIVE     (actually post to your AUTO accounts; opens upload pages for the rest)
set "MODE=1"
set /p MODE="Choose 1 or 2 [default 1]: "

echo.
if "%MODE%"=="2" (
    echo  Publishing %IDEA% LIVE...
    python tools\social_publisher.py --idea %IDEA% --live
) else (
    echo  Dry-run for %IDEA%...
    python tools\social_publisher.py --idea %IDEA%
)

:done
C:
echo.
echo ============================================================
echo  Done. (Re-run this anytime to publish another video.)
echo ============================================================
pause
endlocal
