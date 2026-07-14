#!/usr/bin/env bash
# Install the exact MCP-01 dependency lock into the existing WSL venv.
set -euo pipefail

REPO="${APU_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${REPO}"
VENV="${REPO}/.venv-wsl"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "missing ${VENV}; run run_wsl_bootstrap.sh first" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"
python -m pip install -r apu_characterization/requirements-mcp.txt
python - <<'PY'
from importlib.metadata import version
for package in ("mcp", "jsonschema", "httpx", "httpx-sse", "cryptography"):
    print(f"{package}=={version(package)}")
PY
PYTHONPATH="${REPO}" python apu_characterization/tools/check_mcp_bundle.py
