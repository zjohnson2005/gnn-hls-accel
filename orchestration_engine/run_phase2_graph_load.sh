#!/usr/bin/env bash
# Graph load csynth + cosim (session-load measured cycles). Server-only (Vitis 2025.2.1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source "$ROOT/orchestration_engine/hls_env.sh"

echo "=== graph_load csynth + cosim (50-node TB) ==="
rm -rf oe_graph_load_proj
vitis_hls -f orchestration_engine/run_hls_graph_load.tcl

RPT="$(find oe_graph_load_proj -name 'oe_hls_graph_load_cosim.rpt' | head -1)"
if [[ -z "$RPT" ]]; then
  RPT="$(find oe_graph_load_proj -name '*_cosim.rpt' | head -1)"
fi
echo "graph_load cosim report: $RPT"

mkdir -p orchestration_engine/characterization/out/phase2

if [[ -n "$RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$RPT" \
    --out orchestration_engine/characterization/out/phase2/cosim_graph_load.json \
    --nodes-loaded 50 \
    --ops-processed 103
fi

python3 -m orchestration_engine.phase2_gate.gate_report --refresh
echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
