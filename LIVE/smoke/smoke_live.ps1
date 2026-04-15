param(
    [string]$ComposeFile = "infra/docker-compose.yml",
    [string]$BackendHealthUrl = "http://localhost:8000/health",
    [string]$FrontendUrl = "http://localhost:3001",
    [switch]$WriteReport
)

$ErrorActionPreference = "Stop"
$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )
    $status = if ($Ok) { "PASS" } else { "FAIL" }
    $results.Add([pscustomobject]@{
        Timestamp = (Get-Date).ToString("s")
        Check     = $Name
        Status    = $status
        Detail    = $Detail
    }) | Out-Null

    if ($Ok) {
        Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red
    }
}

try {
    $composeExists = Test-Path -LiteralPath $ComposeFile
    Add-Result -Name "Compose file exists" -Ok $composeExists -Detail $ComposeFile

    if (-not $composeExists) {
        throw "Compose file not found: $ComposeFile"
    }

    $psOutput = docker compose -f $ComposeFile ps 2>&1 | Out-String
    $dockerOk = $LASTEXITCODE -eq 0
    Add-Result -Name "docker compose ps" -Ok $dockerOk -Detail ($psOutput.Trim() -replace "`r`n", " | ")

    if ($dockerOk) {
        $backendUp = $psOutput -match "heizungsleser-v2-backend" -and $psOutput -match "Up"
        $frontendUp = $psOutput -match "heizungsleser-v2-frontend" -and $psOutput -match "Up"
        $dbHealthy = $psOutput -match "heizungsleser-v2-postgres" -and ($psOutput -match "healthy" -or $psOutput -match "Up")

        Add-Result -Name "Backend container up" -Ok $backendUp -Detail "heizungsleser-v2-backend"
        Add-Result -Name "Frontend container up" -Ok $frontendUp -Detail "heizungsleser-v2-frontend"
        Add-Result -Name "DB container healthy/up" -Ok $dbHealthy -Detail "heizungsleser-v2-postgres"
    }

    try {
        $backendResp = Invoke-WebRequest -Uri $BackendHealthUrl -UseBasicParsing -TimeoutSec 15
        Add-Result -Name "Backend health endpoint" -Ok ($backendResp.StatusCode -eq 200) -Detail "HTTP $($backendResp.StatusCode)"
    }
    catch {
        Add-Result -Name "Backend health endpoint" -Ok $false -Detail $_.Exception.Message
    }

    try {
        $frontendResp = Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing -TimeoutSec 15
        Add-Result -Name "Frontend root endpoint" -Ok ($frontendResp.StatusCode -eq 200) -Detail "HTTP $($frontendResp.StatusCode)"
    }
    catch {
        Add-Result -Name "Frontend root endpoint" -Ok $false -Detail $_.Exception.Message
    }
}
catch {
    Add-Result -Name "Smoke script runtime" -Ok $false -Detail $_.Exception.Message
}

$failed = @($results | Where-Object { $_.Status -eq "FAIL" })

if ($WriteReport) {
    $reportDir = "LIVE/reports"
    if (-not (Test-Path -LiteralPath $reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $reportPath = Join-Path $reportDir "smoke-$ts.txt"
    $results | Format-Table -AutoSize | Out-String | Set-Content -Path $reportPath -Encoding UTF8
    Write-Host "Report written: $reportPath"
}

if ($failed.Count -gt 0) {
    Write-Host "`nSmoke-Test Ergebnis: FEHLER" -ForegroundColor Red
    exit 1
}

Write-Host "`nSmoke-Test Ergebnis: OK" -ForegroundColor Green
exit 0
