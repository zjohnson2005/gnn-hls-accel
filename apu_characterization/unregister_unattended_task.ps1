# Remove the logon Task Scheduler job for APU characterization resume.

$ErrorActionPreference = "Stop"
$TaskName = "APU-Characterization-Resume"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Task '$TaskName' is not registered."
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Unregistered '$TaskName'."
