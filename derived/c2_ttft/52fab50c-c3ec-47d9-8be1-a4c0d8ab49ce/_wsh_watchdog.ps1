param([string]$LogPath, [int]$IntervalS)
$ErrorActionPreference = "Continue"
if ($IntervalS -lt 30) { $IntervalS = 30 }
while ($true) {
    Start-Sleep -Seconds $IntervalS
    $utc = (Get-Date).ToUniversalTime().ToString("o")
    $procs = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    if ($procs.Count -eq 0) {
        $rec = [ordered]@{ utc = $utc; event = "watchdog_poll"; n_found = 0; n_killed = 0 }
        Add-Content -LiteralPath $LogPath -Value (ConvertTo-Json -InputObject $rec -Compress)
        continue
    }
    $pids = @($procs | ForEach-Object { [int]$_.Id })
    $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $left = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    $rec = [ordered]@{
        utc            = $utc
        event          = "watchdog_kill"
        n_found        = $pids.Count
        pids_found     = $pids
        n_killed       = $pids.Count - $left.Count
        pids_remaining = @($left | ForEach-Object { [int]$_.Id })
    }
    Add-Content -LiteralPath $LogPath -Value (ConvertTo-Json -InputObject $rec -Compress -Depth 4)
}
