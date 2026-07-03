"""Phase 2 gate report — csynth scatter, crossover, DSE readiness."""

import json
from pathlib import Path

from orchestration_engine.phase2_gate.cosim_parser import load_or_parse as load_cosim
from orchestration_engine.phase2_gate.crossover import build_crossover, render_markdown
from orchestration_engine.phase2_gate.csynth_parser import find_csynth_reports, load_or_parse

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
GATE_DIR = OE_ROOT / "characterization" / "out" / "gate"


def _checklist():
    items = []

    csynth = load_or_parse()
    items.append(
        {
            "id": "csynth_scatter",
            "label": "HLS csynth scatter kernel (run_hls_scatter.tcl)",
            "status": "done"
            if csynth is not None and csynth.is_measured
            else "pending",
            "detail": csynth.report_path if csynth else "No report under oe_scatter_proj/",
        }
    )

    cosim = load_cosim()
    cosim_reports = list((OE_ROOT.parent / "oe_scatter_proj").glob("**/sim/report/*_cosim.rpt"))
    cosim_done = cosim is not None and cosim.passed and cosim.latency_cycles is not None
    items.append(
        {
            "id": "cosim_scatter",
            "label": "HLS cosim scatter (trust cycle count)",
            "status": "done" if cosim_done else "pending",
            "detail": (
                "{0} ({1} cycles)".format(cosim.report_path, cosim.latency_cycles)
                if cosim_done
                else (
                    str(cosim_reports[0])
                    if cosim_reports
                    else "Run run_phase2_scatter_only.sh (includes cosim)"
                )
            ),
        }
    )

    dse_out = OUT_DIR / "dse_report.json"
    items.append(
        {
            "id": "lightningsim_dse",
            "label": "LightningSim FIFO DSE (eval/dse_sweep.py)",
            "status": "done" if dse_out.exists() else "pending",
            "detail": str(dse_out) if dse_out.exists() else "Requires fifo-advisor on Vitis box",
        }
    )

    c1000 = GATE_DIR / "openai_action_heavy_c1000.json"
    items.append(
        {
            "id": "openai_c1000",
            "label": "Real OpenAI anchor at c=1000",
            "status": "done" if c1000.exists() else "pending",
            "detail": str(c1000) if c1000.exists() else "openai_scaling_sweep --levels 1000 --fast --force",
        }
    )

    bench = OE_ROOT / "build" / "oe_bench"
    bench_exe = OE_ROOT / "build" / "oe_bench.exe"
    items.append(
        {
            "id": "oe_bench",
            "label": "Native oe_bench structural proof",
            "status": "done" if bench.exists() or bench_exe.exists() else "pending",
            "detail": str(bench) if bench.exists() else (
                str(bench_exe) if bench_exe.exists() else "build.ps1 on Windows or g++ on Vitis box"
            ),
        }
    )

    return items


def build_report():
    crossover = build_crossover()
    checklist = _checklist()
    pending = [c for c in checklist if c["status"] != "done"]
    passed = len(pending) == 0 and crossover.verdict != "PENDING_CSYNTH"

    return {
        "phase": 2,
        "passed": passed,
        "crossover": crossover.to_dict(),
        "checklist": checklist,
        "pending_count": len(pending),
        "csynth_reports_found": [str(p) for p in find_csynth_reports()],
    }


def render_full_markdown(data):
    crossover = build_crossover()
    lines = [
        "# Phase 2 gate report",
        "",
        "**Status:** {0} ({1} checklist items pending)".format(
            "PASSED" if data["passed"] else "IN PROGRESS",
            data["pending_count"],
        ),
        "",
        render_markdown(crossover),
        "",
        "## Checklist",
        "",
        "| item | status | detail |",
        "|------|--------|--------|",
    ]
    for item in data["checklist"]:
        lines.append("| {0} | {1} | {2} |".format(item["label"], item["status"], item["detail"]))
    return "\n".join(lines)


def main():
    import sys

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = build_report()
    (OUT_DIR / "phase2_gate.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = render_full_markdown(data)
    (OUT_DIR / "phase2_gate.md").write_text(md, encoding="utf-8")
    print("Wrote {0}".format(OUT_DIR / "phase2_gate.md"))
    print(data["crossover"]["headline"])
    if not data["passed"]:
        print("{0} checklist items still pending.".format(data["pending_count"]))
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
