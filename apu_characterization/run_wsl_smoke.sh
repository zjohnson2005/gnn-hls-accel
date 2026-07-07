#!/usr/bin/env bash
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."

# Bridge Windows user env into WSL when launched from Cursor/PowerShell.
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  WIN_KEY="$(powershell.exe -NoProfile -Command \
    '[Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")' 2>/dev/null \
    | tr -d '\r')"
  if [[ -n "${WIN_KEY}" ]]; then
    export OPENAI_API_KEY="${WIN_KEY}"
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set in WSL or Windows user environment." >&2
  exit 1
fi

python3 -c "import langgraph, langchain_openai, psutil"
python3 -m apu_characterization.experiments.real_agent_breakdown \
  --backend openai --profile mixed --seed 0 --sessions 2 --search-locality remote --allow-dirty
