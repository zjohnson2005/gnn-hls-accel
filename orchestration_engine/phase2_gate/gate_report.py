"""Phase 2 gate report — csynth scatter, crossover, DSE readiness."""

import json
from pathlib import Path

from orchestration_engine.phase2_gate.cosim_parser import load_or_parse as load_cosim
from orchestration_engine.phase2_gate.crossover import build_crossover, render_markdown
from orchestration_engine.phase2_gate.csynth_parser import find_csynth_reports, load_or_parse
from orchestration_engine.phase2_gate.ls_gate import (
    dse_report_valid,
    gcn_e2_cosim_done,
    ls_validation_passed,
)

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
    cosim_reports = list(
        (OE_ROOT.parent / "oe_scatter_cosim_proj").glob("**/sim/report/*_cosim.rpt")
    ) + list((OE_ROOT.parent / "oe_scatter_proj").glob("**/sim/report/*_cosim.rpt"))
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

    stream_json = OUT_DIR / "cosim_stream.json"
    items.append(
        {
            "id": "cosim_stream",
            "label": "Streaming scatter cosim (steady-state cycles/completion)",
            "status": "done" if stream_json.exists() else "pending",
            "detail": str(stream_json)
            if stream_json.exists()
            else "Run run_phase2_scatter_stream.sh on Vitis box",
        }
    )

    dse_out = OUT_DIR / "dse_report.json"
    dse_ok, dse_detail = dse_report_valid(dse_out, OE_ROOT.parent)
    items.append(
        {
            "id": "lightningsim_dse",
            "label": "LightningSim GCN DSE (trace-backed, source=lightningsim)",
            "status": "done" if dse_ok else "pending",
            "detail": dse_detail if dse_ok else (
                dse_detail + " — run run_phase2_lightningsim.sh on ece-rschsrv"
                if dse_out.exists()
                else "Requires fifo-advisor + gcn_stream_proj/sol1/trace.pkl"
            ),
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

    bench_log = OUT_DIR / "oe_bench.log"
    items.append(
        {
            "id": "oe_bench",
            "label": "Native oe_bench structural proof",
            "status": "done" if bench_log.exists() else "pending",
            "detail": str(bench_log)
            if bench_log.exists()
            else "bash orchestration_engine/run_oe_bench.sh on Vitis box",
        }
    )

    graph_load_json = OUT_DIR / "cosim_graph_load.json"
    graph_detail = str(graph_load_json)
    graph_status = "pending"
    if graph_load_json.exists():
        try:
            gl = json.loads(graph_load_json.read_text(encoding="utf-8"))
            graph_status = "done" if gl.get("passed") else "pending"
            if gl.get("latency_cycles") is not None:
                graph_detail = "{0} ({1} cycles, {2} cyc/node)".format(
                    graph_load_json,
                    gl.get("latency_cycles"),
                    gl.get("cycles_per_node", "?"),
                )
        except (ValueError, OSError):
            graph_status = "pending"
    items.append(
        {
            "id": "session_load_measured",
            "label": "Session load measured (oe_hls_graph_load cosim)",
            "status": graph_status,
            "detail": graph_detail
            if graph_status == "done"
            else "Run run_phase2_graph_load.sh on ece-rschsrv",
        }
    )

    e2_ok, e2_detail = gcn_e2_cosim_done()
    items.append(
        {
            "id": "gcn_e2_cosim",
            "label": "GCN stream thesis cosim anchor (E2, Vitis 2025.2.1)",
            "status": "done" if e2_ok else "pending",
            "detail": e2_detail,
        }
    )

    ls_ok, ls_detail = ls_validation_passed()
    items.append(
        {
            "id": "ls_validation",
            "label": "LightningSim effectiveness (C1 GCN + C2 OE, ls_validation.json)",
            "status": "done" if ls_ok else "pending",
            "detail": ls_detail,
        }
    )

    power_scatter = OUT_DIR / "power_scatter.json"
    power_gl = OUT_DIR / "power_graph_load.json"
    power_done = power_scatter.exists() and power_gl.exists()
    items.append(
        {
            "id": "power_reports",
            "label": "Power JSON (scatter + graph_load)",
            "status": "done" if power_done else "pending",
            "detail": "{0}, {1}".format(power_scatter, power_gl)
            if power_done
            else "bash orchestration_engine/run_power.sh all",
        }
    )

    banked_json = OUT_DIR / "cosim_scatter_banked.json"
    items.append(
        {
            "id": "cosim_scatter_banked",
            "label": "Banked scatter cosim (oe_hls_scatter_banked_stream)",
            "status": "done" if banked_json.exists() else "pending",
            "detail": str(banked_json)
            if banked_json.exists()
            else "Run run_phase2_scatter_banked.sh on ece-rschsrv",
        }
    )

    dse_oe = OUT_DIR / "dse_report_oe.json"
    dse_oe_ok, dse_oe_detail = dse_report_valid(dse_oe, OE_ROOT.parent)
    items.append(
        {
            "id": "lightningsim_oe_dse",
            "label": "LightningSim OE engine DSE (C2, trace-backed)",
            "status": "done" if dse_oe_ok else "pending",
            "detail": dse_oe_detail if dse_oe_ok else (
                dse_oe_detail + " — run run_phase2_lightningsim_oe.sh"
                if dse_oe.exists()
                else "bash orchestration_engine/run_phase2_lightningsim_oe.sh"
            ),
        }
    )

    oe_exp = OE_ROOT.parent / "cost_model_3d" / "out" / "oe_experiment.json"
    items.append(
        {
            "id": "cost_model_oe",
            "label": "3D cost model on OE kernel graph (E1)",
            "status": "done" if oe_exp.exists() else "pending",
            "detail": str(oe_exp)
            if oe_exp.exists()
            else "bash orchestration_engine/run_oe_cost_model_3d.sh",
        }
    )

    variants = OUT_DIR / "variants_results.json"
    items.append(
        {
            "id": "variants_csynth",
            "label": "OE HLS config variant csynth sweep (C3)",
            "status": "done" if variants.exists() else "pending",
            "detail": str(variants)
            if variants.exists()
            else "bash orchestration_engine/run_phase2_variants.sh",
        }
    )

    power_impl = False
    for pj in (OUT_DIR / "power_scatter.json", OUT_DIR / "power_graph_load.json"):
        if pj.exists():
            try:
                pw = json.loads(pj.read_text(encoding="utf-8"))
                if pw.get("status") not in (None, "pending_impl"):
                    power_impl = True
            except (ValueError, OSError):
                pass
    items.append(
        {
            "id": "vivado_power",
            "label": "Vivado post-impl power (B2 full)",
            "status": "done" if power_impl else "pending",
            "detail": "bash orchestration_engine/run_power_vivado.sh (after impl closes)",
        }
    )

    return items


def build_report():
    crossover = build_crossover()
    checklist = _checklist()
    pending = [c for c in checklist if c["status"] == "pending"]
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
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Phase 2 gate report")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Write reports but always exit 0 (use from multi-step pipelines)",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = build_report()
    (OUT_DIR / "phase2_gate.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = render_full_markdown(data)
    (OUT_DIR / "phase2_gate.md").write_text(md, encoding="utf-8")
    print("Wrote {0}".format(OUT_DIR / "phase2_gate.md"))
    print(data["crossover"]["headline"])
    if not data["passed"]:
        print("{0} checklist items still pending.".format(data["pending_count"]))
    if args.refresh:
        return 0
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
