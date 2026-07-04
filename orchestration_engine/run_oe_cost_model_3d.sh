#!/usr/bin/env bash
# OE 3D cost-model experiment. Needs Python >= 3.7 (dataclasses).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  PY="$CONDA_PREFIX/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PY=python3.12
elif command -v python3.11 >/dev/null 2>&1; then
  PY=python3.11
elif command -v python3.10 >/dev/null 2>&1; then
  PY=python3.10
else
  PY=python3
fi

ver="$("$PY" -c 'import sys; print(sys.version_info[:2])')"
if "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)'; then
  :
else
  echo "ERROR: cost_model_3d needs Python 3.7+ (system python3 is $ver)."
  echo "Use: conda activate fifo-advisor && bash orchestration_engine/run_oe_cost_model_3d.sh"
  exit 1
fi

"$PY" -m cost_model_3d.oe_kernel_graph
