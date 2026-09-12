param(
    [Parameter(Mandatory = $true)][string]$WatchScript,
    [Parameter(Mandatory = $true)][string]$KillLogPath,
    [Parameter(Mandatory = $true)][int]$IntervalS
)
$ErrorActionPreference = "Continue"
$t0 = (Get-Date).ToUniversalTime().ToString("o")
$initial = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
$initRecord = [ordered]@{
    utc        = $t0
    event      = "watchdog_start_kill"
    interval_s = $IntervalS
    pids_found = @($initial | ForEach-Object { [int]$_.Id })
    n_killed   = 0
}
if ($initial.Count -gt 0) {
    $initial | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $left = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    $initRecord.n_killed = $initial.Count - $left.Count
    $initRecord.pids_remaining = @($left | ForEach-Object { [int]$_.Id })
}
Add-Content -LiteralPath $KillLogPath -Value (
    (ConvertTo-Json -InputObject $initRecord -Compress -Depth 4))

# Identical to tools/run_delta_prefill_matrix.ps1 Start-WshWatchdog:
# Start-Process -PassThru -WindowStyle Hidden — NOT DETACHED_PROCESS.
$watchProc = Start-Process -FilePath "powershell.exe" -PassThru -WindowStyle Hidden `
    -ArgumentList @(
        "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass",
        "-File", $WatchScript,
        "-LogPath", $KillLogPath,
        "-IntervalS", "$IntervalS"
    )
[pscustomobject]@{
    kind       = "process"
    pid        = $watchProc.Id
    script     = $WatchScript
    interval_s = $IntervalS
    kill_log   = $KillLogPath
    mechanism  = "Start-Process_WindowStyle_Hidden"
} | ConvertTo-Json -Compress
