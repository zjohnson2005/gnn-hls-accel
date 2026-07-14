#!/usr/bin/env bash
# Native-Linux MCP-01 serial matrix launcher.
set -euo pipefail

REPO="${APU_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${REPO}"

if grep -qiE 'microsoft|wsl' /proc/version; then
  echo "REFUSE: publication matrix requires native bare-metal Linux; WSL is smoke-only" >&2
  exit 2
fi
if command -v systemd-detect-virt >/dev/null && \
   [[ "$(systemd-detect-virt 2>/dev/null || true)" != "none" ]]; then
  echo "REFUSE: publication matrix requires bare metal (virtualization detected)" >&2
  exit 2
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "REFUSE: tracked git tree is dirty" >&2
  exit 2
fi

VENV="${MCP_VENV:-${REPO}/.venv-mcp}"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  python3 -m venv "${VENV}"
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install -r apu_characterization/requirements-mcp.txt
else
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
fi
export PYTHONPATH="${REPO}"

python apu_characterization/tools/check_mcp_bundle.py

CLIENT_CORES="${MCP_CLIENT_CORES:?set MCP_CLIENT_CORES, e.g. 2}"
SERVER_CORES="${MCP_SERVER_CORES:?set MCP_SERVER_CORES, e.g. 4}"
OS_CORES="${MCP_OS_CORES:?set MCP_OS_CORES, e.g. 0,1}"

python -m apu_characterization.experiments.mcp_tax_matrix \
  --execute \
  --publication \
  --client-cores "${CLIENT_CORES}" \
  --server-cores "${SERVER_CORES}" \
  --os-cores "${OS_CORES}" \
  "$@"
