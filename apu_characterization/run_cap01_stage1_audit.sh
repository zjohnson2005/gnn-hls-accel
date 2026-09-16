#!/usr/bin/env bash
# CAP-01 Stage 1: Rust-inclusive verification audit
set -euo pipefail
REPO="${APU_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"
if [[ -f "${HOME}/.cargo/env" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.cargo/env"
fi
if [[ -f "${REPO}/.venv-wsl/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${REPO}/.venv-wsl/bin/activate"
fi
export PYTHONPATH="${REPO}"

echo "=== build rust harness binary ==="
python - <<'PY'
from apu_characterization.cap01.harnesses import build_rust_harness, rust_executable_path
path = build_rust_harness(force=True)
print(f"rust_executable={path}")
print(f"exists={path.is_file()}")
print(f"expected={rust_executable_path()}")
PY

echo "=== verification audit (Axis1 repeats=200) ==="
python apu_characterization/tools/run_cap01_verification_audit.py --axis1-repeats 200
