#!/usr/bin/env bash
# Bare-metal validation driver for the NATIVE Linux box (not WSL2).
#
# Copy this script to the native machine and run:
#   export OPENAI_API_KEY=sk-...
#   bash run_bare_metal_native.sh [REPO_URL] [COMMIT]
#
# Defaults: COMMIT should be the freeze commit containing the
# bare_metal_validation experiment. The v3.1 measurement commit is
# d5fd7b8b441565331154c6aeb599ba5863bed9c8; the freeze commit adds only the
# FO-01 post-tools sampling fix and this experiment (record the delta in
# METHODOLOGY.md, appendix "Bare-metal validation").
set -euo pipefail

REPO_URL="${1:?usage: run_bare_metal_native.sh REPO_URL COMMIT}"
COMMIT="${2:?usage: run_bare_metal_native.sh REPO_URL COMMIT}"
WORKDIR="${BARE_METAL_WORKDIR:-${HOME}/apu_bare_metal}"

export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set." >&2
  exit 1
fi

# Platform sanity: refuse WSL2, this driver is for the native box only.
if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "REFUSED: this looks like WSL2. Run the native driver on the native box." >&2
  exit 1
fi

# Load hygiene: refuse start above 1.0 (1-min).
LOAD1="$(cut -d' ' -f1 /proc/loadavg)"
if awk -v l="${LOAD1}" 'BEGIN { exit (l > 1.0) ? 0 : 1 }'; then
  echo "REFUSED: 1-min loadavg ${LOAD1} exceeds 1.0. Wait for the host to quiesce." >&2
  exit 1
fi
echo "loadavg at start: ${LOAD1}"

echo "=== clone at pinned commit ==="
if [[ ! -d "${WORKDIR}/.git" ]]; then
  git clone "${REPO_URL}" "${WORKDIR}"
fi
cd "${WORKDIR}"
git fetch --all --quiet
git checkout --quiet "${COMMIT}"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "REFUSED: tree is dirty after checkout. Clean it first." >&2
  exit 1
fi
echo "commit: $(git rev-parse HEAD)"

echo "=== venv + pinned deps ==="
VENV="${WORKDIR}/.venv-native"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv "${VENV}"
  else
    python3 -m venv "${VENV}"
  fi
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"
if command -v uv >/dev/null 2>&1; then
  uv pip install py-spy numpy psutil tiktoken sympy \
    langgraph langchain-core langchain-openai httpx
else
  pip install -q --upgrade pip
  pip install -q py-spy numpy psutil tiktoken sympy \
    langgraph langchain-core langchain-openai httpx
fi
python --version

echo "=== BLAS pin assertion ==="
python -c "from apu_characterization.env_pin import assert_blas_pinned; assert_blas_pinned()"

echo "=== environment capture (platform row for the comparison) ==="
python -m apu_characterization.capture_setup

echo "=== timer resolution self-test + instrumentation unit tests (must PASS) ==="
python -m apu_characterization.tests.test_resolution
python -m apu_characterization.tests.test_instr
python -m apu_characterization.tests.test_reconcile_worker
python -m apu_characterization.tests.test_attribution_provenance

echo "=== bare-metal validation subset (6 tasks x 3 seeds, c=1) ==="
# capture_setup rewrites setup.json/EXPERIMENT_SETUP.md, so the tree is
# runtime-dirty here; that refresh is expected and recorded in the artifact.
python -m apu_characterization.experiments.bare_metal_validation \
  --backend openai --seeds 0,1,2 --allow-dirty "$@"

LOAD_END="$(cut -d' ' -f1 /proc/loadavg)"
echo "loadavg at end: ${LOAD_END}"
echo ""
echo "=== done ==="
echo "Copy these back to the primary machine's apu_characterization/out/:"
ls -1 apu_characterization/out/bare_metal_validation_*.json \
      apu_characterization/out/bare_metal_validation_*.md \
      apu_characterization/out/setup.json 2>/dev/null || true
echo "Then run: python apu_characterization/tools/bare_metal_compare.py"
