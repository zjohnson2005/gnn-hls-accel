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
CUR_VER="$(command -v vitis_hls | grep -oE '20[0-9]{2}\.[0-9]+' | head -1)"
OLD_VER="$(grep -oE '20[0-9]{2}\.[0-9]+' "$STAMP" 2>/dev/null | head -1 || true)"
if [[ ! -f "$ROOT/gcn_stream_proj/sol1/syn/report/gcn_layer_stream_csynth.rpt" ]] \
   || [[ -z "$OLD_VER" ]] || [[ "$CUR_VER" != "$OLD_VER" ]]; then
  echo "=== Rebuilding gcn_stream_proj with Vitis $CUR_VER (was: ${OLD_VER:-unknown}) ==="
  rm -rf "$ROOT/gcn_stream_proj"
  vitis_hls -f run_hls_stream_ls.tcl || exit 1
  mkdir -p "$ROOT/gcn_stream_proj/sol1"
  echo "$(command -v vitis_hls) via ${OE_LS_VITIS_SETTINGS64:-PATH}" > "$STAMP"
  ln -sfn sol1 "$ROOT/gcn_stream_proj/solution1"
fi

rm -f "$ROOT/gcn_stream_proj/sol1/trace.pkl"
"$PY" -m orchestration_engine.eval.ls_probe "$ROOT/gcn_stream_proj/sol1"

echo
echo "=== gdb backtrace (only if instrumented testbench crashed) ==="
ART="$(grep -oE 'Build artifacts are being written to \S+' "$LOG" | tail -1 | awk '{print $NF}')"
TB_BIN="$(ls "${ART:-/nonexistent}"/testbench_* 2>/dev/null | head -1)"
if grep -qE 'testbench exit code: -' "$LOG" && [[ -n "$TB_BIN" ]]; then
  if command -v gdb >/dev/null 2>&1; then
    ( cd "$ART" && HLSLITESIM_TRACE_FD=9 gdb -batch -ex run -ex "bt 25" "$TB_BIN" 9>/dev/null 2>&1 | tail -45 )
  else
    echo "(gdb not available; falling back to core-less rerun under catchsegv/ltrace if present)"
    ( cd "$ART" && HLSLITESIM_TRACE_FD=9 "$TB_BIN" 9>/dev/null; echo "manual rerun rc=$?" )
  fi
else
  echo "(testbench did not crash, or artifacts dir not found: ART=${ART:-none})"
fi

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
