@echo off
title WorkHive Tester Launcher
color 0A

echo.
echo  ===========================================
echo   WorkHive Tester -- Auto Launch
echo  ===========================================
echo.

:: Mount Z: drive to avoid ampersand in path
subst Z: "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st" 2>nul
echo  [1/5] Drive Z: mounted

:: Start local Supabase (minimised -- already running is fine)
start "Supabase Local" /min cmd /k "cd /d Z:\ && npx supabase start && echo Supabase ready"
echo  [2/5] Supabase starting...

:: Wait briefly for Supabase to initialise before Edge Functions need it
timeout /t 6 /nobreak >nul

:: Start Edge Functions server (minimised)
start "Edge Functions" /min cmd /k "cd /d Z:\ && npx supabase functions serve"
echo  [3/5] Edge Functions starting...

:: Start Python Analytics API (FastAPI on :8000) -- required for analytics.html
:: Skip if port 8000 is already listening (don't spawn a duplicate that crashes on bind).
netstat -ano | findstr "LISTENING" | findstr ":8000 " >nul 2>&1
if errorlevel 1 (
    start "Python Analytics API" /min cmd /k "cd /d Z:\python-api && C:\wh-venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    echo  [4/5] Python Analytics API starting...
) else (
    echo  [4/5] Python Analytics API already running on :8000 -- skipped
)

:: Start the seeder Flask app (minimised)
start "WorkHive Seeder" /min cmd /k "cd /d Z:\test-data-seeder && venv\Scripts\python.exe app.py"
echo  [5/5] Seeder starting...

:: Wait for Flask to bind to port 5000
timeout /t 4 /nobreak >nul

:: Open the seeder dashboard in the default browser
start http://127.0.0.1:5000

echo.
echo  Done! Browser opening...
echo  All services running in minimised windows.
echo  Close those windows to stop the services.
echo.
echo  Service URLs:
echo    Seeder dashboard : http://127.0.0.1:5000
echo    Supabase Studio  : http://127.0.0.1:54323
echo    Edge Functions   : http://127.0.0.1:54321/functions/v1
echo    Python Analytics : http://127.0.0.1:8000
echo.
timeout /t 3 /nobreak >nul
exit
