#!/usr/bin/env bash
# TLP-01 build and contract gate. Produces no experimental data.
set -euo pipefail

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
else
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "${REPO}"

if [[ -f "${REPO}/.venv-wsl/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${REPO}/.venv-wsl/bin/activate"
fi
export PYTHONPATH="${REPO}"

echo "=== TLP-01 Python gate ==="
python -m pytest -q apu_characterization/tests/tlp01

echo "=== TLP-01 protocol contract ==="
python - <<'PY'
from apu_characterization.tlp01.contracts import (
    FORBIDDEN_CLAIM_FRAGMENTS,
    GATE_NAMES,
    MACHINE_MODELS,
    load_protocol,
    validate_template,
)

protocol = load_protocol()
assert protocol["status"] == "template_requires_t0_lock"
assert protocol["protocol_version"] == "tlp01_v2.1"
assert protocol["validity_class"] == "turn_level_parallelism"
assert not validate_template(protocol)
assert set(protocol["gates"]) >= set(GATE_NAMES)
assert set(protocol["machine_models"]) >= set(MACHINE_MODELS)
assert "ceiling_track" in protocol["claim_ladder"]
assert "frontier_track" in protocol["claim_ladder"]
assert protocol["dependence_oracles"]["headline_form"] == "S_C_bracket_never_point"
assert protocol["gates"]["G_V"]["relative_tolerance"] == 0.05
assert protocol["trace_sources"]["S3"]["required_for_v1"] is False
affirmative = (
    str(protocol.get("claim_under_test") or "")
    + str(protocol["claim_ladder"])
).lower()
for fragment in FORBIDDEN_CLAIM_FRAGMENTS:
    assert fragment not in affirmative, fragment
print("protocol contract: tlp01_v2.1 template OK")
PY

echo "=== TLP-01 bundle contract ==="
python apu_characterization/tools/check_tlp01_bundle.py

echo "=== TLP-01 closeout package (v2 artifacts) ==="
python apu_characterization/tools/build_tlp01_closeout.py

echo "=== G-V1-QUARANTINE ==="
python apu_characterization/tools/check_tlp01_v1_quarantine.py

echo "=== TLP-01 synthetic smoke (debug_only; G-V must PASS) ==="
python -m apu_characterization.tlp01.runner --synthetic-debug \
  --out apu_characterization/out/tlp01/_gate_smoke

echo "=== TLP-01 gate OK ==="
