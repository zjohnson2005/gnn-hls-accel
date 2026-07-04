#!/usr/bin/env bash
# Phase 2 deferred artifacts (run in tmux on ece-rschsrv).
# Skips steps whose output files already exist.
#
# Toolchain split (do not mix):
#   E1 cost model     — conda python 3.7+ (any host)
#   C1 LS validate    — Vitis 2023.1 ARCHIVE + conda
#   C2 OE LS+DSE      — Vitis 2023.1 ARCHIVE + conda
#   C3 variants       — Vitis 2025.2.1 csynth
#   B2 Vivado power   — Vitis 2025.2.1 export scaffold
#   fifo_pareto demo  — conda (optional)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

if [[ -z "${CONDA_PREFIX:-}" ]] && [[ -d "$HOME/miniconda3/envs/fifo-advisor" ]]; then
  export CONDA_PREFIX="$HOME/miniconda3/envs/fifo-advisor"
fi

_run() {
  echo ""
  echo "========== $1 =========="
  shift
  "$@"
}

# E1 — local / conda python (no vitis_hls)
if [[ ! -f "$ROOT/cost_model_3d/out/oe_experiment.json" ]]; then
  _run "E1 OE 3D cost model" bash orchestration_engine/run_oe_cost_model_3d.sh
else
  echo "SKIP E1 ($ROOT/cost_model_3d/out/oe_experiment.json exists)"
fi

# C1 — strict GNN_LS_LITE pairing (optional; long cosim on 2023.1)
if [[ ! -f "$OUT/ls_validation.json" ]] || ! python3 -c \
  "import json; d=json.load(open('$OUT/ls_validation.json')); exit(0 if d.get('passed') else 1)" 2>/dev/null; then
  _run "C1 LS validate GCN" bash orchestration_engine/run_ls_validate_gcn.sh || \
    echo "WARN: C1 incomplete (cosim or pairing); continuing deferred pipeline"
else
  echo "SKIP C1 (ls_validation.json passed)"
fi

# C2 — OE engine LightningSim DSE
if [[ ! -f "$OUT/dse_report_oe.json" ]]; then
  _run "C2 OE LightningSim DSE" bash orchestration_engine/run_phase2_lightningsim_oe.sh
else
  echo "SKIP C2 ($OUT/dse_report_oe.json exists)"
  # Refresh ls_validation scatter row if C2 landed after C1
  if [[ -f "$OUT/ls_validation.json" ]]; then
    PY="${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}"
    PY="${PY:-python3}"
    "$PY" -m orchestration_engine.eval.ls_validate --mode ls_lite || true
  fi
fi

# C3 — variant csynth subset (default 6 points)
if [[ ! -f "$OUT/variants_results.json" ]]; then
  _run "C3 variant csynth" bash orchestration_engine/run_phase2_variants.sh --limit 6
else
  echo "SKIP C3 ($OUT/variants_results.json exists)"
fi

# B2 — Vivado power scaffold (RTL path metadata)
if grep -q 'pending_impl' "$OUT/power_scatter.json" 2>/dev/null; then
  _run "B2 Vivado power scaffold" bash orchestration_engine/run_power_vivado.sh all || true
else
  echo "SKIP B2 (power JSONs not placeholders or missing)"
fi

# fifo_pareto offline demo (methodology; no Vitis)
if [[ ! -f "$OUT/fifo_pareto_demo.json" ]]; then
  _run "fifo_pareto synthetic demo" bash -c '
    PY="${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}"
    PY="${PY:-python3}"
    "$PY" -m fifo_pareto.live_demo --synthetic small --n-samples 500 --save "'"$OUT"'/fifo_pareto.png" --export "'"$OUT"'/fifo_pareto_demo.json"
  '
else
  echo "SKIP fifo_pareto ($OUT/fifo_pareto_demo.json exists)"
fi

python3 -m orchestration_engine.phase2_gate.gate_report

echo ""
echo "Deferred pass done. See $OUT/phase2_gate.md"
