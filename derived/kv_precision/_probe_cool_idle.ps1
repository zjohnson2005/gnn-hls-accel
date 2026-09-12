# One-shot cool/idle probe for DISPATCH P. Report only; does not launch.
$ErrorActionPreference = "Continue"
Write-Host "=== AC / Battery ==="
try {
    $bat = Get-CimInstance Win32_Battery -ErrorAction Stop
    $bat | Format-List BatteryStatus, EstimatedChargeRemaining, Caption
} catch {
    Write-Host ("Win32_Battery: " + $_.Exception.Message)
}
try {
    $bs = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction Stop
    $bs | Select-Object -First 1 | Format-List PowerOnline, Charging, Discharging, RemainingCapacity, Voltage
} catch {
    Write-Host ("BatteryStatus WMI: " + $_.Exception.Message)
}

Write-Host "=== Available MBytes ==="
try {
    $s = (Get-Counter '\Memory\Available MBytes').CounterSamples[0].CookedValue
    Write-Host ("Available MBytes = " + $s)
} catch {
    Write-Host $_.Exception.Message
}

Write-Host "=== Tier-1 contenders ==="
$tier1 = @(
    "Cursor", "Code", "chrome", "msedge", "firefox", "brave", "slack",
    "Discord", "Teams", "ms-teams", "Spotify", "OUTLOOK", "obsidian",
    "docker desktop", "vmmem", "claude"
)
$found = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $tier1 -contains $_.ProcessName })
if ($found.Count -eq 0) {
    Write-Host "none"
} else {
    $found | Group-Object ProcessName | ForEach-Object {
        Write-Host ("{0} x{1}" -f $_.Name, $_.Count)
    }
}

Write-Host "=== Package temp / GPU freq (best effort) ==="
try {
    $tz = @(Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop)
    foreach ($t in $tz) {
        $c = ($t.CurrentTemperature / 10.0) - 273.15
        Write-Host ("MSAcpi {0} C={1:N1}" -f $t.InstanceName, $c)
    }
} catch {
    Write-Host ("MSAcpi: " + $_.Exception.Message)
}
try {
    $counters = Get-Counter '\Thermal Zone Information(*)\Temperature' -ErrorAction Stop
    foreach ($sample in $counters.CounterSamples) {
        Write-Host ("{0} = {1}" -f $sample.Path, $sample.CookedValue)
    }
} catch {
    Write-Host ("ThermalZone counter: " + $_.Exception.Message)
}
try {
    $counters = Get-Counter '\Processor Information(_Total)\% Processor Performance' -ErrorAction Stop
    foreach ($sample in $counters.CounterSamples) {
        Write-Host ("{0} = {1}" -f $sample.Path, $sample.CookedValue)
    }
} catch {
    Write-Host ("ProcPerf: " + $_.Exception.Message)
}
try {
    $counters = Get-Counter '\Processor Information(_Total)\Processor Frequency' -ErrorAction Stop
    foreach ($sample in $counters.CounterSamples) {
        Write-Host ("{0} = {1}" -f $sample.Path, $sample.CookedValue)
    }
} catch {
    Write-Host ("ProcFreq: " + $_.Exception.Message)
}
Write-Host "=== probe_utc ==="
Write-Host ((Get-Date).ToUniversalTime().ToString("o"))
