#!/usr/bin/env bash
# MCP-01 build/instrument gate. No OpenAI key or publication measurement.
set -euo pipefail

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
else
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "${REPO}"

VENV="${REPO}/.venv-wsl"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "missing ${VENV}; run apu_characterization/run_wsl_bootstrap.sh" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"
export PYTHONPATH="${REPO}"

echo "=== MCP-01 bundle preflight ==="
python apu_characterization/tools/check_mcp_bundle.py

echo "=== MCP-01 unit gate ==="
python -m pytest -q apu_characterization/tests/mcp_tax

echo "=== MCP-01 matrix contract ==="
python - <<'PY'
from apu_characterization.mcp_tax.contracts import enumerate_matrix
assert len(enumerate_matrix()) == 120
assert len(enumerate_matrix(include_http_stream=True)) == 160
print("matrix contract: 120 mandatory / 160 with streamable HTTP")
PY

echo "=== MCP-01 gate OK ==="
