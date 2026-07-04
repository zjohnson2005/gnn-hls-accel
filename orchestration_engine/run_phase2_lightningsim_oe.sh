#!/usr/bin/env bash
# LightningSim FIFO DSE on OE engine (graph_load then scatter; axis FIFO trace).
# No synthetic fallbacks — trace capture failure is a hard error.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

if [[ -z "${CONDA_PREFIX:-}" ]] && [[ -d "$HOME/miniconda3/envs/fifo-advisor" ]]; then
  export CONDA_PREFIX="$HOME/miniconda3/envs/fifo-advisor"
fi

_oe_resolve_python() {
  local cand
  for cand in \
    "${OE_PYTHON:-}" \
    "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" \
    "$HOME/miniconda3/envs/fifo-advisor/bin/python" \
    "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$cand" ]] || continue
    [[ -x "$cand" ]] || continue
    if "$cand" -c "import fifo_advisor" 2>/dev/null; then
      echo "$cand"
      return 0
    fi
  done
  echo "ERROR: fifo-advisor not importable." >&2
  return 1
}

OE_PYTHON="$(_oe_resolve_python)" || exit 1
source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"
export PATH="$(dirname "$OE_PYTHON"):$PATH"

echo "Using python: $OE_PYTHON"

PROJ="oe_engine_ls_proj"
STAMP_TAG="OE_ENGINE_LS=df-array-v2"
SOLUTION_DIR="$ROOT/$PROJ/sol1"
CSYNTH_RPT="$SOLUTION_DIR/syn/report/oe_hls_engine_stream_csynth.rpt"
LS_STAMP="$SOLUTION_DIR/.oe_lightningsim_vitis"

if [[ -f "$CSYNTH_RPT" ]] && [[ -f "$LS_STAMP" ]] && grep -q "$STAMP_TAG" "$LS_STAMP"; then
  echo "Reusing $SOLUTION_DIR ($(cat "$LS_STAMP"))"
else
  echo "=== Building oe_hls_engine_stream for LightningSim ($STAMP_TAG) ==="
  rm -rf "$PROJ"
  vitis_hls -f orchestration_engine/run_hls_oe_engine_ls.tcl
  echo "$(command -v vitis_hls) $STAMP_TAG" > "$LS_STAMP"
fi

if [[ -d "$ROOT/$PROJ/sol1" ]] && [[ ! -e "$ROOT/$PROJ/solution1" ]]; then
  ln -sfn sol1 "$ROOT/$PROJ/solution1"
fi

"$OE_PYTHON" -m orchestration_engine.eval.patch_lightningsim "$SOLUTION_DIR"

if [[ ! -f "$SOLUTION_DIR/trace.pkl" ]]; then
  echo "=== Refresh csim + capture trace.pkl (required for real LS DSE) ==="
  vitis_hls -f orchestration_engine/run_hls_oe_engine_ls_csim_refresh.tcl
  if ! "$OE_PYTHON" -m orchestration_engine.eval.capture_ls_trace --solution-dir "$SOLUTION_DIR"; then
    echo ""
    echo "ERROR: OE engine trace capture failed. C2 cannot pass without trace.pkl." >&2
    echo "Fix DATAFLOW top / patch_lightningsim / csim on $SOLUTION_DIR" >&2
    echo "Do NOT use --synthetic or offline DSE for thesis artifacts." >&2
    exit 1
  fi
fi

echo "=== LightningSim FIFO DSE on $SOLUTION_DIR ==="
"$OE_PYTHON" -m orchestration_engine.eval.dse_sweep \
  --solution-dir "$SOLUTION_DIR" \
  --n-samples 500 \
  --batch-size 64 \
  --output "$OUT/dse_report_oe.json"

"$OE_PYTHON" -m orchestration_engine.eval.ls_capture_oe_eval
"$OE_PYTHON" -m orchestration_engine.eval.ls_validate --mode ls_lite
"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report --refresh

echo "Done. See $OUT/dse_report_oe.json and $OUT/ls_validation.json"
