#!/usr/bin/env bash
# Finish Phase A3 after py-spy wrote speedscope but the shell script exited early.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."
REPO="$(pwd)"
VENV="${REPO}/.venv-wsl"
# shellcheck source=/dev/null
source "${VENV}/bin/activate"
PY="${VENV}/bin/python"
OUT="apu_characterization/out"
"${PY}" apu_characterization/tools/pyspy_bucketize.py \
  "${OUT}/pyspy_lh01.speedscope.json" --out "${OUT}/pyspy_lh01_buckets.md"
"${PY}" apu_characterization/tools/generate_attribution_verdict.py \
  --profile-json "${OUT}/profile_lh-01_s0.json" \
  --speedscope "${OUT}/pyspy_lh01.speedscope.json"
echo "verdict: ${OUT}/ATTRIBUTION_VERDICT.md"
