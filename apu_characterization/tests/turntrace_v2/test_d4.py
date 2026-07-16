from __future__ import annotations

import json
from pathlib import Path

from apu_characterization.turntrace_v2.d4 import (
    DEFAULT_CONFIGS,
    accept_against_truth,
    generate_corpus,
    run_d4_analysis,
)


def test_d4_recovers_ground_truth_across_configs(tmp_path: Path) -> None:
    assert len(DEFAULT_CONFIGS) >= 3
    for cfg in DEFAULT_CONFIGS:
        records, truth = generate_corpus(cfg)
        report = run_d4_analysis(records, truth=truth)
        failures = accept_against_truth(report)
        assert not failures, (cfg.name, failures, report["component_errors"])
        out = tmp_path / f"{cfg.name}.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
