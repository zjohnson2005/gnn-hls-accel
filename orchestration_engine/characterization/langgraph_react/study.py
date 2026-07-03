"""Full Phase 1 study: calibrate, optional OpenAI, scaling + reasoning/action axis."""

from __future__ import annotations

import json
import os
from pathlib import Path

from orchestration_engine.characterization.analyze import (
    analyze_profile,
    format_markdown_table,
    format_publishable_summary,
)
from orchestration_engine.characterization.langgraph_react.agent import run_concurrent
from orchestration_engine.characterization.langgraph_react.calibrate import calibrate_preset
from orchestration_engine.characterization.trace_io import save_trace

OUT_DIR = Path("orchestration_engine/characterization/out/study")

ACTION_LEVELS = [1, 100, 500]
REASONING_LEVELS = [1, 100, 500]

OPENAI_KEY_PLACEHOLDERS = frozenset({"sk-...", "sk-your-key-here", "changeme", "your-api-key"})


def openai_key_configured() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key.lower() in OPENAI_KEY_PLACEHOLDERS:
        return False
    if key.startswith("sk-") and len(key) < 24:
        return False
    return True


def _run_openai_trace(reports: list, traces: list[str]) -> None:
    print("Running OpenAI wall-clock trace (c=1, action_heavy)...")
    try:
        prof = run_concurrent(
            preset="action_heavy",
            backend="openai",
            concurrency=1,
            calibrated=False,
            wall_clock=True,
        )
    except Exception as exc:
        name = type(exc).__name__
        print(f"OpenAI run failed ({name}): {exc}", flush=True)
        if "Authentication" in name or "401" in str(exc):
            print(
                "Invalid OPENAI_API_KEY. Set a real key in this shell:\n"
                "  $env:OPENAI_API_KEY = \"sk-...\"\n"
                "Or skip with: py -3 -m ...study --skip-openai",
                flush=True,
            )
        elif "Connection" in name or "Connect" in name:
            print(
                "Network could not reach api.openai.com (firewall, VPN, proxy, or transient outage).\n"
                "  Test: curl.exe https://api.openai.com/v1/models -Headers @{\"Authorization\"=\"Bearer $env:OPENAI_API_KEY\"}\n"
                "  Retry OpenAI only:\n"
                "    py -3 -m orchestration_engine.characterization.langgraph_react.run "
                "--backend openai --preset action_heavy --concurrency 1 --analyze",
                flush=True,
            )
        else:
            print("Continuing without OpenAI trace.", flush=True)
        return

    prof.name = "langgraph_openai_action_heavy_c1"
    prof.meta["label"] = "LangGraph + OpenAI wall-clock (publishable)"
    out = OUT_DIR / "langgraph_openai_action_heavy_c1.json"
    save_trace(prof, out)
    traces.append(str(out))
    reports.append(analyze_profile(prof))
    print(format_markdown_table([reports[-1]]))


def run_study(
    *,
    skip_openai: bool = False,
    skip_calibrate: bool = False,
    calibrate_steps: int = 4,
) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    traces: list[str] = []

    if not skip_calibrate:
        for preset in ("action_heavy", "reasoning_heavy"):
            cal_path = calibrate_preset(preset=preset, calibrate_steps=calibrate_steps)
            print(f"Calibration written: {cal_path.resolve()}")

    if not skip_openai and openai_key_configured():
        _run_openai_trace(reports, traces)
    elif not skip_openai and os.getenv("OPENAI_API_KEY"):
        print(
            "Skipping OpenAI run: OPENAI_API_KEY looks like a placeholder or is too short.\n"
            "Set a valid key or use --skip-openai."
        )
    elif not skip_openai:
        print("Skipping OpenAI run (OPENAI_API_KEY not set).")

    print("\nRunning calibrated mock scaling matrix...")
    matrix: list[tuple[str, int]] = []
    for c in ACTION_LEVELS:
        matrix.append(("action_heavy", c))
    for c in REASONING_LEVELS:
        matrix.append(("reasoning_heavy", c))

    for preset, conc in matrix:
        print(f"  {preset} c={conc} ...")
        prof = run_concurrent(
            preset=preset,
            backend="mock",
            concurrency=conc,
            calibrated=True,
            wall_clock=False,
        )
        prof.name = f"langgraph_{preset}_calibrated_c{conc}"
        prof.meta["label"] = "LangGraph + calibrated mock timing"
        out = OUT_DIR / f"langgraph_{preset}_calibrated_c{conc}.json"
        save_trace(prof, out)
        traces.append(str(out))
        reports.append(analyze_profile(prof))

    summary_md = OUT_DIR / "study_summary.md"
    lines = [
        "# LangGraph Phase 1 study",
        "",
        "Labels:",
        "- **OpenAI trace**: real wall-clock LLM API latency",
        "- **Calibrated mock**: mock LangGraph structure, timings from wall-clock calibration",
        "",
        format_markdown_table(reports),
        "",
    ]
    for rep in reports:
        lines.append(format_publishable_summary(rep))
        lines.append("\n---\n")

    summary_md.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "traces": traces,
        "reports": [r.to_dict() for r in reports],
    }
    report_path = OUT_DIR / "study_report.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {summary_md.resolve()}")
    print(f"Wrote {report_path.resolve()}")
    return report_path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="LangGraph Phase 1 full study")
    parser.add_argument("--skip-calibrate", action="store_true")
    parser.add_argument("--skip-openai", action="store_true")
    parser.add_argument("--calibrate-steps", type=int, default=4)
    args = parser.parse_args()

    run_study(
        skip_openai=args.skip_openai,
        skip_calibrate=args.skip_calibrate,
        calibrate_steps=args.calibrate_steps,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
