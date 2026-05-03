# WorkHive Tester: one-click startup script
# Sets up everything needed to run the test environment, then opens the dashboard.

$ErrorActionPreference = "Continue"

$ProjectRoot = "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"
$SeederPath  = Join-Path $ProjectRoot "test-data-seeder"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  WorkHive Tester: starting up" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Z: drive
if (-not (Test-Path "Z:\")) {
    Write-Host "[1/4] Setting up Z: drive..." -ForegroundColor Yellow
    cmd /c "subst Z: `"$ProjectRoot`""
    Start-Sleep -Milliseconds 500
} else {
    Write-Host "[1/4] Z: drive already set up." -ForegroundColor Green
}

Set-Location "Z:\test-data-seeder"

# 2. Docker check
Write-Host "[2/4] Checking Docker Desktop..." -ForegroundColor Yellow
$dockerRunning = $false
try {
    $null = docker ps 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
} catch {}

if (-not $dockerRunning) {
    Write-Host ""
    Write-Host "  Docker Desktop is not running." -ForegroundColor Red
    Write-Host "  Please open Docker Desktop from your Start menu, wait until" -ForegroundColor Red
    Write-Host "  the whale icon stops animating, then re-run this shortcut." -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}
Write-Host "      ok." -ForegroundColor Green

# 3. Supabase status
Write-Host "[3/4] Checking local Supabase..." -ForegroundColor Yellow
$supabaseRunning = $false
$status = supabase status 2>&1
if ($status -match "API URL") { $supabaseRunning = $true }

if (-not $supabaseRunning) {
    Write-Host "      not running. Starting it now (about 30 seconds)..." -ForegroundColor Yellow
    supabase start
} else {
    Write-Host "      already running." -ForegroundColor Green
}

# 4. Flask dashboard
Write-Host "[4/4] Preparing the seeder dashboard..." -ForegroundColor Yellow

if (-not (Test-Path .\venv)) {
    Write-Host "      First-time setup: creating Python environment..." -ForegroundColor Cyan
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Write-Host "      Installing Playwright browser (about 150 MB)..." -ForegroundColor Cyan
    python -m playwright install chromium
} else {
    .\venv\Scripts\Activate.ps1
    $hasPlaywright = pip list 2>$null | Select-String -Pattern "^playwright " -Quiet
    if (-not $hasPlaywright) {
        Write-Host "      Updating dependencies..." -ForegroundColor Cyan
        pip install -r requirements.txt
        python -m playwright install chromium
    }
}

# Open browser shortly after Flask boots
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://127.0.0.1:5000"
} | Out-Null

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  Ready! Browser will open in a moment." -ForegroundColor Green
Write-Host "  Dashboard: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "  Press Ctrl+C in this window to stop." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

python app.py
