# WorkHive MCP stack verifier.
# Probes every component end-to-end. Read-only. Safe to re-run.
#
#   .\infra\mcp\verify-mcp.ps1

$ErrorActionPreference = "Continue"
$script:pass = 0
$script:fail = 0

function Check {
    param([string]$Name, [scriptblock]$Test)
    Write-Host -NoNewline ("  {0,-40} " -f $Name)
    try {
        $result = & $Test
        if ($result) {
            Write-Host "PASS" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "FAIL" -ForegroundColor Red
            $script:fail++
        }
    } catch {
        Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host ""
Write-Host "=== WorkHive MCP stack verification ===" -ForegroundColor Cyan
Write-Host ""

# 1. Docker daemon
Write-Host "[1] Docker"
Check "docker daemon reachable" { (docker version --format '{{.Server.Version}}' 2>$null) -ne $null }

# 2. Supabase local
Write-Host ""
Write-Host "[2] Supabase local (prereq for Postgres MCP)"
Check "supabase_db_workhive running" {
    (docker ps --filter "name=supabase_db_workhive" --format "{{.Names}}") -eq "supabase_db_workhive"
}
Check "grafana_reader role exists" {
    $out = docker exec supabase_db_workhive psql -U postgres -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='grafana_reader'" 2>$null
    $out -eq "1"
}
Check "Supabase MCP endpoint responds" {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:54321/mcp" -Method GET -TimeoutSec 5 -ErrorAction Stop
        $true
    } catch {
        # 405 (method not allowed) is expected from MCP servers on GET — that's a PASS
        $_.Exception.Response.StatusCode.value__ -in @(200, 400, 405, 406)
    }
}

# 3. Grafana
Write-Host ""
Write-Host "[3] Grafana"
Check "workhive_grafana container running" {
    (docker ps --filter "name=workhive_grafana" --format "{{.Names}}") -eq "workhive_grafana"
}
Check "Grafana UI responds at :3001" {
    try {
        (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3001/api/health" -TimeoutSec 5).StatusCode -eq 200
    } catch { $false }
}
Check "Supabase data source provisioned" {
    try {
        # Read admin pw from .env.mcp
        $envFile = Get-Content "infra/mcp/.env.mcp" | Where-Object { $_ -match "^GRAFANA_ADMIN_PASSWORD=" }
        if (-not $envFile) { return $false }
        $pw = ($envFile -split "=", 2)[1]
        $cred = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("admin:$pw"))
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3001/api/datasources" `
             -Headers @{ Authorization = "Basic $cred" } -TimeoutSec 5
        $r.Content -match "Supabase Local"
    } catch { $false }
}

# 4. GlitchTip
Write-Host ""
Write-Host "[4] GlitchTip (self-hosted Sentry-compatible)"
Check "workhive_glitchtip_web running" {
    (docker ps --filter "name=workhive_glitchtip_web" --format "{{.Names}}") -eq "workhive_glitchtip_web"
}
Check "workhive_glitchtip_worker running" {
    (docker ps --filter "name=workhive_glitchtip_worker" --format "{{.Names}}") -eq "workhive_glitchtip_worker"
}
Check "GlitchTip UI responds at :8000" {
    try {
        (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/" -TimeoutSec 10).StatusCode -in @(200, 302)
    } catch { $false }
}

# 5. MCP servers (only checks if installed via Docker MCP Toolkit)
# Docker MCP Toolkit publishes images under the `mcp/` namespace.
Write-Host ""
Write-Host "[5] Docker MCP Toolkit servers (installed via Docker Desktop GUI)"
$mcpServers = @(
    @{ Name = "obsidian";   Patterns = @("mcp/obsidian", "modelcontextprotocol/obsidian") },
    @{ Name = "postgres";   Patterns = @("mcp/postgres", "modelcontextprotocol/postgres") },
    @{ Name = "grafana";    Patterns = @("mcp/grafana", "grafana/mcp", "grafana/grafana-mcp") },
    @{ Name = "playwright"; Patterns = @("mcp/playwright", "mcr.microsoft.com/playwright") },
    @{ Name = "github";     Patterns = @("mcp/github", "ghcr.io/github/github-mcp-server") },
    @{ Name = "sentry";     Patterns = @("mcp/sentry", "ghcr.io/getsentry/sentry-mcp") }
)
foreach ($s in $mcpServers) {
    Check ("MCP server installed: " + $s.Name) {
        $found = $false
        foreach ($p in $s.Patterns) {
            $img = docker images --format "{{.Repository}}" 2>$null | Where-Object { $_ -eq $p -or $_ -like "$p*" }
            if ($img) { $found = $true; break }
        }
        $found
    }
}

# Summary
Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ("Pass: {0}   Fail: {1}" -f $script:pass, $script:fail)
if ($script:fail -eq 0) {
    Write-Host "All checks green." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some checks failed. See above." -ForegroundColor Yellow
    exit 1
}
