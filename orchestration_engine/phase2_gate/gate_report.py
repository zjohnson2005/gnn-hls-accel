"""Phase 2 gate report — csynth scatter, crossover, DSE readiness."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from orchestration_engine.phase2_gate.crossover import build_crossover, render_markdown
from orchestration_engine.phase2_gate.csynth_parser import find_csynth_reports, load_or_parse

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
GATE_DIR = OE_ROOT / "characterization" / "out" / "gate"


def _checklist() -> list[dict]:
    items = []

    csynth = load_or_parse()
    items.append(
        {
            "id": "csynth_scatter",
            "label": "HLS csynth scatter kernel (run_hls_scatter.tcl)",
            "status": "done"
            if csynth is not None and csynth.top_latency_min is not None
            else "pending",
            "detail": csynth.report_path if csynth else "No report under oe_scatter_proj/",
        }
    )

    cosim_reports = list(OE_ROOT.parent.glob("oe_scatter_proj/**/sim/report/*_cosim.rpt"))
    items.append(
        {
            "id": "cosim_scatter",
            "label": "HLS cosim scatter (trust cycle count)",
            "status": "done" if cosim_reports else "pending",
            "detail": str(cosim_reports[0]) if cosim_reports else "Enable cosim in run_hls_scatter.tcl",
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

    bench = OE_ROOT / "build" / "oe_bench.exe"
    items.append(
        {
            "id": "oe_bench",
            "label": "Native oe_bench structural proof",
            "status": "done" if bench.exists() else "pending",
            "detail": str(bench) if bench.exists() else "build.ps1 on Windows or g++ on Vitis box",
        }
    )

    return items


def build_report() -> dict:
    crossover = build_crossover()
    checklist = _checklist()
    csynth = load_or_parse()
    pending = [c for c in checklist if c["status"] != "done"]
    passed = len(pending) == 0 and crossover.verdict != "PENDING_CSYNTH"

    return {
        "phase": 2,
        "passed": passed,
        "crossover": asdict(crossover),
        "checklist": checklist,
        "pending_count": len(pending),
        "csynth_reports_found": [str(p) for p in find_csynth_reports()],
    }


def render_full_markdown(data: dict) -> str:
    crossover = build_crossover()
    lines = [
        "# Phase 2 gate report",
        "",
        f"**Status:** {'PASSED' if data['passed'] else 'IN PROGRESS'} "
        f"({data['pending_count']} checklist items pending)",
        "",
        render_markdown(crossover),
        "",
        "## Checklist",
        "",
        "| item | status | detail |",
        "|------|--------|--------|",
    ]
    for item in data["checklist"]:
        lines.append(
            f"| {item['label']} | {item['status']} | {item['detail']} |"
        )
    lines.extend(
        [
            "",
            "## Next commands (Vitis box)",
            "",
            "```bash",
            "source /tools/software/xilinx/setup_env.sh",
            "cd gnn-hls-accel",
            "bash orchestration_engine/run_phase2.sh",
            "```",
            "",
            "## Next commands (OpenAI / local)",
            "",
            "```powershell",
            "py -3 -m orchestration_engine.characterization.phase1_gate.closeout",
            "```",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = build_report()
    (OUT_DIR / "phase2_gate.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = render_full_markdown(data)
    (OUT_DIR / "phase2_gate.md").write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'phase2_gate.md'}")
    print(data["crossover"]["headline"])
    if not data["passed"]:
        print(f"{data['pending_count']} checklist items still pending.")
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
