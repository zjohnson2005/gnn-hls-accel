#!/usr/bin/env bash
# Self-contained bundle checksum gate and bare-metal tarball builder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="${ROOT}/.venv-wsl"
if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
fi
export PYTHONPATH="$ROOT"

python apu_characterization/tools/check_mcp_bundle.py

BUNDLE_DIR="${ROOT}/apu_characterization/out/mcp_tax/bundles"
mkdir -p "$BUNDLE_DIR"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="mcp01_baremetal_bundle_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${BUNDLE_DIR}/${ARCHIVE_NAME}"
CHECKSUM_PATH="${ARCHIVE_PATH}.sha256"

if [[ -e "$ARCHIVE_PATH" ]]; then
  echo "REFUSE: archive already exists: $ARCHIVE_PATH" >&2
  exit 1
fi

TAR_PATHS=(
  Makefile
  apu_characterization/bootstrap_mcp.sh
  apu_characterization/build_bundle.sh
  apu_characterization/provision_baremetal.sh
  apu_characterization/run_mcp_gate.sh
  apu_characterization/run_mcp_gate.ps1
  apu_characterization/run_mcp_bare_metal.sh
  apu_characterization/postprocess_mcp.sh
  apu_characterization/requirements-mcp.txt
  apu_characterization/experiments/mcp_tax_matrix.py
  apu_characterization/mcp_tax
  apu_characterization/tests/mcp_tax
  apu_characterization/tools/check_mcp_bundle.py
  apu_characterization/tools/validate_mcp_tax.py
)

for relative in "${TAR_PATHS[@]}"; do
  if [[ ! -e "${ROOT}/${relative}" ]]; then
    echo "REFUSE: missing bundle path: ${relative}" >&2
    exit 1
  fi
done

tar -czf "$ARCHIVE_PATH" \
  --exclude='.venv' \
  --exclude='.venv-wsl' \
  --exclude='.venv-mcp' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='apu_characterization/out/mcp_tax/runs' \
  --exclude='apu_characterization/out/mcp_tax/runtime' \
  --exclude='apu_characterization/out/mcp_tax/bundles' \
  -C "$ROOT" \
  "${TAR_PATHS[@]}"

if [[ ! -s "$ARCHIVE_PATH" ]]; then
  echo "REFUSE: empty tarball: $ARCHIVE_PATH" >&2
  exit 1
fi

(
  cd "$BUNDLE_DIR"
  sha256sum "$ARCHIVE_NAME" > "${ARCHIVE_NAME}.sha256"
)

echo "MCP-01 bare-metal bundle"
echo "archive=${ARCHIVE_PATH}"
echo "checksum_file=${CHECKSUM_PATH}"
cat "$CHECKSUM_PATH"