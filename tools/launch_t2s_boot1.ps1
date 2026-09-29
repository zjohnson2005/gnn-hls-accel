# T2S boot 1. 4B-int4 GPU u8, then 8B-int4 GPU u8, on platform evo-t2.
# Same cell machinery as launch_boot4.ps1. Estimates are base_s plus the
# measured canary overhead. See launch_boot1.ps1 profile t2s-boot1.
# This script does not open the PARITY-REMEASURE prereg.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$RebootIfClear
)

$ErrorActionPreference = "Stop"

if ($RebootIfClear) {
    # Floor matches configs/platforms/evo-t2.yaml measurement_gates.pre_run_available_mb_min.
    $floorMb = 24000
    $busy = @(Get-Process -Name python, llama-server -ErrorAction SilentlyContinue)
    if ($busy.Count -gt 0) {
        Write-Host "REFUSED -- python or llama-server is running"
        exit 1
    }
    $freeMb = (Get-Counter '\Memory\Available MBytes').CounterSamples[0].CookedValue
    if ([double]$freeMb -lt $floorMb) {
        Write-Host ("REFUSED -- free memory {0} MB is below floor {1}" -f [int]$freeMb, $floorMb)
        exit 1
    }
    $launch = "powershell -NoProfile -File `"$PSCommandPath`" -Detach"
    New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce" `
        -Name "T2SBoot1" -Value $launch -PropertyType String -Force | Out-Null
    shutdown /r /t 5 /c "T2S-boot-1"
    exit 0
}

$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "t2s-boot1")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
& powershell @launchArgs
exit $LASTEXITCODE
