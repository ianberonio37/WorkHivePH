$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .\venv)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    pip install -r requirements.txt
    Write-Host "Installing Playwright Chromium browser (~150 MB, one-time)..." -ForegroundColor Cyan
    python -m playwright install chromium
} else {
    .\venv\Scripts\Activate.ps1
    # Make sure playwright + browser are installed (idempotent)
    $hasPlaywright = pip list 2>$null | Select-String -Pattern "^playwright " -Quiet
    if (-not $hasPlaywright) {
        Write-Host "Installing Playwright (new dependency)..." -ForegroundColor Cyan
        pip install -r requirements.txt
        python -m playwright install chromium
    }
}

Write-Host ""
Write-Host "Starting Flask seeder..." -ForegroundColor Green
Write-Host "Open http://127.0.0.1:5000 in your browser" -ForegroundColor Yellow
Write-Host "Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

python app.py
