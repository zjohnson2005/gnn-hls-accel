"""Run instrumented LangGraph ReAct agent and export characterization traces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestration_engine.characterization.analyze import (
    analyze_profile,
    format_markdown_table,
    format_publishable_summary,
)
from orchestration_engine.characterization.trace_io import save_trace


def _check_deps() -> None:
    try:
        import langgraph  # noqa: F401
        import langchain_core  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "LangGraph dependencies missing. Install with:\n"
            "  py -3 -m pip install -r orchestration_engine/characterization/requirements-langgraph.txt"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    _check_deps()

    from orchestration_engine.characterization.langgraph_react.agent import run_concurrent

    parser = argparse.ArgumentParser(description="Instrumented LangGraph ReAct agent")
    parser.add_argument(
        "--preset",
        default="action_heavy",
        choices=["action_heavy", "balanced", "reasoning_heavy"],
    )
    parser.add_argument("--backend", default="mock", choices=["mock", "openai"])
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("orchestration_engine/characterization/out/langgraph_react.json"),
    )
    parser.add_argument("--calibrate", action="store_true", help="Wall-clock calibrate preset")
    parser.add_argument("--study", action="store_true", help="Full Phase 1 study matrix")
    parser.add_argument("--analyze", action="store_true", help="Print disaggregation after run")
    parser.add_argument("--calibrated", action="store_true", help="Use calibration JSON timings")
    args = parser.parse_args(argv)

    if args.study:
        from orchestration_engine.characterization.langgraph_react.study import run_study

        run_study()
        return 0

    if args.calibrate:
        from orchestration_engine.characterization.langgraph_react.calibrate import calibrate_preset

        path = calibrate_preset(preset=args.preset)
        print(f"Wrote calibration: {path.resolve()}")
        return 0

    profile = run_concurrent(
        preset=args.preset,
        backend=args.backend,
        concurrency=args.concurrency,
        seed=args.seed,
        calibrated=args.calibrated,
    )
    profile.name = f"langgraph_{args.preset}_c{args.concurrency}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_trace(profile, args.output)
    print(f"Wrote trace: {args.output.resolve()}")
    print(f"Spans: {len(profile.spans)}  Agents: {args.concurrency}")

    if args.analyze:
        report = analyze_profile(profile)
        print()
        print(format_markdown_table([report]))
        print()
        print(format_publishable_summary(report))

    print()
    print("Analyze later with:")
    print(f"  py -3 -m orchestration_engine.characterization.run --trace {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
