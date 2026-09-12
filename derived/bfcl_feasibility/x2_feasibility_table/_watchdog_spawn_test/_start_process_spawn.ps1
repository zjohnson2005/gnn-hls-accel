
$ErrorActionPreference = "Stop"
$p = Start-Process -FilePath "powershell.exe" -PassThru -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass",
    "-File", "C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\x2_feasibility_table\_watchdog_spawn_test\_wsh_watchdog.ps1",
    "-LogPath", "C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\x2_feasibility_table\_watchdog_spawn_test\watchdog_kills.jsonl",
    "-IntervalS", "5"
)
Start-Sleep -Seconds 8
$alive = $null -ne (Get-Process -Id $p.Id -ErrorAction SilentlyContinue)
$n = @(Get-Content -LiteralPath "C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\x2_feasibility_table\_watchdog_spawn_test\watchdog_kills.jsonl" -ErrorAction SilentlyContinue).Count
[pscustomobject]@{
    label = "start_process_matrix_pattern"
    pid = $p.Id
    alive_after_8s = $alive
    n_log_lines = $n
} | ConvertTo-Json -Compress
if ($alive) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
