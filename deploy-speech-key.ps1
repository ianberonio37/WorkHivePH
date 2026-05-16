# Azure Speech Key Rotation + Edge Function Redeploy
# Run this script and paste your new AZURE_SPEECH_KEY when prompted

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "Azure Speech Key Rotation + Supabase Deploy" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Prompt for the key
$speechKey = Read-Host "Paste your new AZURE_SPEECH_KEY"

if (-not $speechKey -or $speechKey.Length -lt 10) {
    Write-Host "ERROR: Invalid key (too short)" -ForegroundColor Red
    exit 1
}

Write-Host "Key received (length: $($speechKey.Length))" -ForegroundColor Green

# Map Z: drive to avoid & character issue
Write-Host "Mapping Z: drive..." -ForegroundColor Cyan
subst Z: "."

# Change to Z: drive
Z:

# Update Supabase secret
Write-Host "Updating Supabase secret..." -ForegroundColor Cyan
npx supabase secrets set AZURE_SPEECH_KEY=$speechKey

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Secret update failed" -ForegroundColor Red
    cd C:
    subst Z: /d
    exit 1
}

Write-Host "✓ Secret updated" -ForegroundColor Green

# Redeploy edge functions
Write-Host "Redeploying edge functions..." -ForegroundColor Cyan
.\deploy-functions.ps1

if ($LASTEXITCODE -eq 0) {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "✓ SUCCESS: Speech Key rotated + functions redeployed" -ForegroundColor Green
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
} else {
    Write-Host "ERROR: Redeploy failed" -ForegroundColor Red
    cd C:
    subst Z: /d
    exit 1
}

# Cleanup
Write-Host "Cleaning up..." -ForegroundColor Cyan
cd C:
subst Z: /d
Write-Host "Done." -ForegroundColor Green
