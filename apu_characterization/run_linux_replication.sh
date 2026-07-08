#!/usr/bin/env bash
# Run publishable Linux replication in WSL (audit must pass).
# Usage:
#   export OPENAI_API_KEY=sk-...   # required (WSL does not inherit PowerShell session vars)
#   bash apu_characterization/run_linux_replication.sh --allow-dirty
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."

if [[ -z "${OPENAI_API_KEY:-}" ]] && command -v powershell.exe >/dev/null 2>&1; then
  WIN_KEY="$(powershell.exe -NoProfile -Command '$env:OPENAI_API_KEY' 2>/dev/null | tr -d '\r\n')"
  if [[ -n "${WIN_KEY}" ]]; then
    export OPENAI_API_KEY="${WIN_KEY}"
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set. In PowerShell before running the .ps1 script:" >&2
  echo '  $env:OPENAI_API_KEY = "sk-..."' >&2
  exit 1
fi

echo "=== WSL replication starting (platform: $(uname -s), OPENAI_API_KEY: set) ==="

echo "=== platform ==="
python3 -m apu_characterization.tests.test_resolution
python3 -m apu_characterization.tests.test_inst

echo "=== capture ==="
python3 -m apu_characterization.capture_setup

ALLOW=""
if [[ "${1:-}" == "--allow-dirty" ]]; then
  ALLOW="--allow-dirty"
fi

echo "=== replication remote only (n=5 seeds, locality_ablation 4KB cap) ==="
python3 -m apu_characterization.experiments.replication_batch \
  --backend openai --seeds 0,1,2,3,4 --search-locality remote ${ALLOW}

echo "=== done (50 OpenAI sessions: 10 tasks x 5 seeds) ==="
