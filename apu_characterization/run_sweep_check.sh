#!/usr/bin/env bash
# Poll background c-ladder sweep; validate audit when done.
#
#   bash apu_characterization/run_sweep_check.sh
#   bash apu_characterization/run_sweep_check.sh --validate
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
elif [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != bash && -f "${BASH_SOURCE[0]}" ]]; then
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
else
  REPO="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "${REPO}"

VENV="${REPO}/.venv-wsl"
if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
fi

python apu_characterization/tools/sweep_status.py "$@"
