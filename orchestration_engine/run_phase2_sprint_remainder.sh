#!/usr/bin/env bash
# Remaining Phase 2 sprint artifacts (ece-rschsrv). Run inside tmux.
# Skips steps whose output JSON/log already exists.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

_run() {
  echo ""
  echo "========== $1 =========="
  shift
  "$@"
}

if [[ ! -f "$OUT/oe_bench.log" ]]; then
  _run "A1 oe_bench" bash orchestration_engine/run_oe_bench.sh
else
  echo "SKIP oe_bench ($OUT/oe_bench.log exists)"
fi

if [[ ! -f "$OUT/cosim_graph_load.json" ]]; then
  _run "B1 graph_load cosim" bash orchestration_engine/run_phase2_graph_load.sh
else
  echo "SKIP graph_load ($OUT/cosim_graph_load.json exists)"
fi

if [[ ! -f "$OUT/cosim_scatter_banked.json" ]]; then
  _run "B3 banked scatter cosim" bash orchestration_engine/run_phase2_scatter_banked.sh
else
  echo "SKIP banked scatter ($OUT/cosim_scatter_banked.json exists)"
fi

if [[ ! -f "$OUT/power_scatter.json" ]] || [[ ! -f "$OUT/power_graph_load.json" ]]; then
  _run "B2 power placeholders" bash orchestration_engine/run_power.sh all
else
  echo "SKIP power JSONs (already present)"
fi

if [[ -f "$OUT/cosim_graph_load.json" ]]; then
  python3 -m orchestration_engine.characterization.regen_cost_model
fi

python3 -m orchestration_engine.phase2_gate.gate_report

echo ""
echo "Sprint remainder done. See $OUT/phase2_gate.md"
