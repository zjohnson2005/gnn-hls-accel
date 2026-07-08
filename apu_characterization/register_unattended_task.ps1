# Register a logon Task Scheduler job that resumes APU characterization work.
#
# One-liner (from repo root):
#   .\apu_characterization\register_unattended_task.ps1
#
# Options:
#   -Mode Auto|Replicate|Probe   (default Auto)
#   -TestOnly                    print planned task; do not register
#   -AllowDirty                  pass --allow-dirty to replication

param(
    [ValidateSet("Auto", "Replicate", "Probe")]
    [string]$Mode = "Auto",
    [switch]$TestOnly,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

$TaskName = "APU-Characterization-Resume"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resumeScript = Join-Path $PSScriptRoot "run_unattended_resume.ps1"

if (-not (Test-Path $resumeScript)) {
    Write-Error "Missing $resumeScript"
}

$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$resumeScript`" -Mode $Mode"
if ($AllowDirty) { $arguments += " -AllowDirty" }

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $arguments `
    -WorkingDirectory $repo

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

$description = @"
Resume APU v3 replication or probe suite after logon/reboot.
Repo: $repo
Log: apu_characterization/out/unattended_run.log
Requires OPENAI_API_KEY in user environment for replication/gate.
"@

Write-Host "Task: $TaskName"
Write-Host "Trigger: At logon for $env:USERNAME"
Write-Host "Action: powershell.exe $arguments"
Write-Host "WorkingDirectory: $repo"
Write-Host "Mode: $Mode"
Write-Host "Log: apu_characterization/out/unattended_run.log"
Write-Host ""
Write-Host "Ensure OPENAI_API_KEY is set as a persistent user environment variable"
Write-Host "(System Properties > Environment Variables) before shutting down."
Write-Host ""

if ($TestOnly) {
    Write-Host "TestOnly: task not registered."
    exit 0
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Replacing existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description $description.Trim() | Out-Null

Write-Host "Registered. On next logon the task runs automatically."
Write-Host "Unregister: .\apu_characterization\unregister_unattended_task.ps1"
