#!/usr/bin/env bash
# Build and run oe_bench; capture log for Phase 2 gate. Run on Vitis box (g++).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash orchestration_engine/build.sh

OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

BENCH="$ROOT/orchestration_engine/build/oe_bench"
"$BENCH" 4 2 42 | tee "$OUT/oe_bench.log"
"$BENCH" 100 2 42 >> "$OUT/oe_bench.log"

python3 -m orchestration_engine.phase2_gate.gate_report

echo "Wrote $OUT/oe_bench.log and refreshed phase2_gate.md"
