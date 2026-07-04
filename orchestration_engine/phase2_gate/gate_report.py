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

    ls_val = OUT_DIR / "ls_validation.json"
    gcn_e2 = OUT_DIR / "cosim_gcn_stream.json"
    ls_status = "pending"
    ls_detail = "bash orchestration_engine/run_gcn_stream_cosim.sh (E2) or run_ls_validate_gcn.sh (C1)"
    if gcn_e2.exists():
        try:
            g2 = json.loads(gcn_e2.read_text(encoding="utf-8"))
            if g2.get("passed") and g2.get("latency_cycles") is not None:
                ls_status = "done"
                ls_detail = "E2 gcn cosim {0} cyc ({1})".format(
                    g2.get("latency_cycles"), gcn_e2.name
                )
        except (ValueError, OSError):
            pass
    elif ls_val.exists():
        try:
            lv = json.loads(ls_val.read_text(encoding="utf-8"))
            if lv.get("gcn_stream_validated") or lv.get("passed"):
                ls_status = "done"
            ls_detail = str(ls_val)
        except (ValueError, OSError):
            pass
    items.append(
        {
            "id": "ls_validated",
            "label": "GCN stream cosim anchor (E2) / LS validation",
            "status": ls_status,
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
    items.append(
        {
            "id": "lightningsim_oe_dse",
            "label": "LightningSim DSE on OE engine (C2)",
            "status": "done" if dse_oe.exists() else "pending",
            "detail": str(dse_oe)
            if dse_oe.exists()
            else "bash orchestration_engine/run_phase2_lightningsim_oe.sh",
        }
    )

    ls_val = OUT_DIR / "ls_validation.json"
    ls_val_done = False
    if ls_val.exists():
        try:
            lv = json.loads(ls_val.read_text(encoding="utf-8"))
            ls_val_done = bool(lv.get("passed"))
        except (ValueError, OSError):
            pass
    items.append(
        {
            "id": "ls_validation",
            "label": "LS vs Vitis validation report (C1/C2)",
            "status": "done" if ls_val_done else "pending",
            "detail": str(ls_val)
            if ls_val.exists()
            else "bash orchestration_engine/run_ls_validate_gcn.sh",
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
