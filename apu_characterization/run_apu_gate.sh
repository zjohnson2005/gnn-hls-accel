#!/usr/bin/env bash
# Fail-fast gate: WSL bootstrap (if needed) + unit tests + FO-01 OpenAI smoke.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_apu_gate.sh
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"
# shellcheck source=apu_env.sh
source "$(dirname "$0")/apu_env.sh"

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
else
  cd "$(dirname "$0")/.."
  REPO="$(pwd)"
fi
cd "${REPO}"

git config core.autocrlf true 2>/dev/null || true

VENV="${REPO}/.venv-wsl"

if [[ -z "${OPENAI_API_KEY:-}" ]] && command -v powershell.exe >/dev/null 2>&1; then
  WIN_KEY="$(powershell.exe -NoProfile -Command '$env:OPENAI_API_KEY' 2>/dev/null | tr -d '\r\n')"
  if [[ -n "${WIN_KEY}" ]]; then
    export OPENAI_API_KEY="${WIN_KEY}"
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set (required for FO-01 smoke)." >&2
  exit 1
fi

if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "=== venv missing — running bootstrap ==="
  bash apu_characterization/run_wsl_bootstrap.sh
else
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
  echo "=== unit tests (gate) ==="
  python -m apu_characterization.tests.test_resolution
  python -m apu_characterization.tests.test_instr
  python -m apu_characterization.tests.test_reconcile_worker
  python -m apu_characterization.tests.test_attribution_provenance
fi

echo "=== FO-01 smoke (OpenAI fan-out) ==="
bash apu_characterization/run_v3_fo01_smoke_wsl.sh

echo "=== apu-gate OK ==="
