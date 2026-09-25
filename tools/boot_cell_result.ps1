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
