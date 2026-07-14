#!/usr/bin/env bash
# Parallel postprocessing only; never launches MCP-01 measurements.
set -euo pipefail

REPO="${APU_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${REPO}"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 RETAINED_RUN_ROOT [postprocess options]" >&2
  exit 2
fi

VENV="${MCP_VENV:-${REPO}/.venv-mcp}"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "missing ${VENV}; run the bare-metal launcher/bootstrap first" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"
export PYTHONPATH="${REPO}"

python -m apu_characterization.mcp_tax.postprocess "$@"
