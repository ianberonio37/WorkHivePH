@echo off
title WorkHive — NotebookLM Campaign

:: Map project root to Z: — the & in the folder name breaks cmd.exe without this.
subst Z: "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st" >nul 2>&1
Z:
cd \

if "%~1"=="" goto :help

python tools\notebooklm_campaign.py %*
goto :end

:help
echo.
echo NotebookLM long-form lane — usage
echo ==================================
echo.
echo   notebooklm.bat doctor
echo       Diagnose library + session readiness.
echo.
echo   notebooklm.bat prepare ^<idea_id^>
echo       Build the source bundle (no NotebookLM calls).
echo.
echo   notebooklm.bat run ^<idea_id^> [--profile marketing^|sales^|enablement^|minimal] [--lang en^|tl] [--only kind,kind]
echo       Full campaign for an idea.
echo.
echo   notebooklm.bat run-one ^<idea_id^> ^<audio^|video^|slides^|infographic^|mindmap^|blog^|briefing^|study^> [--lang en^|tl]
echo       Generate a single artifact.
echo.
echo   notebooklm.bat status ^<idea_id^>
echo       Show generated artifacts for one idea.
echo.
echo   notebooklm.bat list
echo       List every idea with a NotebookLM workspace.
echo.
echo Examples:
echo   notebooklm.bat run idea_007
echo   notebooklm.bat run idea_007 --profile sales
echo   notebooklm.bat run-one idea_007 audio --lang tl
echo.
pause

:end
