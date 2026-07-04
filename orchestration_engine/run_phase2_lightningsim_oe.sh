#!/usr/bin/env bash
# LightningSim FIFO DSE on OE engine (graph_load -> scatter DATAFLOW).
# Server-only: Vitis 2023.1 ARCHIVE + conda fifo-advisor.
#
#   cd ~/gnn-hls-accel && bash orchestration_engine/run_phase2_lightningsim_oe.sh
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
  echo "ERROR: fifo-advisor not importable. Set CONDA_PREFIX or OE_PYTHON." >&2
  return 1
}

OE_PYTHON="$(_oe_resolve_python)" || exit 1
source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"
export PATH="$(dirname "$OE_PYTHON"):$PATH"

echo "Using python: $OE_PYTHON"

PRIMARY_PROJ="oe_engine_ls_proj"
FALLBACK_PROJ="oe_stream_ls_proj"
STAMP_TAG="OE_ENGINE_LS=df-stream"
USE_FALLBACK=0
SOLUTION_DIR="$ROOT/$PRIMARY_PROJ/sol1"
CSYNTH_RPT="$SOLUTION_DIR/syn/report/oe_hls_engine_stream_csynth.rpt"
LS_STAMP="$SOLUTION_DIR/.oe_lightningsim_vitis"

_build_primary() {
  echo "=== Building oe_hls_engine_stream for LightningSim ($STAMP_TAG) ==="
  rm -rf "$PRIMARY_PROJ"
  vitis_hls -f orchestration_engine/run_hls_oe_engine_ls.tcl
  echo "$(command -v vitis_hls) $STAMP_TAG via ${OE_LS_VITIS_SETTINGS64:-PATH}" > "$LS_STAMP"
  SOLUTION_DIR="$ROOT/$PRIMARY_PROJ/sol1"
  CSYNTH_RPT="$SOLUTION_DIR/syn/report/oe_hls_engine_stream_csynth.rpt"
}

_build_fallback() {
  echo "=== Fallback: oe_hls_scatter_stream only ($FALLBACK_PROJ) ==="
  USE_FALLBACK=1
  rm -rf "$FALLBACK_PROJ"
  vitis_hls -f orchestration_engine/run_hls_oe_stream_ls.tcl
  SOLUTION_DIR="$ROOT/$FALLBACK_PROJ/sol1"
  CSYNTH_RPT="$SOLUTION_DIR/syn/report/oe_hls_scatter_stream_csynth.rpt"
  echo "$(command -v vitis_hls) OE_SCATTER_LS=stream via ${OE_LS_VITIS_SETTINGS64:-PATH}" \
    > "$SOLUTION_DIR/.oe_lightningsim_vitis"
}

if [[ -f "$CSYNTH_RPT" ]] && [[ -f "$LS_STAMP" ]] && grep -q "$STAMP_TAG" "$LS_STAMP"; then
  echo "Reusing $SOLUTION_DIR ($(cat "$LS_STAMP"))"
elif [[ ! -f "$CSYNTH_RPT" ]]; then
  if ! _build_primary; then
    _build_fallback
  fi
else
  echo "WARNING: rebuilding $PRIMARY_PROJ for LightningSim."
  if ! _build_primary; then
    _build_fallback
  fi
fi

_proj="${SOLUTION_DIR%%/sol1}"
if [[ -d "$_proj/sol1" ]] && [[ ! -e "$_proj/solution1" ]]; then
  ln -sfn sol1 "$_proj/solution1"
fi

"$OE_PYTHON" -m orchestration_engine.eval.patch_lightningsim "$SOLUTION_DIR" || exit 1

_csim_refresh() {
  if [[ "$USE_FALLBACK" -eq 1 ]]; then
    vitis_hls -f orchestration_engine/run_hls_oe_stream_ls_csim_refresh.tcl
  else
    vitis_hls -f orchestration_engine/run_hls_oe_engine_ls_csim_refresh.tcl
  fi
}

if [[ ! -f "$SOLUTION_DIR/trace.pkl" ]]; then
  echo "=== Refresh csim + capture trace.pkl ==="
  _csim_refresh
  if ! "$OE_PYTHON" -m orchestration_engine.eval.capture_ls_trace --solution-dir "$SOLUTION_DIR"; then
    echo ""
    echo "WARNING: OE engine trace capture failed."
    if [[ "$USE_FALLBACK" -eq 0 ]]; then
      echo "Retrying with scatter-only fallback..."
      _build_fallback
      "$OE_PYTHON" -m orchestration_engine.eval.patch_lightningsim "$SOLUTION_DIR" || exit 1
      _csim_refresh
      if ! "$OE_PYTHON" -m orchestration_engine.eval.capture_ls_trace --solution-dir "$SOLUTION_DIR"; then
        echo "Using offline synthetic DSE fallback."
        "$OE_PYTHON" -m orchestration_engine.eval.dse_sweep \
          --synthetic --n-samples 500 --batch-size 64 \
          --output "$OUT/dse_report_oe.json"
        exit 0
      fi
    else
      echo "Using offline synthetic DSE fallback."
      "$OE_PYTHON" -m orchestration_engine.eval.dse_sweep \
        --synthetic --n-samples 500 --batch-size 64 \
        --output "$OUT/dse_report_oe.json"
      exit 0
    fi
  fi
fi

echo "=== LightningSim FIFO DSE on OE engine ($SOLUTION_DIR) ==="
"$OE_PYTHON" -m orchestration_engine.eval.dse_sweep \
  --solution-dir "$SOLUTION_DIR" \
  --n-samples 500 \
  --batch-size 64 \
  --output "$OUT/dse_report_oe.json"

"$OE_PYTHON" -m orchestration_engine.eval.ls_validate --mode ls_lite
"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report --refresh

echo "Done. See $OUT/dse_report_oe.json"
