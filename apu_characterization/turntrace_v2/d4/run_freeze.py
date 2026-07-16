"""CLI: freeze D4 analysis against synthetic corpora (≥3 configs)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apu_characterization.turntrace_v2.d4 import (
    DEFAULT_CONFIGS,
    accept_against_truth,
    generate_corpus,
    run_d4_analysis,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/turntrace_v2/d4_freeze"),
    )
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    all_ok = True
    summaries = []
    for cfg in DEFAULT_CONFIGS:
        records, truth = generate_corpus(cfg)
        report = run_d4_analysis(records, truth=truth)
        failures = accept_against_truth(report)
        path = args.out / f"{cfg.name}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        summaries.append({"config": cfg.name, "failures": failures, "n_records": len(records)})
        if failures:
            all_ok = False
    (args.out / "summary.json").write_text(
        json.dumps({"ok": all_ok, "runs": summaries}, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": all_ok, "runs": summaries}, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
