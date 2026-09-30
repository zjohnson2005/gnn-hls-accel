# Read a ceiling summary without letting worker stdout become the return value.
# The boot-1 crash was $ran.Status after Invoke-CeilingCell also emitted the
# worker's stdout lines, so $ran was an Object[] and Status was missing.

function Get-BootCeilingResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$SummaryPath,
        [string[]]$Stdout = @(),
        [int]$ExitCode = 0,
        [string]$RunId = "",
        [string]$Out = ""
    )
    $status = ""
    if (Test-Path -LiteralPath $SummaryPath) {
        $summary = Get-Content -LiteralPath $SummaryPath -Raw -Encoding utf8 | ConvertFrom-Json
        $prop = $summary.PSObject.Properties["status"]
        if ($null -ne $prop) { $status = [string]$prop.Value }
    }
    $stdoutText = (@($Stdout) | ForEach-Object { [string]$_ }) -join "`n"
    return [pscustomobject]@{
        Status = $status
        Exit = $ExitCode
        RunId = $RunId
        Out = $Out
        Stdout = $stdoutText
    }
}

function Select-BootPriorCells {
    <#
    A boot summary keeps cells only from the same boot id. A previous boot's
    rows, including a stale REFUSED row, are not merged into the new document.
    #>
    param($Existing, [string]$BootId)
    if ($null -eq $Existing) { return @() }
    $bootProp = $Existing.PSObject.Properties["boot_id"]
    if ($null -eq $bootProp -or [string]$bootProp.Value -ne [string]$BootId) {
        return @()
    }
    $cellsProp = $Existing.PSObject.Properties["cells"]
    if ($null -eq $cellsProp -or $null -eq $cellsProp.Value) { return @() }
    return @($cellsProp.Value)
}

function Read-CellStatusFile {
    <#
    Line 1 is the cell status. Line 2, when present, is the session run id.
    A status-only file leaves the run id empty.
    #>
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{ Status = "complete"; RunId = "" }
    }
    $lines = @(Get-Content -LiteralPath $Path)
    $status = "complete"
    $runId = ""
    if ($lines.Count -ge 1 -and -not [string]::IsNullOrWhiteSpace([string]$lines[0])) {
        $status = ([string]$lines[0]).Trim()
    }
    if ($lines.Count -ge 2) {
        $runId = ([string]$lines[1]).Trim()
    }
    return [pscustomobject]@{ Status = $status; RunId = $runId }
}

function Merge-BootCells {
    <#
    Named cells already on disk stay. New rows are appended. A row whose
    name is already present updates that slot. Objects with no name, such as
    a KV readback document, are not cells and are not kept.
    #>
    param($Prior, $Added)
    $merged = @()
    foreach ($item in @($Prior)) {
        if ($null -eq $item) { continue }
        $prop = $item.PSObject.Properties["name"]
        if ($null -eq $prop -or [string]::IsNullOrWhiteSpace([string]$prop.Value)) { continue }
        $merged += $item
    }
    foreach ($row in @($Added)) {
        if ($null -eq $row) { continue }
        $nameProp = $row.PSObject.Properties["name"]
        if ($null -eq $nameProp -or [string]::IsNullOrWhiteSpace([string]$nameProp.Value)) { continue }
        $name = [string]$nameProp.Value
        $found = $false
        for ($i = 0; $i -lt $merged.Count; $i++) {
            if ([string]$merged[$i].name -eq $name) {
                $merged[$i] = $row
                $found = $true
            }
        }
        if (-not $found) { $merged += $row }
    }
    return @($merged)
}
