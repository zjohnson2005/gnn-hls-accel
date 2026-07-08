#!/usr/bin/env bash
# Phase D: v3 replication (thread-identity measured attribution).
#
# Prerequisites: bash apu_characterization/run_wsl_bootstrap.sh
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_linux_replication_v3.sh [--allow-dirty]
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
VENV="${REPO}/.venv-wsl"

# /mnt/c/ checkouts: WSL git needs autocrlf or every file looks modified.
git config core.autocrlf true 2>/dev/null || true

_on_replicate_exit() {
  local code=$?
  if [[ -f "${REPO}/apu_characterization/out/replicate_v3.state.json" ]]; then
    if [[ -x "${VENV}/bin/python" ]]; then
      "${VENV}/bin/python" "${REPO}/apu_characterization/tools/apu_replicate_finish_state.py" "${code}" || true
    else
      python3 "${REPO}/apu_characterization/tools/apu_replicate_finish_state.py" "${code}" || true
    fi
  fi
}
trap _on_replicate_exit EXIT

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
  echo "ERROR: ${VENV} missing. Run: bash apu_characterization/run_wsl_bootstrap.sh" >&2
  exit 1
fi

echo "=== pre-flight (git clean — no calibration/setup writes yet) ==="
"${PY}" -m apu_characterization.setup_validate

echo "=== calibration (mock backend false step-infer rate) ==="
"${PY}" -m apu_characterization.experiments.step_infer_calibration

echo "=== WSL v3 replication (thread-identity, instr-version 3) ==="
"${PY}" -m apu_characterization.tests.test_resolution
"${PY}" -m apu_characterization.tests.test_attribution_provenance
"${PY}" -m apu_characterization.capture_setup

echo "=== post-capture setup check (ignore driver-refreshed paths) ==="
"${PY}" -c "from apu_characterization.setup_validate import GIT_IGNORE_RUNTIME_REFRESH, load_and_validate; load_and_validate(ignore_dirty_paths=GIT_IGNORE_RUNTIME_REFRESH); print('post-capture setup OK')"

ALLOW=""
if [[ "${1:-}" == "--allow-dirty" ]]; then
  ALLOW="--allow-dirty"
fi

"${PY}" -m apu_characterization.experiments.replication_batch \
  --backend openai --seeds 0,1,2,3,4 --search-locality remote \
  --instr-version 3 ${ALLOW}

echo "=== validate ==="
"${PY}" apu_characterization/tools/validate_publishable.py \
  apu_characterization/out/replication_remote_search_v3.json

echo "=== done ==="
