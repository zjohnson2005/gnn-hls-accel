# Shared pre-spawn measurement gates for launch_*.ps1 (PORT-2).
#
# Dot-source from a launcher after $root is set:
#   . (Join-Path $PSScriptRoot '_run_measurement_gates.ps1')
#   Invoke-SeamMeasurementGates -RepoRoot $root -PythonExe $PythonExe -PlatformId $PlatformId -DryRun:$DryRun
#
# Refuses (exit 1) when any pass/fail gate fails, unless -DryRun (report-only).
# Writes gate JSON under derived/_gate_probes/ for seal attachment. A -DryRun
# writes under derived/_gate_probes/_dryrun/ (gitignored), so a dry run does
# not leave the tree dirty for the next real launch.
#
# Get-SeamGateRefusals reads the refusal_reasons of a gate JSON, for the
# launchers' dry-run summary:
#   $gateJson = Invoke-SeamMeasurementGates ...
#   $gateFails = @(Get-SeamGateRefusals -GateJson $gateJson)

Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "_utf8_nobom.ps1")

function Invoke-SeamMeasurementGates {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [string]$PlatformId = "",
        # T2S is not rebooted: skip only the uptime gate; the gate JSON records
        # the UNCOLD_UPTIME deviation (seam.measurement_gates --skip-uptime).
        [switch]$SkipUptime,
        [switch]$DryRun
    )

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        Write-Host "REFUSED -- PythonExe missing: $PythonExe"
        if (-not $DryRun) { exit 2 }
        return $null
    }

    $probeDir = Join-Path $RepoRoot "derived\_gate_probes"
    if ($DryRun) { $probeDir = Join-Path $probeDir "_dryrun" }
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
    if ($SkipUptime) {
        $pyArgs += "--skip-uptime"
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
    Write-Utf8NoBom -Path $outJson -Text $text
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

function Get-SeamGateRefusals {
    # refusal_reasons from a gate JSON written by Invoke-SeamMeasurementGates.
    # Report-only: it reads the gate result and changes no gate.
    [CmdletBinding()]
    param([string]$GateJson = "")

    if ([string]::IsNullOrWhiteSpace($GateJson) -or -not (Test-Path -LiteralPath $GateJson)) {
        return @("gates: no gate JSON (the gates did not run)")
    }
    $text = Get-Content -LiteralPath $GateJson -Raw -Encoding UTF8
    $start = $text.IndexOf("{")
    $end = $text.LastIndexOf("}")
    if ($start -lt 0 -or $end -le $start) {
        return @("gates: gate JSON unreadable: $GateJson")
    }
    try {
        $doc = $text.Substring($start, $end - $start + 1) | ConvertFrom-Json
    } catch {
        return @("gates: gate JSON unreadable: $GateJson")
    }
    if ($null -eq $doc.PSObject.Properties["refusal_reasons"]) {
        return @("gates: gate JSON has no refusal_reasons: $GateJson")
    }
    return @($doc.refusal_reasons | ForEach-Object { [string]$_ })
}
