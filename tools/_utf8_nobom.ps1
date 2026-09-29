# UTF-8 without a BOM. Windows PowerShell 5 Set-Content -Encoding utf8 writes a BOM,
# and Python json.loads(encoding="utf-8") then raises JSONDecodeError.

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text
    )
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $Text, $utf8)
}
