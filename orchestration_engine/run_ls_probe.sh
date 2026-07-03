#!/usr/bin/env bash
# Probe why LightningSim reports "kernel did not run" on gcn_stream:
# dump the instrumented testbench's exit code + stdout, all build subprocess
# results, and the kernel-related symbols in the kept testbench object.
#
# Usage (inside fifo-advisor conda env):
#   bash orchestration_engine/run_ls_probe.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="$ROOT/ls_probe.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

PY="${CONDA_PREFIX:-$HOME/miniconda3/envs/fifo-advisor}/bin/python"

# shellcheck disable=SC1091
if ! source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"; then
  exit 1
fi
export PATH="$(dirname "$PY"):$PATH"
echo "XILINX_HLS=${XILINX_HLS:-unset}"

# Vitis 2023.2+ compat: make LS find generated headers (hls_signal_handler.h).
"$PY" -m orchestration_engine.eval.patch_lightningsim "$ROOT/gcn_stream_proj/sol1" || exit 1

# If the env fell back to a different Vitis version than the one that built
# the project, the bitcode is stale — rebuild (csim + csynth only, ~10 min).
STAMP="$ROOT/gcn_stream_proj/sol1/.oe_lightningsim_vitis"
STAMP_TAG="GNN_LS_LITE=ptr512"
CUR_VER="$(command -v vitis_hls | grep -oE '20[0-9]{2}\.[0-9]+' | head -1)"
OLD_STAMP="$(cat "$STAMP" 2>/dev/null || true)"
if [[ ! -f "$ROOT/gcn_stream_proj/sol1/syn/report/gcn_layer_stream_csynth.rpt" ]] \
   || [[ "$OLD_STAMP" != *"$CUR_VER"* ]] || [[ "$OLD_STAMP" != *"$STAMP_TAG"* ]]; then
  echo "=== Rebuilding gcn_stream_proj with Vitis $CUR_VER ($STAMP_TAG) ==="
  rm -rf "$ROOT/gcn_stream_proj"
  if ! vitis_hls -f run_hls_stream_ls.tcl; then
    echo ""
    echo "ERROR: vitis_hls rebuild failed with $CUR_VER."
    echo "Try pinning a known-good version, then re-run:"
    echo "  export OE_LS_VITIS_VERSION=2023.1"
    echo "  bash orchestration_engine/run_ls_probe.sh"
    exit 1
  fi
  mkdir -p "$ROOT/gcn_stream_proj/sol1"
  echo "$(command -v vitis_hls) $STAMP_TAG via ${OE_LS_VITIS_SETTINGS64:-PATH}" > "$STAMP"
  ln -sfn sol1 "$ROOT/gcn_stream_proj/solution1"
fi

rm -f "$ROOT/gcn_stream_proj/sol1/trace.pkl"
"$PY" -m orchestration_engine.eval.ls_bitcode_inspect "$ROOT/gcn_stream_proj/sol1" || true
"$PY" -m orchestration_engine.eval.ls_probe "$ROOT/gcn_stream_proj/sol1"
RC=$?
ART="$(grep -oE 'Build artifacts are being written to \S+' "$LOG" | tail -1 | awk '{print $NF}')"
TMPD="$(grep -oE 'Intermediate objects are being written to \S+' "$LOG" | tail -1 | awk '{print $NF}')"
TB_BIN="$(ls "${ART:-/nonexistent}"/testbench_* 2>/dev/null | head -1)"
if [[ "$RC" -ne 0 ]] || grep -qE 'testbench exit code: -(11|6|8)' "$LOG"; then
  "$PY" -m orchestration_engine.eval.ls_crash_diag \
    "$ROOT/gcn_stream_proj/sol1" "${ART:-}" "${TMPD:-}" "${TB_BIN:-}" || true
fi

echo
echo "=== kernel symbols in kept testbench objects (post-objcopy) ==="
if [[ -n "${TMPD:-}" ]] && [[ -d "$TMPD" ]]; then
  echo "tempdir: $TMPD"
  for obj in "$TMPD"/testbench.*.o; do
    [[ -f "$obj" ]] || continue
    echo "--- $obj ---"
    nm "$obj" 2>/dev/null | grep -iE "gcn_layer_stream|apatb|FifoRead|FifoWrite" || echo "(no matching symbols)"
  done
  echo "--- fifo support IR (if generated) ---"
  ls -la "$TMPD"/fifo_*.ll 2>/dev/null || echo "(no fifo_*.ll — LS FIFO template may not have matched)"
else
  echo "(tempdir not found in log)"
fi

echo
echo "Log written to $LOG"
exit "$RC"
