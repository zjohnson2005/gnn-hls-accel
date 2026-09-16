#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
else
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "${REPO}"

if [[ -f .venv-oa01/bin/activate ]]; then
  . .venv-oa01/bin/activate
fi
export PYTHONPATH="${REPO}"

python -m pytest -q apu_characterization/tests/oa01
python - <<'PY'
import json
from pathlib import Path

from apu_characterization.oa01 import PROTOCOL_VERSION, SUBJECT_COMMIT
from apu_characterization.oa01.manifest import validate_manifest

root = Path("apu_characterization/oa01")
protocol = json.loads((root / "protocol_oa01_v1.json").read_text())
manifest = json.loads((root / "task_manifest.json").read_text())
assert protocol["protocol_version"] == PROTOCOL_VERSION
assert protocol["status"] == "pre_registered_locked"
assert protocol["subject"]["commit"] == SUBJECT_COMMIT
assert protocol["task_manifest_sha256"] == manifest["manifest_sha256"]
assert not validate_manifest(manifest)
assert [t["order"] for t in manifest["tasks"]] == list(range(15))
print("OA-01 protocol and pre-registration lock OK")
PY
python -m apu_characterization.oa01.runner --phase S

