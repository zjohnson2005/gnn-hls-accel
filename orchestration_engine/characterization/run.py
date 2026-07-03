"""CLI — run Phase 0/1 disaggregation study."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyze import (
    DisaggregationReport,
    analyze_many,
    analyze_profile,
    format_markdown_table,
    format_publishable_summary,
)
from .react_sim import PRESETS, scaling_study, simulate_concurrent_agents, simulate_react_agent
from .trace_io import EXAMPLE_TRACE, TraceNotFoundError, load_trace, save_trace


def _run_presets(args: argparse.Namespace) -> list[DisaggregationReport]:
    reports: list[DisaggregationReport] = []
    for key in args.presets:
        preset = PRESETS[key]
        if args.concurrency <= 1:
            profile = simulate_react_agent(preset)
        else:
            profile = simulate_concurrent_agents(preset, args.concurrency)
        reports.append(analyze_profile(profile))
        if args.save_traces:
            out = Path(args.output_dir) / f"{preset.name}_c{args.concurrency}.json"
            save_trace(profile, out)
    return reports


def _run_scaling(args: argparse.Namespace) -> tuple[list[DisaggregationReport], list[dict]]:
    preset = PRESETS[args.preset]
    levels = [int(x) for x in args.scale_levels.split(",")]
    profiles = scaling_study(preset, levels)
    reports = analyze_many(profiles)
    scaling_rows = []
    for prof, rep in zip(profiles, reports):
        scaling_rows.append(
            {
                "concurrency": prof.concurrency,
                "orchestration_us": rep.orchestration_us,
                "orchestration_pct_accelerable_cpu": rep.orchestration_pct_of_accelerable_cpu,
                "orchestration_pct_cpu_tool": rep.orchestration_pct_of_cpu_tool,
                "cpu_tool_pct_e2e": rep.cpu_tool_pct_of_e2e,
                "io_wait_pct_cpu_tool": (
                    100.0 * rep.io_wait_us / rep.cpu_tool_phase_us
                    if rep.cpu_tool_phase_us
                    else 0
                ),
                "wall_clock_e2e_us": rep.e2e_us,
            }
        )
        if args.save_traces:
            save_trace(prof, Path(args.output_dir) / f"scale_c{prof.concurrency}.json")
    return reports, scaling_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 0/1: disaggregate CPU-side agentic latency bucket"
    )
    parser.add_argument(
        "--presets",
        nargs="*",
        default=["action_heavy", "balanced", "reasoning_heavy"],
        choices=list(PRESETS.keys()),
        help="ReAct workload presets to simulate",
    )
    parser.add_argument("--preset", default="action_heavy", choices=list(PRESETS.keys()))
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--scaling",
        action="store_true",
        help="Run concurrency scaling study (datacenter-relevant)",
    )
    parser.add_argument(
        "--scale-levels",
        default="1,10,100,500,1000",
        help="Comma-separated concurrency levels for --scaling",
    )
    parser.add_argument(
        "--trace",
        type=Path,
        metavar="PATH",
        help=f"Analyze an instrumented JSON trace (example: {EXAMPLE_TRACE.name})",
    )
    parser.add_argument("--output-dir", default="orchestration_engine/characterization/out")
    parser.add_argument("--save-traces", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON report to stdout")
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    reports: list[DisaggregationReport] = []
    scaling_rows: list[dict] = []

    if args.trace is not None and args.scaling:
        parser.error("--trace and --scaling are mutually exclusive; run separately.")

    if args.trace:
        try:
            profile = load_trace(args.trace)
        except TraceNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        reports = [analyze_profile(profile)]
    elif args.scaling:
        reports, scaling_rows = _run_scaling(args)
    else:
        reports = _run_presets(args)

    md_table = format_markdown_table(reports)
    print(md_table)
    print()

    for rep in reports:
        summary = format_publishable_summary(rep)
        summary_path = out_dir / f"{rep.workload_name}_summary.md"
        summary_path.write_text(summary, encoding="utf-8")
        print(summary)
        print("---")

    combined = {
        "reports": [r.to_dict() for r in reports],
        "scaling": scaling_rows,
    }
    combined_path = out_dir / "disaggregation_report.json"
    combined_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(f"Wrote {combined_path}")

    if scaling_rows:
        print("\n## Concurrency scaling (datacenter aggregate CPU view)")
        print(
            "| Concurrency | Orch / (CPU-IO) | Orch us (aggregate) | "
            "CPU tool / E2E (norm) | Wall E2E us |"
        )
        print("|-------------|------------------|---------------------|----------------------|-------------|")
        for row in scaling_rows:
            print(
                f"| {row['concurrency']} | {row['orchestration_pct_accelerable_cpu']:.1f}% | "
                f"{row['orchestration_us']:,} | {row['cpu_tool_pct_e2e']:.1f}% | "
                f"{row['wall_clock_e2e_us']:,} |"
            )

    if args.json:
        json.dump(combined, sys.stdout, indent=2)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
