#!/usr/bin/env bash
# TurnTrace v2 build and contract gate (+ D4 freeze + optional CPU dry-run check).
set -euo pipefail

if [[ -n "${APU_REPO_ROOT:-}" ]]; then
  REPO="${APU_REPO_ROOT}"
else
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "${REPO}"

if [[ -f "${REPO}/.venv-wsl/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${REPO}/.venv-wsl/bin/activate"
fi
export PYTHONPATH="${REPO}"

echo "=== TurnTrace v2 Python gate ==="
python -m pytest -q apu_characterization/tests/turntrace_v2

echo "=== TurnTrace v2 protocol contract ==="
python - <<'PY'
from apu_characterization.turntrace_v2.contracts import (
    PROTOCOL_VERSION,
    load_protocol,
    validate_protocol,
    validate_protocol_lock,
)

protocol = load_protocol()
assert protocol["protocol_version"] == PROTOCOL_VERSION
assert protocol["revision"] == "C"
assert not validate_protocol(protocol)
assert not validate_protocol_lock()
assert protocol["replay_bundle"]["mandatory_for_headline"] is True
print(f"protocol contract: {PROTOCOL_VERSION} OK")
PY

echo "=== TurnTrace v2 D4 freeze (synthetic acceptance) ==="
python - <<'PY'
from apu_characterization.turntrace_v2.d4 import (
    DEFAULT_CONFIGS,
    accept_against_truth,
    generate_corpus,
    run_d4_analysis,
)
for cfg in DEFAULT_CONFIGS:
    records, truth = generate_corpus(cfg)
    report = run_d4_analysis(records, truth=truth)
    failures = accept_against_truth(report)
    assert not failures, (cfg.name, failures)
print(f"D4 freeze OK across {len(DEFAULT_CONFIGS)} configs")
PY

echo "=== TurnTrace v2 synthetic smoke (debug_only; replay acceptance on 3 traj) ==="
python -m apu_characterization.turntrace_v2.runner --synthetic-debug \
  --out apu_characterization/out/turntrace_v2/_gate_smoke

if [[ "${TTV2_REQUIRE_CPU_DRYRUN:-0}" == "1" ]]; then
  echo "=== TurnTrace v2 CPU dry-run artifact check ==="
  test -f apu_characterization/out/turntrace_v2/cpu_dryrun/cpu_dryrun_report.json
  python - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("apu_characterization/out/turntrace_v2/cpu_dryrun/cpu_dryrun_report.json").read_text())
assert report["provisional"] is True
assert report["prefill_acceptance_passed"] is True
assert report["all_swaps_ok"] is True
assert report["n_trajectories"] >= 5
meta = json.loads(Path("apu_characterization/out/turntrace_v2/cpu_dryrun/corpus/corpus_metadata.json").read_text())
assert meta["headline_eligible"] is False
print("CPU dry-run artifact OK (provisional)")
PY
fi

echo "=== TurnTrace v2 gate OK ==="
