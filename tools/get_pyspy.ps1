# Fetch a standalone py-spy.exe for the turn watchdog's hang dump (Task AX).
# On the XPS: <profile>\seam_tools\py-spy.exe; the window script runs it before the reboot.
#
# Approved by Zach 2026-10-20: py-spy as a STANDALONE executable in the seam
# tools folder, NOT installed into .venv-seam, so the measurement environment is
# unchanged. The venv's pip only DOWNLOADS the wheel (no install); py-spy.exe is
# extracted from the wheel's *.data/scripts/. The pip freeze of the venv is hashed
# before and after and must match.
#
# Does nothing if py-spy.exe is already present (still reports its sha256 and
# version, and the freeze hash). Output lines (one per fact):
#   PRESENT / WHEEL <name> <sha256> / SHA256 <exe sha256> / VERSION <text>
#   FREEZE_BEFORE <sha256> / FREEZE_AFTER <sha256> / PIP_FREEZE_UNCHANGED
# Exit codes: 0 ok; 2 download failed; 3 no py-spy.exe in the wheel;
#             4 pip freeze changed (stop: the venv was modified); 5 wheel sha256 mismatch.
# Pin: py-spy 0.4.2 (PyPI win_amd64 wheel uploaded 2026-04-24), wheel sha256 checked
# before extraction (value read from PyPI on the Mac, 2026-10-20).
param(
    [string]$Version = "0.4.2",
    [string]$WheelSha256 = "8b06a353c177677e4e1701b288d8c58e2f8d4208ee81a8048d9f72ba800918f8",
    # Defaults: the XPS layout under the current user's profile (PORT-1: no user path literals).
    [string]$Python = (Join-Path $env:USERPROFILE "Projects\gnn-hls-accel\.venv-seam\Scripts\python.exe"),
    [string]$ToolsDir = (Join-Path $env:USERPROFILE "seam_tools")
)
$ErrorActionPreference = "Continue"

function Get-TextSha256([string]$Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "")
}

function Get-FreezeHash {
    $lines = @(& $Python -m pip freeze --all 2>$null)
    return Get-TextSha256 (($lines | Sort-Object) -join "`n")
}

New-Item -ItemType Directory -Force $ToolsDir | Out-Null
$exe = Join-Path $ToolsDir "py-spy.exe"
$before = Get-FreezeHash
"FREEZE_BEFORE $before"

if (Test-Path -LiteralPath $exe) {
    "PRESENT $exe"
} else {
    $dl = Join-Path $ToolsDir "pyspy_dl"
    New-Item -ItemType Directory -Force $dl | Out-Null
    $pipOut = @(& $Python -m pip download "py-spy==$Version" --no-deps --only-binary=:all: -d $dl 2>&1)
    $pipCode = $LASTEXITCODE
    $pipOut | ForEach-Object { "PIP $_" }
    $whl = Get-ChildItem -LiteralPath $dl -Filter "py_spy-$Version-*.whl" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($pipCode -ne 0 -or $null -eq $whl) {
        "DOWNLOAD_FAILED py-spy==$Version (pip exit $pipCode)"
        exit 2
    }
    $whlHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $whl.FullName).Hash
    "WHEEL $($whl.Name) $whlHash"
    if ($whlHash.ToLower() -ne $WheelSha256.ToLower()) {
        "WHEEL_SHA256_MISMATCH expected $WheelSha256"
        exit 5
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($whl.FullName)
    try {
        $entry = $zip.Entries | Where-Object { $_.FullName -like "*.data/scripts/py-spy.exe" } |
            Select-Object -First 1
        if ($null -eq $entry) {
            "NO_EXE_IN_WHEEL $($whl.Name)"
            exit 3
        }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $exe, $true)
    } finally {
        $zip.Dispose()
    }
}

"SHA256 $((Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash)"
"VERSION $((& $exe --version 2>&1) -join ' ')"
$after = Get-FreezeHash
"FREEZE_AFTER $after"
if ($after -ne $before) {
    "PIP_FREEZE_CHANGED"
    exit 4
}
"PIP_FREEZE_UNCHANGED"
exit 0
