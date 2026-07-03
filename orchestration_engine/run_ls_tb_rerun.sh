#!/usr/bin/env bash
# Re-run the last LS instrumented testbench outside LightningSim (gdb/ldd friendly).
#
# Usage (after a failed ls_probe):
#   bash orchestration_engine/run_ls_tb_rerun.sh
#   bash orchestration_engine/run_ls_tb_rerun.sh /tmp/lightningsim.hpycznov/testbench_gcn_layer_stream
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/ls_probe.log"
TB="${1:-}"

if [[ -z "$TB" ]]; then
  ART="$(grep -oE 'Build artifacts are being written to \S+' "$LOG" 2>/dev/null | tail -1 | awk '{print $NF}')"
  TB="$(ls "${ART:-/nonexistent}"/testbench_* 2>/dev/null | head -1)"
fi

if [[ ! -x "$TB" ]]; then
  echo "ERROR: testbench binary not found. Pass path or run ls_probe first."
  echo "  tried: ${TB:-<empty>}"
  exit 1
fi

export CONDA_PREFIX="${CONDA_PREFIX:-$HOME/miniconda3/envs/fifo-advisor}"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OE_CONDA_LIB="${CONDA_PREFIX}/lib"
ART_DIR="$(dirname "$TB")"

echo "=== ldd libstdc++ ==="
ldd "$TB" | grep -E 'libstdc\+\+|not found' || true

echo
echo "=== run (no trace fd) ==="
( cd "$ART_DIR" && "$TB" )
echo "exit=$?"

echo
echo "=== run (HLSLITESIM_TRACE_FD=9) ==="
( cd "$ART_DIR" && HLSLITESIM_TRACE_FD=9 "$TB" 9>/dev/null )
echo "exit=$?"

if command -v gdb >/dev/null 2>&1; then
  echo
  echo "=== gdb backtrace ==="
  ( cd "$ART_DIR" && HLSLITESIM_TRACE_FD=9 gdb -batch -ex run -ex 'bt 25' "$TB" 9>/dev/null ) || true
fi
