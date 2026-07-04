#!/usr/bin/env bash
# Probe LightningSim "kernel did not run" on oe_engine_ls_proj (C2).
#
#   bash orchestration_engine/run_ls_probe_oe.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="$ROOT/ls_probe_oe.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

PY="${CONDA_PREFIX:-$HOME/miniconda3/envs/fifo-advisor}/bin/python"
if [[ -z "${CONDA_PREFIX:-}" ]] && [[ -x "$HOME/miniconda3/envs/fifo-advisor/bin/python" ]]; then
  export CONDA_PREFIX="$HOME/miniconda3/envs/fifo-advisor"
fi

# shellcheck disable=SC1091
if ! source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"; then
  exit 1
fi
export PATH="$(dirname "$PY"):$PATH"

SOL="$ROOT/oe_engine_ls_proj/sol1"
STAMP_TAG="OE_ENGINE_LS=df-array-v4-no-sub-ifaces"

echo "=== OE engine LS probe ($STAMP_TAG) ==="
"$PY" -m orchestration_engine.eval.patch_lightningsim "$SOL" || exit 1

if [[ ! -f "$SOL/syn/report/oe_hls_engine_stream_csynth.rpt" ]]; then
  echo "Building oe_engine_ls_proj (csim + csynth)..."
  vitis_hls -f orchestration_engine/run_hls_oe_engine_ls.tcl || exit 1
  echo "$(command -v vitis_hls) $STAMP_TAG" > "$SOL/.oe_lightningsim_vitis"
  ln -sfn sol1 "$ROOT/oe_engine_ls_proj/solution1"
fi

echo "=== refresh csim ==="
vitis_hls -f orchestration_engine/run_hls_oe_engine_ls_csim_refresh.tcl || exit 1

rm -f "$SOL/trace.pkl"
"$PY" -m orchestration_engine.eval.ls_bitcode_inspect "$SOL" || true
"$PY" -m orchestration_engine.eval.ls_probe "$SOL"
RC=$?

ART="$(grep -oE 'Build artifacts are being written to \S+' "$LOG" | tail -1 | awk '{print $NF}')"
TMPD="$(grep -oE 'Intermediate objects are being written to \S+' "$LOG" | tail -1 | awk '{print $NF}')"
TB_BIN="$(ls "${ART:-/nonexistent}"/testbench_* 2>/dev/null | head -1)"
if [[ "$RC" -ne 0 ]] || grep -qE 'testbench exit code: -(11|6|8)' "$LOG"; then
  "$PY" -m orchestration_engine.eval.ls_crash_diag "$SOL" "${ART:-}" "${TMPD:-}" "${TB_BIN:-}" || true
fi

echo
echo "=== kernel symbols (post-objcopy) ==="
if [[ -n "${TMPD:-}" ]] && [[ -d "$TMPD" ]]; then
  for obj in "$TMPD"/testbench.*.o; do
    [[ -f "$obj" ]] || continue
    echo "--- $obj ---"
    nm "$obj" 2>/dev/null | grep -iE "oe_hls_engine_stream|apatb|FifoRead|FifoWrite" || echo "(no matching symbols)"
  done
fi

echo
echo "Log: $LOG"
exit "$RC"
