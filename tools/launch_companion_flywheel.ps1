# AI Companion Flywheel Launcher — 100 Turns
# ============================================
# Orchestrates 100-turn self-improvement loop for Zaniah & Hezekiah

param(
    [int]$TurnsToRun = 100,
    [int]$RestBetweenTurns = 5,
    [string]$StartFrom = "1"
)

$ROOT = Split-Path -Parent $PSScriptRoot
$TURNS = @()
$PAGES = @("alert-hub.html", "analytics.html", "logbook.html", "skillmatrix.html")
$SCENARIOS = @("logbook_entry", "asset_query", "report_intent", "safety_check", "energy_anomaly")
$HIVES = @("manila", "baguio", "cebu")

Write-Host ""
Write-Host "=================================================================================="
Write-Host "  AI Companion Flywheel — 100-Turn Self-Improvement Loop"
Write-Host "  Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "=================================================================================="
Write-Host ""

# Create observations directory
$ObsDir = "$ROOT\.tmp"
if (-not (Test-Path $ObsDir)) {
    New-Item -ItemType Directory -Path $ObsDir -Force | Out-Null
}

# Run 100 turns
$TurnsArray = @()
for ($i = 1; $i -le $TurnsToRun; $i++) {
    $PageIdx = ($i - 1) % $PAGES.Count
    $ScenarioIdx = ($i - 1) % $SCENARIOS.Count
    $HiveIdx = ($i - 1) % $HIVES.Count

    $Page = $PAGES[$PageIdx]
    $Scenario = $SCENARIOS[$ScenarioIdx]
    $Hive = $HIVES[$HiveIdx]

    $TurnsArray += @{
        Turn = $i
        Page = $Page
        Scenario = $Scenario
        Hive = $Hive
    }
}

# Launch turns in background via Python orchestrator
$PythonScript = "$ROOT\tools\run_companion_flywheel_loop.py"

if (Test-Path $PythonScript) {
    Write-Host "Launching 100-turn flywheel loop via Python orchestrator..."
    Write-Host "Command: python $PythonScript"
    Write-Host ""

    # Run in background
    $Job = Start-Job -ScriptBlock {
        param($Script, $Turns, $TurnsToRun)
        Set-Location $using:ROOT
        & python $Script
    } -ArgumentList $PythonScript, $TurnsArray, $TurnsToRun

    Write-Host "✓ Flywheel loop launched (Job ID: $($Job.Id))"
    Write-Host "  Monitoring in background... 100 turns × ~1min each ≈ 100 minutes"
    Write-Host ""
    Write-Host "Track progress with: Get-Job -Id $($Job.Id) | Receive-Job -Keep -Wait"
    Write-Host ""
    Write-Host "Reports will appear in:"
    Write-Host "  - $ROOT\companion_flywheel_report_*.md"
    Write-Host "  - $ROOT\.tmp\companion_observations_turn_*.jsonl"
    Write-Host ""

    exit 0
} else {
    Write-Host "ERROR: Python orchestrator not found at $PythonScript"
    exit 1
}
