[CmdletBinding()]
param(
    [string]$TaskName = "OddsQuant-Collector",
    [switch]$ReplaceRunningScheduler
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run-local-scheduler.ps1"
$powershell = Join-Path $PSHOME "powershell.exe"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Scheduler runner not found: $runner"
}

if ($ReplaceRunningScheduler) {
    $existing = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match "(?i)(^|\s)-m\s+app\.jobs\.scheduler(\s|$)"
    }
    foreach ($process in $existing) {
        Stop-Process -Id $process.ProcessId -Force
    }
}

$arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $runner
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 255 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Runs the OddsQuant prospective collector at its configured adaptive cadence."
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

foreach ($attempt in 1..20) {
    Start-Sleep -Seconds 1
    $registered = Get-ScheduledTask -TaskName $TaskName
    if ($registered.State -eq "Running") {
        break
    }
}

$registered = Get-ScheduledTask -TaskName $TaskName
if ($registered.State -ne "Running") {
    throw "Scheduled task $TaskName did not enter the Running state."
}

$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $TaskName
    State = $registered.State
    LastRunTime = $info.LastRunTime
    LastTaskResult = $info.LastTaskResult
    User = $currentUser
}
