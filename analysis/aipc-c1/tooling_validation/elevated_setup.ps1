$ErrorActionPreference = "Continue"
$log = "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\elevated_setup.log"
function W($m){ "$(Get-Date -Format o) $m" | Tee-Object -FilePath $log -Append }
W "elevated start; IsAdmin check"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
W "IsAdmin=$($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))"

# Add current user to Performance Log Users
$user = "$env:USERDOMAIN\$env:USERNAME"
W "Adding $user to Performance Log Users"
net localgroup "Performance Log Users" $user /add 2>&1 | ForEach-Object { W $_ }
net localgroup "Performance Monitor Users" $user /add 2>&1 | ForEach-Object { W $_ }

# PresentMon capture
$pm = "C:\Users\zjohn\AppData\Local\Microsoft\WinGet\Packages\Intel.PresentMon.Console_Microsoft.Winget.Source_8wekyb3d8bbwe\presentmon.exe"
$csv = "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\presentmon_f3_canvas_60s.csv"
$html = "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\fixtures\f3_canvas60.html"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$uri = "file:///" + ($html -replace '\\','/')
if (-not (Get-Process chrome -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $chrome -ArgumentList @("--user-data-dir=C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\chrome_pm_profile","--disable-extensions","--autoplay-policy=no-user-gesture-required","--new-window",$uri)
  Start-Sleep -Seconds 5
}
W "Starting PresentMon 60s"
& $pm --process_name chrome.exe --output_file $csv --timed 60 --terminate_after_timed --stop_existing_session --v2_metrics *> "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\presentmon_f3_canvas_60s.log"
W "PresentMon exit=$LASTEXITCODE csvExists=$(Test-Path $csv) size=$((Get-Item $csv -EA SilentlyContinue).Length)"

# typeperf NPU search elevated
typeperf -q 2>&1 | Select-String -Pattern 'NPU|Neural' | Out-File "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\npu_counters_elevated.txt"
W "NPU counter lines: $((Get-Content C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\npu_counters_elevated.txt | Measure-Object).Count)"

# Processor performance via typeperf
typeperf "\Processor Information(_Total)\% Processor Performance" -sc 3 2>&1 | Out-File "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\typeperf_proc_perf.txt"
W "typeperf proc done"

"done $(Get-Date -Format o)" | Set-Content "C:\Users\zjohn\Projects\gnn-hls-accel\analysis\aipc-c1\tooling_validation\elevated_setup.done"
W "all done"
