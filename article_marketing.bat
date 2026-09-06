@echo off
setlocal enabledelayedexpansion
title WorkHive Article Marketing

:: ============================================================
:: WorkHive Article Marketing - one-click launcher
::   You type a topic, drop in a photo, and this produces:
::     - a branded share card (your photo + headline + workhiveph.com)
::     - a Facebook caption that leads with the facts
::     - and, when the topic genuinely fits, a real /learn article
::
:: Same shape as video_marketing.bat, including the Z: mapping:
:: the & in the folder name breaks cmd.exe without it.
:: ============================================================

set "PROJ=c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"
subst Z: "%PROJ%" >nul 2>&1
Z:
cd \

echo.
echo ============================================================
echo   WorkHive Article Marketing
echo ============================================================
echo.
echo   1. One topic now
echo   2. Run the whole queue  (.tmp\topic_queue)
echo   3. Open the queue folder so I can drop topics + photos in
echo   4. Open the last results
echo.
set "MODE="
set /p MODE="   Pick 1-4 (or just press Enter for 1): "
if "%MODE%"=="" set MODE=1

if "%MODE%"=="3" (
    if not exist "Z:\.tmp\topic_queue" mkdir "Z:\.tmp\topic_queue"
    echo.
    echo   Drop a .txt and a matching photo with the SAME name, e.g.
    echo     01_power-rates.txt   ^<- line 1 is the topic, the rest are your facts
    echo     01_power-rates.jpg   ^<- your photo
    start "" "Z:\.tmp\topic_queue"
    goto :done
)

if "%MODE%"=="4" (
    if not exist "Z:\.tmp\topic_posts" mkdir "Z:\.tmp\topic_posts"
    start "" "Z:\.tmp\topic_posts"
    goto :done
)

if "%MODE%"=="2" (
    echo.
    echo   Running the queue...
    echo.
    python tools\topic_post.py --batch
    goto :results
)

:: ---- single topic -------------------------------------------------------
echo.
set "TOPIC="
set /p TOPIC="   Topic (the headline, in your words): "
if "%TOPIC%"=="" (
    echo   No topic given, nothing to do.
    goto :done
)

echo.
echo   Paste the FACTS you saw, on one line. These matter: any number in the
echo   post that is NOT traceable to what you type here gets flagged as
echo   invented, because the AI will happily make figures up.
set "NOTES="
set /p NOTES="   Facts: "

echo.
echo   Photo (drag the file into this window, then press Enter).
echo   Leave blank to skip the card.
set "PHOTO="
set /p PHOTO="   Photo: "
:: strip surrounding quotes that drag-and-drop adds
set PHOTO=%PHOTO:"=%

echo.
set "WRITE="
set /p WRITE="   Also publish a /learn article if the topic fits? (y/N): "

set "ARGS="
if not "%PHOTO%"=="" set ARGS=!ARGS! --photo "%PHOTO%"
if /i "%WRITE%"=="y" set ARGS=!ARGS! --apply

echo.
echo   Working. The AI drafting takes about 20 seconds.
echo.
python tools\topic_post.py "%TOPIC%" --notes "%NOTES%" !ARGS!

:results
echo.
echo ============================================================
echo   Done. Read the caption before you post it.
echo.
echo   Anything listed as "figures not traceable" is invented:
echo   verify it or delete it. Everything else has been checked.
echo ============================================================
echo.
set "OPENIT="
set /p OPENIT="   Open the results folder? (Y/n): "
if /i not "%OPENIT%"=="n" start "" "Z:\.tmp\topic_posts"

:done
echo.
pause
endlocal
