#!/usr/bin/env bash
# CAP-01 build and contract gate. Produces no experimental data.
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
# Non-login shells (--noprofile/--norc) omit ~/.cargo/bin; source rustup env when present.
if [[ -f "${HOME}/.cargo/env" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.cargo/env"
elif [[ -x "${HOME}/.cargo/bin/cargo" ]]; then
  export PATH="${HOME}/.cargo/bin:${PATH}"
fi
export PYTHONPATH="${REPO}"

echo "=== CAP-01 Python gate ==="
python -m pytest -q apu_characterization/tests/cap01

echo "=== CAP-01 matrix contract ==="
python - <<'PY'
from apu_characterization.cap01.contracts import enumerate_primary_matrix, load_protocol

protocol = load_protocol()
assert protocol["status"] == "template_requires_p0_lock"
cells = enumerate_primary_matrix(protocol)
assert len(cells) == 180
assert len({cell.cell_id for cell in cells}) == 180
assert protocol["protocol_version"] == "cap01_v2"
assert protocol["candidate_pool"]["minimum_candidates_per_task"] == 2048
assert set(protocol["corpus"]["domains"]) == {
    "FUNCTION_CALLING",
    "TEXT_TO_SQL",
    "CODE",
    "MATH",
    "STRUCTURED_EXTRACTION",
}
assert protocol["corpus"]["tasks_per_domain"] == 50
assert protocol["statistics"]["primary_cell"]["budget_selection"] == "domain_primary_tier"
assert protocol["statistics"]["secondary_family"]["correction"] == "Holm"
assert protocol["gates"]["G8"]["name"] == "verifier_cost_parity"
assert protocol["gates"]["G8"]["relative_tolerance"] == 0.15
print("matrix contract: 180 harness/scale/budget/seed cells")
PY

echo "=== CAP-01 bundle contract ==="
python apu_characterization/tools/check_cap01_bundle.py

if [[ -f apu_characterization/cap01/rust_harness/Cargo.toml ]]; then
  echo "=== CAP-01 Rust gate ==="
  cargo test --manifest-path apu_characterization/cap01/rust_harness/Cargo.toml
  cargo build --release \
    --manifest-path apu_characterization/cap01/rust_harness/Cargo.toml
fi

echo "=== CAP-01 gate OK ==="
