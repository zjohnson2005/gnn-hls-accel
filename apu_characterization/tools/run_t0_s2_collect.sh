#!/usr/bin/env bash
# S2 live collection — requires OPENAI_API_KEY in the environment.
set -euo pipefail
REPO="/mnt/c/Users/zjohn/Projects/gnn-hls-accel"
cd "$REPO"
# shellcheck source=/dev/null
source "$REPO/.venv-wsl/bin/activate"
export PYTHONPATH="$REPO"

key_len="${#OPENAI_API_KEY}"
if [[ -z "${OPENAI_API_KEY:-}" || "${key_len}" -lt 20 ]]; then
  echo "OPENAI_API_KEY missing or invalid (len=${key_len}); refuse S2 collection" >&2
  exit 2
fi

echo "=== S2 COLLECT (50 sessions) ==="
python apu_characterization/tools/collect_tlp01_s2.py --max-sessions 50 --attempt-budget 120

echo "=== T0 CLOSE ==="
python apu_characterization/tools/close_tlp01_t0.py

echo "=== T0 S2 COMPLETE ==="
