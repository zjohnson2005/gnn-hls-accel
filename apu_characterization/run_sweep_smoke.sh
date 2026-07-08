#!/usr/bin/env bash
# Concurrency sweep smoke: single ladder level c=5, one seed, live OpenAI
# backend. Requires a CLEAN git tree: --allow-dirty is intentionally NOT
# passed, so a dirty tree fails loudly and the user must commit first.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_sweep_smoke.sh
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
# shellcheck source=apu_env.sh
source "${REPO}/apu_characterization/apu_env.sh"

git config core.autocrlf true 2>/dev/null || true

if [[ -z "${OPENAI_API_KEY:-}" ]] && command -v powershell.exe >/dev/null 2>&1; then
  WIN_KEY="$(powershell.exe -NoProfile -Command '$env:OPENAI_API_KEY' 2>/dev/null | tr -d '\r\n')"
  if [[ -n "${WIN_KEY}" ]]; then
    export OPENAI_API_KEY="${WIN_KEY}"
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set (required for the openai backend)." >&2
  exit 1
fi

VENV="${REPO}/.venv-wsl"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "=== venv missing: running bootstrap ==="
  bash apu_characterization/run_wsl_bootstrap.sh
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"

# Fail loudly on a dirty tree BEFORE spending API budget: the smoke is a
# publishable-pipeline check and must be reproducible from a commit.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: git tree is dirty. Commit all changes before running the sweep smoke." >&2
  echo "Dirty paths:" >&2
  git status --short >&2
  exit 1
fi

echo "=== BLAS pin ==="
python -c "from apu_characterization.env_pin import assert_blas_pinned; assert_blas_pinned()"

echo "=== sweep smoke (c=5, seed 0, openai, remote search) ==="
python -m apu_characterization.experiments.concurrency_sweep \
  --backend openai --levels 5 --seeds 0 --search-locality remote --no-saturate-stop

echo "=== validating audit ==="
python -c "
import json, sys
from pathlib import Path
p = Path('apu_characterization/out/concurrency_sweep.json')
d = json.loads(p.read_text())
audit = d.get('audit') or {}
if not audit.get('pass'):
    print('AUDIT FAIL:', audit.get('violations'))
    sys.exit(1)
print('audit pass:', d.get('result_validity'))
"

echo "=== sweep smoke OK ==="
