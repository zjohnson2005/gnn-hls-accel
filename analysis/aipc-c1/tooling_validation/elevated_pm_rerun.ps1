$ErrorActionPreference = "Continue"
$log = "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\elevated_pm_rerun.log"
function W($m){ "$(Get-Date -Format o) $m" | Tee-Object -FilePath $log -Append }
"" | Set-Content $log
W "rerun start IsAdmin check"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
W "IsAdmin=$($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))"

$html = "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\fixtures\f3_canvas60.html"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$uri = "file:///" + ($html -replace '\\','/')
$profile = "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\chrome_pm_profile"
# Kill stale PresentMon if any, relaunch chrome
Get-Process PresentMon*, presentmon -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Process -FilePath $chrome -ArgumentList @("--user-data-dir=$profile","--disable-extensions","--autoplay-policy=no-user-gesture-required","--new-window",$uri)
Start-Sleep -Seconds 6
W "chrome launched; starting 60s PresentMon"

$pm = "C:\Users\zjohn\AppData\Local\Microsoft\WinGet\Packages\Intel.PresentMon.Console_Microsoft.Winget.Source_8wekyb3d8bbwe\presentmon.exe"
$csv = "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\presentmon_f3_canvas_60s.csv"
& $pm --process_name chrome.exe --output_file $csv --timed 60 --terminate_after_timed --stop_existing_session --v2_metrics *> "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\presentmon_f3_canvas_60s.log"
W "PresentMon exit=$LASTEXITCODE csvExists=$(Test-Path $csv) size=$((Get-Item $csv -EA SilentlyContinue).Length)"

# Analyze frame times
if (Test-Path $csv) {
  $rows = Import-Csv $csv
  $col = ($rows[0].PSObject.Properties.Name | Where-Object { $_ -match 'MsBetweenPresents|msBetweenPresents|FrameTime' } | Select-Object -First 1)
  W "frame column=$col rows=$($rows.Count)"
  if ($col) {
    $vals = $rows | ForEach-Object { [double]($_.$col) } | Where-Object { $_ -gt 0 -and $_ -lt 1000 }
    $sorted = $vals | Sort-Object
    $n = $sorted.Count
    $med = $sorted[[int]($n/2)]
    $p95 = $sorted[[int](0.95*($n-1))]
    $p99 = $sorted[[int](0.99*($n-1))]
    W ("n={0} median={1:N3}ms p95={2:N3} p99={3:N3} mean={4:N3}" -f $n,$med,$p95,$p99,(($vals|Measure-Object -Average).Average))
  } else {
    W ("headers: " + ($rows[0].PSObject.Properties.Name -join ','))
  }
}

# NPU counters elevated
typeperf -q 2>&1 | Select-String -Pattern 'NPU|Neural' | Out-File "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\npu_counters_elevated.txt"
W "NPU counter lines: $((Get-Content C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\npu_counters_elevated.txt -EA SilentlyContinue | Measure-Object).Count)"
typeperf "\Processor Information(_Total)\% Processor Performance" -sc 3 *> "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\typeperf_proc_perf.txt"
W "typeperf proc done"

"done $(Get-Date -Format o)" | Set-Content "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\elevated_pm_rerun.done"
W "all done"
