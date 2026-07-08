#!/usr/bin/env bash
# Start v3 replication in background (~1 hr). Poll with: make apu-replicate-check
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   bash apu_characterization/run_apu_replicate_unattended.sh [--allow-dirty]
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

ALLOW=""
if [[ "${1:-}" == "--allow-dirty" ]]; then
  ALLOW="--allow-dirty"
fi

if [[ ! -f "${REPO}/.venv-wsl/bin/activate" ]]; then
  bash apu_characterization/run_wsl_bootstrap.sh
fi

mkdir -p apu_characterization/out
PID_FILE="${REPO}/apu_characterization/out/replicate_v3.pid"
if [[ -f "${PID_FILE}" ]]; then
  old="$(cat "${PID_FILE}" 2>/dev/null || echo 0)"
  if kill -0 "${old}" 2>/dev/null; then
    echo "Replication already running (pid ${old}). Use: make apu-replicate-check" >&2
    exit 2
  fi
fi

nohup bash apu_characterization/run_linux_replication_v3.sh ${ALLOW} \
  > apu_characterization/out/replicate_v3.log 2>&1 &
echo $! > "${PID_FILE}"

python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

repo = Path(".")
pid = int((repo / "apu_characterization/out/replicate_v3.pid").read_text().strip())
state = {
    "status": "running",
    "pid": pid,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "log": "apu_characterization/out/replicate_v3.log",
    "artifact": "apu_characterization/out/replication_remote_search_v3.json",
}
(repo / "apu_characterization/out/replicate_v3.state.json").write_text(
    json.dumps(state, indent=2) + "\n", encoding="utf-8"
)
print(f"Started replication pid={pid}")
print("Poll: make apu-replicate-check")
PY
