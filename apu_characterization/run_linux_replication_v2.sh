#!/usr/bin/env bash
# Phase C: v2 replication (thread hooks + RESIDUAL_UNATTRIBUTED gate).
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_wsl_bootstrap.sh   # once
#   bash apu_characterization/run_linux_replication_v2.sh [--allow-dirty]
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."
REPO="$(pwd)"
VENV="${REPO}/.venv-wsl"

if [[ -z "${OPENAI_API_KEY:-}" ]] && command -v powershell.exe >/dev/null 2>&1; then
  WIN_KEY="$(powershell.exe -NoProfile -Command '$env:OPENAI_API_KEY' 2>/dev/null | tr -d '\r\n')"
  if [[ -n "${WIN_KEY}" ]]; then
    export OPENAI_API_KEY="${WIN_KEY}"
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set." >&2
  exit 1
fi

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
  PY="${VENV}/bin/python"
else
  PY="python3"
fi

echo "=== WSL v2 replication (instr-version 2) ==="
echo "platform: $(uname -s), python: $("${PY}" --version)"

"${PY}" -m apu_characterization.tests.test_resolution
"${PY}" -m apu_characterization.tests.test_instr
"${PY}" -m apu_characterization.capture_setup

ALLOW=""
if [[ "${1:-}" == "--allow-dirty" ]]; then
  ALLOW="--allow-dirty"
fi

"${PY}" -m apu_characterization.experiments.replication_batch \
  --backend openai --seeds 0,1,2,3,4 --search-locality remote \
  --instr-version 2 ${ALLOW}

echo "=== migration report ==="
"${PY}" apu_characterization/tools/replication_v2_compare.py

echo "=== validate v2 ==="
"${PY}" apu_characterization/tools/validate_publishable.py \
  apu_characterization/out/replication_remote_search_v2.json

echo "=== done ==="
