#!/usr/bin/env bash
# Full c-ladder concurrency sweep in the background (survives the launching
# terminal). Levels 5,10,25,50,100 with seeds 0,1,2 (n=3 per level).
#
# NOTE: n=5 seeds at the saturation level is a FOLLOW-UP run once N_max is
# known; rerun with --levels <N_max> --seeds 0,1,2,3,4 to firm it up.
#
# State files (like run_apu_replicate_unattended.sh):
#   apu_characterization/out/sweep.pid         background pid
#   apu_characterization/out/sweep.log         combined stdout/stderr
#   apu_characterization/out/sweep.state.json  running/done/failed + timestamps
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_sweep_ladder.sh [--allow-dirty]
#   bash apu_characterization/run_sweep_ladder.sh --worker [--allow-dirty]  (internal)
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${HOME}/.local/bin:${PATH}"

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
elif [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != bash && -f "${BASH_SOURCE[0]}" ]]; then
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
else
  REPO="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "${REPO}"
# Export for the nohup'ed worker re-invocation (piped bash cannot re-resolve
# its own path from BASH_SOURCE).
export APU_REPO_ROOT="${REPO}"
# shellcheck source=apu_env.sh
source "${REPO}/apu_characterization/apu_env.sh"

LEVELS="5,10,25,50,100"
SEEDS="0,1,2"
OUT_DIR="${REPO}/apu_characterization/out"
PID_FILE="${OUT_DIR}/sweep.pid"
LOG_FILE="${OUT_DIR}/sweep.log"
STATE_FILE="${OUT_DIR}/sweep.state.json"

MODE="launcher"
ALLOW=""
for arg in "$@"; do
  case "${arg}" in
    --worker) MODE="worker" ;;
    --allow-dirty) ALLOW="--allow-dirty" ;;
  esac
done

write_state() {
  local status="$1"
  python3 - "$status" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status = sys.argv[1]
path = Path("apu_characterization/out/sweep.state.json")
state = {}
if path.is_file():
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state = {}
pid_file = Path("apu_characterization/out/sweep.pid")
if pid_file.is_file():
    try:
        state["pid"] = int(pid_file.read_text().strip())
    except ValueError:
        pass
state["status"] = status
state.setdefault("started_at", datetime.now(timezone.utc).isoformat())
state["updated_at"] = datetime.now(timezone.utc).isoformat()
state["log"] = "apu_characterization/out/sweep.log"
state["artifact"] = "apu_characterization/out/concurrency_sweep.json"
state["report"] = "apu_characterization/out/concurrency_sweep_report.md"
state["figures"] = "apu_characterization/out/figures/"
path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
PY
}

if [[ "${MODE}" == "worker" ]]; then
  VENV="${REPO}/.venv-wsl"
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
  write_state "running"
  set +e
  python -m apu_characterization.experiments.concurrency_sweep \
    --backend openai --levels "${LEVELS}" --seeds "${SEEDS}" \
    --search-locality remote ${ALLOW}
  rc=$?
  if [[ ${rc} -eq 0 ]]; then
    python apu_characterization/tools/sweep_figures.py || rc=$?
    python apu_characterization/tools/sweep_report.py || rc=$?
  fi
  set -e
  if [[ ${rc} -eq 0 ]]; then
    write_state "done"
  else
    write_state "failed"
  fi
  exit ${rc}
fi

# ------------------------------------------------------------- launcher path
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

if [[ -z "${ALLOW}" ]] && [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "ERROR: uncommitted tracked changes. Commit first or pass --allow-dirty." >&2
  git status --short --untracked-files=no >&2
  exit 1
fi

if [[ ! -f "${REPO}/.venv-wsl/bin/activate" ]]; then
  bash apu_characterization/run_wsl_bootstrap.sh
fi

mkdir -p "${OUT_DIR}"
if [[ -f "${PID_FILE}" ]]; then
  old="$(cat "${PID_FILE}" 2>/dev/null || echo 0)"
  if kill -0 "${old}" 2>/dev/null; then
    echo "Sweep already running (pid ${old}). Check ${LOG_FILE}." >&2
    exit 2
  fi
fi

# Re-invoke this script in worker mode under nohup so the ladder survives the
# launching terminal (and the PowerShell window). CRs stripped in case of a
# CRLF checkout on /mnt/c.
nohup bash -c "tr -d '\r' < apu_characterization/run_sweep_ladder.sh | bash -s -- --worker ${ALLOW}" \
  > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"
write_state "running"

echo "Started sweep ladder pid=$(cat "${PID_FILE}")"
echo "Levels: ${LEVELS}, seeds: ${SEEDS}"
echo "Log:   ${LOG_FILE}"
echo "State: ${STATE_FILE}"
