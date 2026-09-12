$m = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | Select-Object -First 1
if ($null -eq $m) { Write-Output "NO_METHODS"; exit 1 }
Write-Output "HAS_METHODS"
$b = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | Select-Object -First 1
Write-Output ("current=" + $b.CurrentBrightness)
