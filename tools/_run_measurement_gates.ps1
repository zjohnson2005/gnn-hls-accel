# Shared pre-spawn measurement gates for launch_*.ps1 (PORT-2).
#
# Dot-source from a launcher after $root is set:
#   . (Join-Path $PSScriptRoot '_run_measurement_gates.ps1')
#   Invoke-SeamMeasurementGates -RepoRoot $root -PythonExe $PythonExe -PlatformId $PlatformId -DryRun:$DryRun
#
# Refuses (exit 1) when any pass/fail gate fails, unless -DryRun (report-only).
# Writes gate JSON under derived/_gate_probes/ for seal attachment.

Set-StrictMode -Version Latest

function Invoke-SeamMeasurementGates {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [string]$PlatformId = "",
        [switch]$DryRun
    )

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        Write-Host "REFUSED -- PythonExe missing: $PythonExe"
        if (-not $DryRun) { exit 2 }
        return $null
    }

    $probeDir = Join-Path $RepoRoot "derived\_gate_probes"
    New-Item -ItemType Directory -Force -Path $probeDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $outJson = Join-Path $probeDir ("gates_" + $stamp + ".json")

    $pyArgs = @(
        "-m", "seam.measurement_gates",
        "--repo-root", $RepoRoot,
        "--json"
    )
    if (-not [string]::IsNullOrWhiteSpace($PlatformId)) {
        $pyArgs += @("--platform-id", $PlatformId)
    }

    Write-Host "=== measurement gates (PORT-2) ==="
    $prev = $env:PYTHONPATH
    try {
        if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
            $env:PYTHONPATH = $RepoRoot
        } elseif ($env:PYTHONPATH -notlike "*$RepoRoot*") {
            $env:PYTHONPATH = "$RepoRoot;$env:PYTHONPATH"
        }
        $output = & $PythonExe @pyArgs 2>&1
        $code = $LASTEXITCODE
    } finally {
        $env:PYTHONPATH = $prev
    }

    $text = ($output | ForEach-Object { "$_" }) -join "`n"
    Set-Content -LiteralPath $outJson -Value $text -Encoding utf8
    Write-Host $text
    Write-Host ("gate_json: {0}" -f $outJson)

    if ($code -ne 0) {
        Write-Host ("GATES FAILED (exit={0})" -f $code)
        if (-not $DryRun) {
            Write-Host "REFUSED -- measurement gates failed; no spawn"
            exit 1
        }
        Write-Host "DRY-RUN: continuing past gate failures (report-only)"
    } else {
        Write-Host "GATES: all pass/fail gates PASS"
    }
    return $outJson
}
