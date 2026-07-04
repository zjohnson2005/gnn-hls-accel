#!/usr/bin/env bash
# Banked scatter cosim. Server-only (ece-rschsrv, Vitis 2025.2.1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source "$ROOT/orchestration_engine/hls_env.sh"

echo "=== banked scatter csynth + cosim ==="
rm -rf oe_scatter_banked_proj
vitis_hls -f orchestration_engine/run_hls_scatter_banked.tcl

RPT="$(find oe_scatter_banked_proj -name '*_cosim.rpt' | head -1)"
mkdir -p orchestration_engine/characterization/out/phase2

if [[ -n "$RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$RPT" --fan-out 4 \
    --transactions 4 \
    --out orchestration_engine/characterization/out/phase2/cosim_scatter_banked.json
fi

python3 -m orchestration_engine.phase2_gate.gate_report --refresh
