"""Compare v1 and v2 replication aggregates and publish migration table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_agg(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("aggregate", {})


def med(agg: dict, key: str) -> float:
    return float(agg.get(key, {}).get("median", 0.0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--v1",
        type=Path,
        default=Path("apu_characterization/out/replication_remote_search.json"),
    )
    parser.add_argument(
        "--v2",
        type=Path,
        default=Path("apu_characterization/out/replication_remote_search_v2.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/replication_v1_v2_migration.md"),
    )
    args = parser.parse_args()
    if not args.v1.is_file():
        raise SystemExit(f"missing v1: {args.v1}")
    if not args.v2.is_file():
        raise SystemExit(f"missing v2: {args.v2}")

    a1 = load_agg(args.v1)
    a2 = load_agg(args.v2)
    rows = [
        ("Batch host CPU ms", "batch_host_cpu_ms", False),
        ("Pooled TOOL %", "pooled_tool_compute_pct", False),
        ("Pooled ORCH total %", "pooled_orch_pct", False),
        ("Pooled ORCH measured %", "pooled_orch_measured_pct", False),
        ("Pooled ORCH reconcile % (v1)", "pooled_orch_reconcile_pct", False),
        ("Pooled harness strict %", "pooled_harness_strict_pct", False),
        ("Pooled harness broad %", "pooled_harness_broad_pct", False),
        ("Pooled RESIDUAL_UNATTRIBUTED % (v2)", "pooled_residual_unattributed_pct", False),
        ("Pooled CLIENT_HTTP % (v2)", "pooled_client_http_pct", False),
        ("Pooled CLIENT_PARSE % (v2)", "pooled_client_parse_pct", False),
        ("Pooled FRAMEWORK % (v2)", "pooled_framework_pct", False),
    ]
    lines = [
        "# Replication v1 vs v2 mass migration",
        "",
        f"- v1 artifact: `{args.v1.name}`",
        f"- v2 artifact: `{args.v2.name}`",
        "",
        "| Headline | v1 median | v2 median | Notes |",
        "|----------|-----------|-----------|-------|",
    ]
    reconcile_v1 = med(a1, "pooled_orch_reconcile_pct")
    for label, key, _ in rows:
        v1 = med(a1, key) if key in a1 else 0.0
        v2 = med(a2, key) if key in a2 else 0.0
        note = ""
        if key == "pooled_orch_reconcile_pct":
            note = "v1 reconcile bucket"
        if key == "pooled_residual_unattributed_pct":
            note = "v2 residual gate target <15%"
        lines.append(f"| {label} | {v1:.1f} | {v2:.1f} | {note} |")
    lines.extend(
        [
            "",
            f"Old reconcile mass (v1 median): **{reconcile_v1:.1f}%** of batch host CPU.",
            "",
            "v2 should decompose this mass into CLIENT_*, FRAMEWORK, THREADPOOL, EVENT_LOOP, "
            "and leave RESIDUAL_UNATTRIBUTED below 15% per session.",
            "",
        ]
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
