#!/usr/bin/env bash
# Phase 2 deferred artifacts (run in tmux on ece-rschsrv).
# LightningSim proof requires C1 + C2 with trace-backed DSE (no synthetic shortcuts).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

if [[ -z "${CONDA_PREFIX:-}" ]] && [[ -d "$HOME/miniconda3/envs/fifo-advisor" ]]; then
  export CONDA_PREFIX="$HOME/miniconda3/envs/fifo-advisor"
fi

PY="${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}"
PY="${PY:-python3}"

_run() {
  echo ""
  echo "========== $1 =========="
  shift
  "$@"
}

_c1_passed() {
  "$PY" -c "
import json, sys
from pathlib import Path
p = Path('$OUT/ls_validation.json')
if not p.is_file(): sys.exit(1)
d = json.loads(p.read_text())
sys.exit(0 if d.get('c1_passed') else 1)
" 2>/dev/null
}

_c2_passed() {
  "$PY" -c "
import json, sys
from pathlib import Path
from orchestration_engine.phase2_gate.ls_gate import dse_report_valid
ok, _ = dse_report_valid(Path('$OUT/dse_report_oe.json'))
if not ok: sys.exit(1)
p = Path('$OUT/ls_validation.json')
if not p.is_file(): sys.exit(1)
d = json.loads(p.read_text())
sys.exit(0 if d.get('c2_passed') else 1)
" 2>/dev/null
}

# E1
if [[ ! -f "$ROOT/cost_model_3d/out/oe_experiment.json" ]]; then
  _run "E1 OE 3D cost model" bash orchestration_engine/run_oe_cost_model_3d.sh
else
  echo "SKIP E1 ($ROOT/cost_model_3d/out/oe_experiment.json exists)"
fi

# C1 — required
if ! _c1_passed; then
  _run "C1 LightningSim vs Vitis (GCN)" bash orchestration_engine/run_ls_validate_gcn.sh
else
  echo "SKIP C1 (c1_passed in ls_validation.json)"
fi

# C2 — required
if ! _c2_passed; then
  _run "C2 OE LightningSim DSE + pairing" bash orchestration_engine/run_phase2_lightningsim_oe.sh
else
  echo "SKIP C2 (c2_passed + valid dse_report_oe.json)"
  "$PY" -m orchestration_engine.eval.ls_validate --mode ls_lite
fi

# C3
if [[ ! -f "$OUT/variants_results.json" ]]; then
  _run "C3 variant csynth" bash orchestration_engine/run_phase2_variants.sh --limit 6
else
  echo "SKIP C3 ($OUT/variants_results.json exists)"
fi

# B2 scaffold (non-blocking)
if grep -q 'pending_impl' "$OUT/power_scatter.json" 2>/dev/null; then
  _run "B2 Vivado power scaffold" bash orchestration_engine/run_power_vivado.sh all || true
else
  echo "SKIP B2 (power JSONs not placeholders or missing)"
fi

"$PY" -m orchestration_engine.phase2_gate.gate_report

echo ""
echo "Deferred pass done. See $OUT/phase2_gate.md"
