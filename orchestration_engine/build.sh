#!/usr/bin/env bash
# Build orchestration_engine software sim + oe_bench (local / Vitis box, no Vitis).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build"
INC=(-I "$ROOT/include" -I "$ROOT/software")
STD=(-std=c++17)
COMMON=(
  "$ROOT/software/engine_sim.cpp"
  "$ROOT/software/cpu_baseline.cpp"
  "$ROOT/software/workload_gen.cpp"
)

mkdir -p "$BUILD"

g++ "${STD[@]}" "${INC[@]}" -o "$BUILD/oe_sim_tb" \
  "${COMMON[@]}" "$ROOT/tb/oe_sim_tb.cpp"

g++ "${STD[@]}" "${INC[@]}" -o "$BUILD/oe_bench" \
  "${COMMON[@]}" "$ROOT/software/main_bench.cpp"

echo "Built: $BUILD/oe_sim_tb, $BUILD/oe_bench"
