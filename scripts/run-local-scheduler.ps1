[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$logDir = Join-Path $env:LOCALAPPDATA "OddsQuant\logs"
$workerLog = Join-Path $logDir "scheduler.log"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$env:ODDSQUANT_ENVIRONMENT = "production"
$env:ODDSQUANT_SEED_DEMO = "false"

Push-Location $backendDir
try {
    $ErrorActionPreference = "Continue"
    & py -m alembic upgrade head *>> $workerLog
    $migrationExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($migrationExitCode -ne 0) {
        throw "Database migration failed with exit code $migrationExitCode."
    }

    while ($true) {
        $ErrorActionPreference = "Continue"
        & py -m app.jobs.scheduler *>> $workerLog
        $schedulerExitCode = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        Add-Content -LiteralPath $workerLog -Value (
            "{0:o} scheduler exited with code {1}; restarting in 60 seconds." -f (
                Get-Date
            ), $schedulerExitCode
        )
        Start-Sleep -Seconds 60
    }
}
finally {
    Pop-Location
}
