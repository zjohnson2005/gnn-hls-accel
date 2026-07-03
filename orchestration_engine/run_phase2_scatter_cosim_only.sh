#!/usr/bin/env bash
# Re-run scatter cosim only (dedicated project; standalone, ~2-5 min).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp ]]; then
  echo "ERROR: repo is stale. Run: git pull origin main"
  exit 1
fi

source "$ROOT/orchestration_engine/hls_env.sh"

echo "=== scatter cosim x4 for II (oe_scatter_cosim_proj) ==="
rm -rf oe_scatter_cosim_proj
vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl

COSIM_RPT="$(find oe_scatter_cosim_proj -name 'oe_hls_scatter_kernel_cosim.rpt' | head -1)"
echo "cosim report: $COSIM_RPT"

mkdir -p orchestration_engine/characterization/out/phase2
python3 -m orchestration_engine.phase2_gate.cosim_parser --report "$COSIM_RPT" --fan-out 2
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
