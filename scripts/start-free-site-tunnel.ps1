[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$taskTemp = Join-Path $env:TEMP "oddsquant-free-tunnel"
$apiOutput = Join-Path $taskTemp "api.out.log"
$apiError = Join-Path $taskTemp "api.err.log"
$workerOutput = Join-Path $taskTemp "worker.out.log"
$workerError = Join-Path $taskTemp "worker.err.log"
$tunnelOutput = Join-Path $taskTemp "tunnel.out.log"
$tunnelError = Join-Path $taskTemp "tunnel.err.log"

New-Item -ItemType Directory -Path $taskTemp -Force | Out-Null

$cloudflared = @(
    (Get-Command cloudflared -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
    "C:\Program Files (x86)\cloudflared\cloudflared.exe",
    "C:\Program Files\cloudflared\cloudflared.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not $cloudflared) {
    throw "cloudflared is not installed. Run: winget install --id Cloudflare.cloudflared --exact"
}

Push-Location $backendDir
try {
    & py -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$apiUrl = "http://127.0.0.1:$Port"
$apiReady = $false
try {
    Invoke-WebRequest -Uri "$apiUrl/api/v1/matchdays" -UseBasicParsing -TimeoutSec 3 | Out-Null
    $apiReady = $true
}
catch {
    $apiReady = $false
}

if (-not $apiReady) {
    $env:ODDSQUANT_ENVIRONMENT = "production"
    $env:ODDSQUANT_SEED_DEMO = "false"
    $env:ODDSQUANT_CORS_ORIGINS = "https://oddsquant-research.kkakarantzas17.chatgpt.site"
    Start-Process -FilePath "py" `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port" `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput $apiOutput `
        -RedirectStandardError $apiError `
        -WindowStyle Hidden

    foreach ($attempt in 1..20) {
        Start-Sleep -Seconds 1
        try {
            Invoke-WebRequest -Uri "$apiUrl/api/v1/matchdays" -UseBasicParsing -TimeoutSec 3 | Out-Null
            $apiReady = $true
            break
        }
        catch {
            $apiReady = $false
        }
    }
}

if (-not $apiReady) {
    throw "The API did not become ready. Review $apiError."
}

$scheduler = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like "*app.jobs.scheduler*"
} | Select-Object -First 1

if (-not $scheduler) {
    $env:ODDSQUANT_ENVIRONMENT = "production"
    $env:ODDSQUANT_SEED_DEMO = "false"
    Start-Process -FilePath "py" `
        -ArgumentList "-m", "app.jobs.scheduler" `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput $workerOutput `
        -RedirectStandardError $workerError `
        -WindowStyle Hidden
}

$publicUrl = $null
if (Test-Path -LiteralPath $tunnelError) {
    $existingUrl = Select-String -Path $tunnelError -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" |
        Select-Object -Last 1
    if ($existingUrl -and (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
        $publicUrl = $existingUrl.Matches[0].Value
    }
}

if (-not $publicUrl) {
    Start-Process -FilePath $cloudflared `
        -ArgumentList "tunnel", "--url", $apiUrl, "--no-autoupdate" `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $tunnelOutput `
        -RedirectStandardError $tunnelError `
        -WindowStyle Hidden
}

foreach ($attempt in 1..30) {
    if ($publicUrl) {
        break
    }
    Start-Sleep -Seconds 1
    if (Test-Path -LiteralPath $tunnelError) {
        $match = Select-String -Path $tunnelError -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" |
            Select-Object -Last 1
        if ($match) {
            $publicUrl = $match.Matches[0].Value
            break
        }
    }
}

if (-not $publicUrl) {
    throw "The tunnel URL was not found. Review $tunnelError."
}

Write-Output "OddsQuant API tunnel: $publicUrl"
Write-Output "Keep this computer, the API, scheduler, and cloudflared running while the site uses this URL."
