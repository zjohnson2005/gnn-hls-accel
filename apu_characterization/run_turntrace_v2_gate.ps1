# TurnTrace v2 build and contract gate (Windows).
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$env:PYTHONPATH = $Repo

Write-Host "=== TurnTrace v2 Python gate ==="
py -3 -m pytest -q apu_characterization/tests/turntrace_v2
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== TurnTrace v2 protocol contract ==="
py -3 -c "from apu_characterization.turntrace_v2.contracts import PROTOCOL_VERSION, load_protocol, validate_protocol; protocol = load_protocol(); assert protocol['protocol_version'] == PROTOCOL_VERSION; assert not validate_protocol(protocol); print('protocol contract:', PROTOCOL_VERSION, 'OK')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== TurnTrace v2 D4 freeze ==="
py -3 -c "from apu_characterization.turntrace_v2.d4 import DEFAULT_CONFIGS, accept_against_truth, generate_corpus, run_d4_analysis; 
for cfg in DEFAULT_CONFIGS:
 r,t=generate_corpus(cfg); rep=run_d4_analysis(r, truth=t); f=accept_against_truth(rep); assert not f, (cfg.name,f)
print('D4 freeze OK', len(DEFAULT_CONFIGS))"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== TurnTrace v2 synthetic smoke ==="
py -3 -m apu_characterization.turntrace_v2.runner --synthetic-debug --out apu_characterization/out/turntrace_v2/_gate_smoke
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($env:TTV2_REQUIRE_CPU_DRYRUN -eq "1") {
  Write-Host "=== TurnTrace v2 CPU dry-run artifact check ==="
  $report = Get-Content apu_characterization/out/turntrace_v2/cpu_dryrun/cpu_dryrun_report.json -Raw | ConvertFrom-Json
  if (-not $report.provisional) { throw "cpu dryrun must be provisional" }
  if (-not $report.prefill_acceptance_passed) { throw "prefill gate failed" }
  if (-not $report.all_swaps_ok) { throw "swap replay failed" }
}

Write-Host "=== TurnTrace v2 gate OK ==="
