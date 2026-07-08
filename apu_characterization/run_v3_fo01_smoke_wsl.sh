#!/usr/bin/env bash
# Phase 1 smoke: FO-01 fan-out session (OpenAI, instr v3, ~2-5 min).
#
# Gates residual-provenance < 15% on the single session before a full replication.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_v3_fo01_smoke_wsl.sh
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

if [[ -f "${REPO}/.venv-wsl/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${REPO}/.venv-wsl/bin/activate"
else
  echo "Run bash apu_characterization/run_wsl_bootstrap.sh first." >&2
  exit 1
fi

echo "=== v3 unit tests (attribution) ==="
python -m apu_characterization.tests.test_attribution_provenance

echo "=== FO-01 OpenAI smoke (fanout profile, seed 1) ==="
python -m apu_characterization.experiments.real_agent_breakdown \
  --backend openai --profile fanout --seed 1 --sessions 1 \
  --search-locality remote --instr-version 3 --allow-dirty

echo "=== residual gate on FO-01 session ==="
python apu_characterization/tools/check_v3_session_residual.py \
  apu_characterization/out/real_agent_breakdown_remote_search.json FO-01

echo "=== FO-01 smoke OK ==="
