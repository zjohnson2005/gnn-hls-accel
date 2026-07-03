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

rm -f "$ROOT/gcn_stream_proj/sol1/trace.pkl"
"$PY" -m orchestration_engine.eval.ls_probe "$ROOT/gcn_stream_proj/sol1"

echo
echo "=== kernel symbols in kept testbench objects (post-objcopy) ==="
TMPD="$(grep -oE 'Intermediate objects are being written to \S+' "$LOG" | tail -1 | awk '{print $NF}')"
if [[ -n "${TMPD:-}" ]] && [[ -d "$TMPD" ]]; then
  echo "tempdir: $TMPD"
  for obj in "$TMPD"/testbench.*.o; do
    [[ -f "$obj" ]] || continue
    echo "--- $obj ---"
    nm "$obj" 2>/dev/null | grep -iE "gcn_layer_stream|apatb|FifoRead|FifoWrite" || echo "(no matching symbols)"
  done
  echo "--- linked bitcode objects ---"
  ls -la "$TMPD" | head -30
else
  echo "(tempdir not found in log)"
fi

echo
echo "Log written to $LOG"
