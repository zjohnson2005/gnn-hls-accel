# Build orchestration_engine software sim + benchmarks (local, no Vitis).
# Linux/macOS: bash orchestration_engine/build.sh
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Root "build"
$Inc = @("-I", (Join-Path $Root "include"), "-I", (Join-Path $Root "software"))
$Std = @("-std=c++17")
$Common = @(
    (Join-Path $Root "software/engine_sim.cpp"),
    (Join-Path $Root "software/cpu_baseline.cpp"),
    (Join-Path $Root "software/workload_gen.cpp")
)

New-Item -ItemType Directory -Force -Path $Build | Out-Null

g++ @Std @Inc -o (Join-Path $Build "oe_sim_tb.exe") @Common (Join-Path $Root "tb/oe_sim_tb.cpp")
g++ @Std @Inc -o (Join-Path $Build "oe_bench.exe") @Common (Join-Path $Root "software/main_bench.cpp")

Write-Host "Built: $Build/oe_sim_tb.exe, $Build/oe_bench.exe"
