#!/usr/bin/env bash
# One-time WSL bootstrap for verifiable recharacterization (PEP 668 safe).
#
# Prefers `uv` (no sudo). Falls back to apt python3-venv if uv missing.
#
# Usage:
#   bash apu_characterization/run_wsl_bootstrap.sh
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."
REPO="$(pwd)"
VENV="${REPO}/.venv-wsl"

if ! command -v uv >/dev/null 2>&1; then
  echo "=== installing uv (user-local, no sudo) ==="
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

echo "=== creating venv at ${VENV} ==="
rm -rf "${VENV}"
if command -v uv >/dev/null 2>&1; then
  uv venv "${VENV}"
else
  if ! python3 -m venv "${VENV}" 2>/dev/null; then
    echo "ERROR: need python3-venv. Run once:" >&2
    echo "  sudo apt install python3.14-venv python3-pip" >&2
    exit 1
  fi
fi

# shellcheck source=/dev/null
source "${VENV}/bin/activate"

echo "=== installing deps ==="
if command -v uv >/dev/null 2>&1; then
  uv pip install py-spy numpy psutil tiktoken sympy \
    langgraph langchain-core langchain-openai httpx
else
  pip install -q --upgrade pip
  pip install -q py-spy numpy psutil tiktoken sympy \
    langgraph langchain-core langchain-openai httpx
fi

echo "=== versions ==="
python --version
py-spy --version

echo "=== platform self-tests ==="
python -m apu_characterization.tests.test_resolution
python -m apu_characterization.tests.test_instr
python -m apu_characterization.tests.test_reconcile_worker

echo "=== bootstrap OK ==="
echo "Next: export OPENAI_API_KEY=sk-... && bash apu_characterization/run_profile_lh01_wsl.sh"
