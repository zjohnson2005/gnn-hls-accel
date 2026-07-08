#!/usr/bin/env bash
# Quick v3 smoke: 1 scripted session on Linux (no OpenAI).
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."
source .venv-wsl/bin/activate
python -m apu_characterization.experiments.real_agent_breakdown \
  --backend scripted --profile mixed --seed 0 --sessions 1 \
  --search-locality remote --instr-version 3 --allow-dirty
echo "smoke OK"
