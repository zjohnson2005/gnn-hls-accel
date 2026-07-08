#!/usr/bin/env bash
# Phase A3: profile LH-01 (task index 8) with instrumentation + py-spy on WSL.
#
# Usage (from repo root in WSL, or via run_profile_lh01_wsl.ps1 from PowerShell):
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_profile_lh01_wsl.sh
#
# Uses a repo-local venv (PEP 668 safe). Does not mutate system Python.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."
REPO="$(pwd)"
VENV="${REPO}/.venv-wsl"

if [[ -z "${OPENAI_API_KEY:-}" ]] && command -v powershell.exe >/dev/null 2>&1; then
  WIN_KEY="$(powershell.exe -NoProfile -Command '$env:OPENAI_API_KEY' 2>/dev/null | tr -d '\r\n')"
  if [[ -n "${WIN_KEY}" ]]; then
    export OPENAI_API_KEY="${WIN_KEY}"
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set." >&2
  exit 1
fi

if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "=== venv missing; run bootstrap first ==="
  bash "${REPO}/apu_characterization/run_wsl_bootstrap.sh"
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"

echo "=== installing deps in venv ==="
if command -v uv >/dev/null 2>&1; then
  uv pip install -q py-spy numpy psutil tiktoken sympy \
    langgraph langchain-core langchain-openai httpx 2>/dev/null || true
else
  pip install -q --upgrade pip
  pip install -q py-spy numpy psutil tiktoken sympy
  pip install -q langgraph langchain-core langchain-openai httpx 2>/dev/null || true
fi

PY="${VENV}/bin/python"
PYSPY="${VENV}/bin/py-spy"
# Default 20 Hz: 100 Hz falls behind on LH-01 (ThreadPool + httpx); weights stay valid but sparse.
PYSPY_RATE="${PYSPY_RATE:-20}"
TASK_INDEX=8
SEED=0
OUT="apu_characterization/out"
PROFILE_JSON="${OUT}/profile_lh-01_s0.json"
SPEEDSCOPE="${OUT}/pyspy_lh01.speedscope.json"

echo "=== py-spy version ==="
"${PYSPY}" --version

echo "=== py-spy sanity (2s busy loop) ==="
"${PYSPY}" record --format speedscope --output "${OUT}/pyspy_sanity.speedscope.json" -d 2 -- \
  "${PY}" -c "import time; t=time.time()+1.5; exec('while time.time()<t: pass')"
echo "sanity profile: ${OUT}/pyspy_sanity.speedscope.json"

echo "=== LH-01 profile session (OpenAI, instr v1) ==="
"${PY}" -m apu_characterization.experiments.profile_reconcile_session \
  --task-index "${TASK_INDEX}" --seed "${SEED}" --backend openai --instr-version 1

echo "=== py-spy record same session (rate=${PYSPY_RATE} Hz, native stacks) ==="
set +e
"${PYSPY}" record --rate "${PYSPY_RATE}" --native --format speedscope \
  --output "${SPEEDSCOPE}" --subprocesses -- \
  "${PY}" -m apu_characterization.experiments.profile_reconcile_session \
  --task-index "${TASK_INDEX}" --seed "${SEED}" --backend openai --instr-version 1
PYSPY_RC=$?
set -e
if [[ ! -f "${SPEEDSCOPE}" ]]; then
  echo "ERROR: py-spy did not write ${SPEEDSCOPE} (exit ${PYSPY_RC})" >&2
  exit 1
fi
if [[ "${PYSPY_RC}" -ne 0 ]]; then
  echo "WARNING: py-spy exited ${PYSPY_RC} (common on WSL: 'No child process'); speedscope kept." >&2
fi

echo "=== bucketize ==="
"${PY}" apu_characterization/tools/pyspy_bucketize.py "${SPEEDSCOPE}" --out "${OUT}/pyspy_lh01_buckets.md"

echo "=== verdict ==="
"${PY}" apu_characterization/tools/generate_attribution_verdict.py \
  --profile-json "${PROFILE_JSON}" \
  --speedscope "${SPEEDSCOPE}"

echo "=== done ==="
echo "profile: ${PROFILE_JSON}"
echo "speedscope: ${SPEEDSCOPE}"
echo "verdict: apu_characterization/out/ATTRIBUTION_VERDICT.md"
