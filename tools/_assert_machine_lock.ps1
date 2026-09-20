# Shared machine-lock / alive-worker gate for launch_*.ps1.
#
# Dot-source after $root is set:
#   . (Join-Path $PSScriptRoot '_assert_machine_lock.ps1')
#   Assert-SeamMachineLockClear -RepoRoot $root [-DryRun]
#
# Refuses spawn when .locks/machine.lock is held by a live PID, or when another
# measurement worker (CAP-4 / H-1 / ceiling / matrix / ...) is already alive.
# Stale locks (dead owner PID) are reported and allowed to continue.

Set-StrictMode -Version Latest

$script:SeamMeasurementWorkerPatterns = @(
    "run_h1_hybrid.py",
    "run_cap4_prefill_curve.py",
    "run_c1_ceiling.py",
    "run_c2_ttft.py",
    "run_delta_prefill_matrix",
    "run_gpu_only_matrix",
    "run_bfcl_session_residency",
    "run_q8b",
    "ceiling_a.ps1",
    "seam.tools.delta_n",
    "seam.tools.attrib",
    "seam.tools.prompt_a",
    "seam.tools.efilter_run",
    "seam.tools.ceiling_a",
    "seam.tools.a3_residency",
    "seam.tools.fixed_throughput",
    "seam.tools.canary_baseline"
)

function Get-SeamAliveMeasurementWorkers {
    [CmdletBinding()]
    param(
        [int[]]$ExcludePids = @()
    )
    $exclude = @{}
    foreach ($pidEx in $ExcludePids) { $exclude[[int]$pidEx] = $true }
    $hits = @()
    $procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    foreach ($proc in $procs) {
        $pidVal = [int]$proc.ProcessId
        if ($exclude.ContainsKey($pidVal)) { continue }
        $cl = $proc.CommandLine
        if ([string]::IsNullOrWhiteSpace($cl)) { continue }
        $clLower = $cl.ToLowerInvariant()
        foreach ($pat in $script:SeamMeasurementWorkerPatterns) {
            if ($clLower.Contains($pat.ToLowerInvariant())) {
                $hits += [pscustomobject]@{
                    pid          = $pidVal
                    name         = $proc.Name
                    command_line = $cl
                    matched      = $pat
                }
                break
            }
        }
    }
    return $hits
}

function Assert-SeamMachineLockClear {
    <#
    .SYNOPSIS
      Refuse spawn when machine.lock is held by a live PID, or another
      measurement worker is already running.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [switch]$DryRun
    )

    $lockPath = Join-Path $RepoRoot ".locks\machine.lock"

    function _Refuse([string]$Reason) {
        Write-Host ""
        Write-Host "REFUSED -- $Reason"
        if ($DryRun) { return }
        exit 1
    }

    Write-Host "=== machine-lock / alive-worker check ==="
    if (Test-Path -LiteralPath $lockPath) {
        $raw = Get-Content -LiteralPath $lockPath -Raw -ErrorAction Stop
        $ownerPid = $null
        try {
            $rec = $raw | ConvertFrom-Json
            if ($null -ne $rec.pid) { $ownerPid = [int]$rec.pid }
        } catch {
            if ($raw -match '^\s*pid\s*=\s*(\d+)') {
                $ownerPid = [int]$Matches[1]
            } else {
                _Refuse ("machine.lock present but unparseable at {0}; refuse spawn" -f $lockPath)
                return
            }
        }
        if ($null -ne $ownerPid) {
            $alive = $null -ne (Get-Process -Id $ownerPid -ErrorAction SilentlyContinue)
            if ($alive) {
                _Refuse ("machine.lock held by live PID {0} ({1}); refuse spawn" -f $ownerPid, $lockPath)
                return
            }
            Write-Host ("machine.lock present but owner PID {0} is dead (stale); continuing" -f $ownerPid)
        } else {
            _Refuse ("machine.lock present with no pid at {0}; refuse spawn" -f $lockPath)
            return
        }
    } else {
        Write-Host "machine.lock: absent"
    }

    $workers = @(Get-SeamAliveMeasurementWorkers -ExcludePids @($PID))
    if ($workers.Count -gt 0) {
        Write-Host "REFUSED -- another measurement worker is alive:"
        foreach ($w in $workers) {
            Write-Host ("  - pid={0} name={1} matched={2}" -f $w.pid, $w.name, $w.matched)
            Write-Host ("    cmd={0}" -f $w.command_line)
        }
        _Refuse ("{0} measurement worker(s) alive; refuse spawn" -f $workers.Count)
        return
    }
    Write-Host "alive measurement workers: none"
    Write-Host ""
}
