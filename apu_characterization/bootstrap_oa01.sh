#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
else
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "${REPO}"

if command -v uv >/dev/null 2>&1; then
  uv venv --clear --seed --python python3 .venv-oa01
else
  python3 -m venv .venv-oa01
fi
. .venv-oa01/bin/activate
python -m pip install --upgrade pip
python -m pip install -r apu_characterization/requirements-oa01.txt
python - <<'PY'
import importlib.metadata
import json

expected = "388da74aad620a384ab47669b17c52133e30e7c3"
raw = importlib.metadata.distribution("mini-swe-agent").read_text("direct_url.json")
if not raw:
    raise SystemExit("mini-swe-agent direct_url.json missing")
commit = json.loads(raw).get("vcs_info", {}).get("commit_id")
if commit != expected:
    raise SystemExit(f"mini-swe-agent commit {commit!r} != {expected}")
print(f"mini-swe-agent subject lock OK: {commit}")
PY

