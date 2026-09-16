"""TLP-01 offline runner: G-V first, then ceiling + frontier analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from apu_characterization.tlp01.analyze import analyze_experiment
from apu_characterization.tlp01.audit import audit_experiment, audit_g_v
from apu_characterization.tlp01.contracts import TraceEvent
from apu_characterization.tlp01.extract import (
    make_synthetic_chain_session,
    make_synthetic_parallel_session,
)
from apu_characterization.tlp01.labels import (
    DATA_SOURCE_REAL,
    DATA_SOURCE_SYNTHETIC,
    _strip_internal_keys,
    assert_no_rung_labels_in_smoke_report,
    assert_no_rung_labels_in_text,
    audit_g_smoke_label,
)
from apu_characterization.tlp01.phase_diagram import write_phase_diagram_artifact
from apu_characterization.tlp01.report import write_report
from apu_characterization.tlp01.schema import load_frozen_trace
from apu_characterization.validity import DEBUG_ONLY, TURN_LEVEL_PARALLELISM


def load_sessions_from_dir(trace_dir: Path) -> list[list[TraceEvent]]:
    """Load frozen traces from a directory or a T0 manifest.json colocated there."""
    manifest = trace_dir / "manifest.json"
    if manifest.is_file():
        from apu_characterization.tlp01.t1_graphs import load_sessions_from_manifest

        _, rows = load_sessions_from_manifest(manifest)
        return [events for _, events in rows]
    sessions: list[list[TraceEvent]] = []
    paths = sorted(trace_dir.glob("*.jsonl"))
    if not paths:
        paths = sorted(trace_dir.rglob("*.jsonl"))
    for path in paths:
        sessions.append(load_frozen_trace(path))
    return sessions


def synthetic_debug_sessions() -> list[list[TraceEvent]]:
    sessions: list[list[TraceEvent]] = []
    for seed in range(5):
        sessions.append(
            make_synthetic_parallel_session(
                session_id=f"syn-FO-s{seed}", seed=seed, width=4
            )
        )
        sessions.append(
            make_synthetic_chain_session(
                session_id=f"syn-CN-s{seed}", seed=seed, steps=4
            )
        )
    return sessions


def run(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    out_root: Path,
    validity: str,
    kappa: float | None = None,
) -> dict:
    # Foundation gate: nothing downstream until G-V PASS on every session.
    for events in sessions:
        gate = audit_g_v(events)
        if not gate["pass"]:
            raise RuntimeError(
                "G-V FAILED — blocking all counterfactuals: "
                + "; ".join(gate["errors"])
            )

    data_source = (
        DATA_SOURCE_SYNTHETIC if validity == DEBUG_ONLY else DATA_SOURCE_REAL
    )
    audit = audit_experiment(sessions, kappa=kappa)
    aggregate = analyze_experiment(
        list(sessions), include_frontier=True, data_source=data_source
    )
    aggregate["result_validity"] = validity
    smoke_gate = audit_g_smoke_label(aggregate)
    audit["gates"]["G_SMOKE_LABEL"] = smoke_gate
    if not smoke_gate["pass"]:
        raise RuntimeError(
            "G-SMOKE-LABEL FAILED: " + "; ".join(smoke_gate["errors"])
        )

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "m4_predictor").mkdir(parents=True, exist_ok=True)
    (out_root / "report").mkdir(parents=True, exist_ok=True)
    (out_root / "dependence_graphs").mkdir(parents=True, exist_ok=True)

    phase = aggregate.get("phase_diagram") or {}
    write_phase_diagram_artifact(phase, out_root / "m4_predictor")
    (out_root / "audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    # Strip bulky cell list + internal smoke keys from published aggregate.
    slim = _strip_internal_keys(dict(aggregate))
    if "phase_diagram" in slim:
        slim_phase = {
            k: v for k, v in slim["phase_diagram"].items() if k != "cells"
        }
        slim_phase["cell_count"] = len(phase.get("cells") or [])
        slim["phase_diagram"] = slim_phase
    aggregate_text = json.dumps(slim, indent=2) + "\n"
    (out_root / "aggregate.json").write_text(aggregate_text, encoding="utf-8")
    report_path = write_report(
        aggregate,
        out_root / "report" / "tlp01_report.md",
        audit=audit,
    )
    if data_source != DATA_SOURCE_REAL:
        report_text = report_path.read_text(encoding="utf-8")
        assert_no_rung_labels_in_smoke_report(report_text, context="tlp01_report.md")
        for path in (out_root / "m4_predictor").glob("phase_diagram.*"):
            assert_no_rung_labels_in_text(
                path.read_text(encoding="utf-8"), context=str(path)
            )
    return {
        "audit": audit,
        "report_path": str(report_path),
        "g_v_pass": True,
        "result_validity": validity,
        "data_source": data_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--traces",
        type=Path,
        default=Path("apu_characterization/out/tlp01/traces"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/tlp01"),
    )
    parser.add_argument(
        "--synthetic-debug",
        action="store_true",
        help="Use synthetic sessions (debug_only; not quotable).",
    )
    parser.add_argument("--kappa", type=float, default=None)
    args = parser.parse_args()

    if args.synthetic_debug:
        sessions = synthetic_debug_sessions()
        validity = DEBUG_ONLY
    else:
        if not args.traces.is_dir():
            raise SystemExit(
                f"missing traces dir {args.traces}; pass --synthetic-debug for smoke"
            )
        sessions = load_sessions_from_dir(args.traces)
        if not sessions:
            raise SystemExit(f"no *.jsonl traces in {args.traces}")
        validity = TURN_LEVEL_PARALLELISM

    result = run(sessions, out_root=args.out, validity=validity, kappa=args.kappa)
    print(
        f"G-V PASS; G-SMOKE-LABEL PASS; report={result['report_path']} "
        f"validity={validity} data_source={result['data_source']}"
    )


if __name__ == "__main__":
    main()
