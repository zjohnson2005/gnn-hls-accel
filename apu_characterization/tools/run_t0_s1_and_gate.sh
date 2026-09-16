#!/usr/bin/env bash
# Freeze schema, extract S1, run tlp unit tests (no live S2).
set -euo pipefail
REPO="/mnt/c/Users/zjohn/Projects/gnn-hls-accel"
cd "$REPO"
# shellcheck source=/dev/null
source "$REPO/.venv-wsl/bin/activate"
export PYTHONPATH="$REPO"

echo "=== SCHEMA FREEZE ==="
python apu_characterization/tools/freeze_tlp01_schema.py

echo "=== S1 EXTRACT ==="
python apu_characterization/tools/extract_tlp01_s1.py

echo "=== TLP UNIT TESTS ==="
python -m pytest -q apu_characterization/tests/tlp01

echo "=== T0 S1+GATE PREP OK ==="
