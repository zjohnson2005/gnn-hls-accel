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
