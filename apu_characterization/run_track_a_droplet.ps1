# Track A: bare-metal validation on a DigitalOcean droplet (footnote-grade).
#
# Prereqs: droplet created (Basic Regular 4 vCPU / 8 GB, Ubuntu 24.04, SSH key),
# OPENAI_API_KEY set in this PowerShell session, bundle exists at
# C:\Users\zjohn\Projects\apu_bare_metal.bundle (create with:
#   git bundle create C:\Users\zjohn\Projects\apu_bare_metal.bundle main).
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_track_a_droplet.ps1 -Target root@164.90.x.x
#
# Does: transfer bundle + driver, run the full validation remotely
# (bootstrap, gates, 18 sessions), pull artifacts back, remind to destroy.

param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [string]$Commit = ""
)

$ErrorActionPreference = "Stop"

if (-not $env:OPENAI_API_KEY) {
    Write-Error "OPENAI_API_KEY is not set in this PowerShell session."
    exit 1
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$bundle = "C:\Users\zjohn\Projects\apu_bare_metal.bundle"
if (-not (Test-Path $bundle)) {
    Write-Error "Bundle not found at $bundle. Create it: git bundle create $bundle main"
    exit 1
}

if (-not $Commit) {
    $Commit = (git -C $repo rev-parse main).Trim()
}
Write-Host "Commit for the droplet run: $Commit"

Write-Host "Transferring bundle (156 MB) and driver to $Target ..."
scp $bundle "$repo\apu_characterization\run_bare_metal_native.sh" "${Target}:"
if ($LASTEXITCODE -ne 0) { Write-Error "scp failed"; exit 1 }

Write-Host "Running validation on the droplet (bootstrap + gates + 18 sessions, 1-2 h) ..."
# Key passed via stdin-safe env assignment on the remote; never echoed.
$remoteCmd = "export OPENAI_API_KEY='" + ($env:OPENAI_API_KEY -replace "'", "'\''") + "'; " +
    "tr -d '\r' < run_bare_metal_native.sh > run_native.sh; " +
    "bash run_native.sh ~/apu_bare_metal.bundle $Commit"
ssh $Target $remoteCmd
if ($LASTEXITCODE -ne 0) { Write-Error "remote run failed (exit $LASTEXITCODE)"; exit 1 }

Write-Host "Pulling artifacts back ..."
$outDir = "$repo\apu_characterization\out"
$pull = "scp ${Target}:apu_bare_metal/apu_characterization/out/bare_metal_validation_*.json ${Target}:apu_bare_metal/apu_characterization/out/bare_metal_validation_*.md ${Target}:apu_bare_metal/apu_characterization/out/setup.json $outDir\"
Invoke-Expression $pull
if ($LASTEXITCODE -ne 0) {
    Write-Warning "wildcard scp failed; trying native_vm filenames"
    scp "${Target}:apu_bare_metal/apu_characterization/out/bare_metal_validation_native_vm.json" $outDir\
    scp "${Target}:apu_bare_metal/apu_characterization/out/bare_metal_validation_native_vm.md" $outDir\
}
Copy-Item -Force "$outDir\setup.json" "$outDir\setup_native_vm.json" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1. python apu_characterization/tools/bare_metal_compare.py"
Write-Host "  2. DESTROY THE DROPLET in the DigitalOcean console (billing stops)."
