#!/usr/bin/env bash
# Post-reboot / logon resume for APU characterization (WSL).
#
# Idempotent:
#   - publishable v3 artifact + probe suite done -> exit 0 quickly
#   - replication pid alive -> exit 0
#   - stale pid after reboot -> restart replication
#   - missing/invalid artifact -> gate + unattended replication
#
# Modes (APU_UNATTENDED_MODE or --mode):
#   auto      default: replicate if needed; else run probe suite once
#   replicate force replication path when artifact invalid
#   probe     run probe suite only (no OpenAI unless APU_REREPPLICATE=1)
#
# Usage:
#   export OPENAI_API_KEY=sk-...   # required for replication / gate FO-01
#   bash apu_characterization/run_unattended_resume.sh [--mode auto|replicate|probe] [--allow-dirty]
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"
# shellcheck source=apu_env.sh
source "$(dirname "$0")/apu_env.sh"

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
else
  cd "$(dirname "$0")/.."
  REPO="$(pwd)"
fi
cd "${REPO}"

git config core.autocrlf true 2>/dev/null || true

MODE="${APU_UNATTENDED_MODE:-auto}"
ALLOW=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:?--mode requires a value}"
      shift 2
      ;;
    --allow-dirty)
      ALLOW="--allow-dirty"
      export APU_ALLOW_DIRTY=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ARTIFACT="${REPO}/apu_characterization/out/replication_remote_search_v3.json"
PROBE_DONE="${REPO}/apu_characterization/out/unattended_probe.done"
VALIDATE="${REPO}/apu_characterization/tools/validate_publishable.py"
PID_FILE="${REPO}/apu_characterization/out/replicate_v3.pid"
STATE_FILE="${REPO}/apu_characterization/out/replicate_v3.state.json"
VENV="${REPO}/.venv-wsl"

_log() {
  echo "[$(date -Iseconds)] $*"
}

_artifact_valid() {
  [[ -f "${ARTIFACT}" ]] || return 1
  "${PY}" "${VALIDATE}" "${ARTIFACT}" >/dev/null 2>&1
}

_replication_running() {
  [[ -f "${PID_FILE}" ]] || return 1
  local pid
  pid="$(cat "${PID_FILE}" 2>/dev/null || echo 0)"
  [[ "${pid}" -gt 0 ]] && kill -0 "${pid}" 2>/dev/null
}

_ensure_venv() {
  if [[ ! -f "${VENV}/bin/activate" ]]; then
    _log "venv missing — bootstrap"
    bash "${REPO}/apu_characterization/run_wsl_bootstrap.sh"
  fi
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
  PY="${VENV}/bin/python"
}

_run_probes() {
  _log "=== probe suite (no OpenAI) ==="
  "${PY}" -m apu_characterization.tests.test_resolution
  "${PY}" -m apu_characterization.tests.test_attribution_provenance
  "${PY}" "${REPO}/apu_characterization/tools/_tool_injection_probe.py"
  "${PY}" "${REPO}/apu_characterization/tools/_v1_v3_mass_conservation.py"
  date -Iseconds > "${PROBE_DONE}"
  _log "probe suite complete -> ${PROBE_DONE}"
}

_run_gate() {
  _log "=== apu-gate (OpenAI FO-01 smoke) ==="
  bash "${REPO}/apu_characterization/run_apu_gate.sh"
}

_start_replication() {
  _log "=== start unattended v3 replication ==="
  bash "${REPO}/apu_characterization/run_apu_replicate_unattended.sh" ${ALLOW}
}

if [[ -z "${OPENAI_API_KEY:-}" ]] && command -v powershell.exe >/dev/null 2>&1; then
  WIN_KEY="$(powershell.exe -NoProfile -Command '$env:OPENAI_API_KEY' 2>/dev/null | tr -d '\r\n')"
  if [[ -n "${WIN_KEY}" ]]; then
    export OPENAI_API_KEY="${WIN_KEY}"
  fi
fi

_ensure_venv
_log "unattended resume: mode=${MODE} repo=${REPO}"

if _replication_running; then
  _log "replication already running (pid $(cat "${PID_FILE}")) — exit 0"
  exit 0
fi

if _artifact_valid; then
  _log "v3 artifact passes validate_publishable"
  case "${MODE}" in
    replicate)
      _log "mode=replicate but artifact already publishable — exit 0"
      exit 0
      ;;
    probe)
      _run_probes
      if [[ "${APU_REREPPLICATE:-}" == "1" ]]; then
        if [[ -z "${OPENAI_API_KEY:-}" ]]; then
          _log "APU_REREPPLICATE=1 set but OPENAI_API_KEY missing — skip re-replication"
          exit 1
        fi
        _run_gate
        _start_replication
      fi
      exit 0
      ;;
    auto)
      if [[ -f "${PROBE_DONE}" ]]; then
        _log "artifact valid and probe suite already done — exit 0"
        exit 0
      fi
      _run_probes
      if [[ "${APU_REREPPLICATE:-}" == "1" ]]; then
        if [[ -z "${OPENAI_API_KEY:-}" ]]; then
          _log "APU_REREPPLICATE=1 set but OPENAI_API_KEY missing — skip re-replication"
          exit 1
        fi
        _run_gate
        _start_replication
      fi
      exit 0
      ;;
    *)
      _log "unknown mode: ${MODE}" >&2
      exit 1
      ;;
  esac
fi

# Replication path: artifact missing or fails validate_publishable.
_log "v3 artifact missing or not publishable — replication required"
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  _log "ERROR: OPENAI_API_KEY not set (needed for gate + replication)" >&2
  exit 1
fi

if [[ -f "${STATE_FILE}" ]]; then
  _log "prior replicate_v3.state.json present (likely interrupted by shutdown)"
fi

case "${MODE}" in
  probe)
    _log "mode=probe but artifact not publishable — running probes only"
    _run_probes
    exit 0
    ;;
  auto|replicate)
    _run_gate
    _start_replication
    exit 0
    ;;
  *)
    _log "unknown mode: ${MODE}" >&2
    exit 1
    ;;
esac
