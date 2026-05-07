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
echo  [1/4] Drive Z: mounted

:: Start local Supabase (minimised -- already running is fine)
start "Supabase Local" /min cmd /k "cd /d Z:\ && npx supabase start && echo Supabase ready"
echo  [2/4] Supabase starting...

:: Wait briefly for Supabase to initialise before Edge Functions need it
timeout /t 6 /nobreak >nul

:: Start Edge Functions server (minimised)
start "Edge Functions" /min cmd /k "cd /d Z:\ && npx supabase functions serve"
echo  [3/4] Edge Functions starting...

:: Start the seeder Flask app (minimised)
start "WorkHive Seeder" /min cmd /k "cd /d Z:\test-data-seeder && venv\Scripts\python.exe app.py"
echo  [4/4] Seeder starting...

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
echo.
timeout /t 3 /nobreak >nul
exit
