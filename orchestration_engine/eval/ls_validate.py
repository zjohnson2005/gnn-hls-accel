"""Compare Vitis cosim cycle counts with LightningSim trace latency (C1 effectiveness)."""

import argparse
import json
import sys
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
REPO = OE_ROOT.parent
GCN_LS_SOL = REPO / "gcn_stream_proj" / "sol1"


def _read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _ls_latency_for_c1():
    """LightningSim side of C1: fresh eval on the trace/DSE solution."""
    captured = _read_json(OUT_DIR / "ls_gcn_eval.json")
    if captured and captured.get("lightningsim_cycles") is not None:
        src = str(OUT_DIR / "ls_gcn_eval.json")
        if captured.get("dse_baseline_max_latency") is not None:
            src += " (live eval; dse baseline {0})".format(
                captured.get("dse_baseline_max_latency")
            )
        return int(captured["lightningsim_cycles"]), src

    if not (GCN_LS_SOL / "trace.pkl").is_file():
        return None, "missing {0}/trace.pkl — run run_phase2_lightningsim.sh".format(GCN_LS_SOL)

    try:
        from fifo_advisor.opt_env import LSEnv

        env = LSEnv(str(GCN_LS_SOL.resolve()))
        result = env.eval_solution_default()
        if result.latency is not None:
            return int(result.latency), "fifo_advisor.eval_solution_default({0})".format(
                GCN_LS_SOL
            )
    except Exception as exc:
        return None, "fifo_advisor failed: {0}".format(exc)
    return None, "fifo_advisor unavailable"


def _find_gcn_vitis_cycles(mode):
    if mode == "ls_lite":
        cached = _read_json(OUT_DIR / "cosim_gcn_stream_ls.json")
        if cached and cached.get("latency_cycles") is not None:
            if cached.get("passed") and cached.get("status") != "csynth_only":
                return int(cached["latency_cycles"]), str(OUT_DIR / "cosim_gcn_stream_ls.json")
            if cached.get("status") == "csynth_only":
                return None, "{0} (csynth_only — run real cosim for C1)".format(
                    OUT_DIR / "cosim_gcn_stream_ls.json"
                )
        search_roots = [REPO / "gcn_stream_ls_cosim_proj"]
    else:
        cached = _read_json(OUT_DIR / "cosim_gcn_stream.json")
        if cached and cached.get("passed") and cached.get("latency_cycles") is not None:
            return int(cached["latency_cycles"]), str(OUT_DIR / "cosim_gcn_stream.json")
        search_roots = [REPO / "gcn_stream_cosim_proj", REPO / "gcn_stream_proj", REPO / "gcn_proj"]

    reports = []
    for root in search_roots:
        if root.exists():
            reports.extend(root.glob("**/sim/report/*_cosim.rpt"))

    if not reports:
        if mode == "ls_lite":
            return None, "bash orchestration_engine/run_ls_validate_gcn.sh"
        return None, "bash orchestration_engine/run_gcn_stream_cosim.sh"

    from orchestration_engine.phase2_gate.cosim_parser import parse_cosim_report

    report_path = sorted(reports)[0]
    rep = parse_cosim_report(report_path)
    if rep.passed and rep.latency_cycles is not None:
        return int(rep.latency_cycles), str(report_path)
    return None, str(report_path)


def _row(name, vitis_cycles, ls_cycles, vitis_source, ls_source, comparison):
    if vitis_cycles is None or ls_cycles is None:
        return {
            "kernel": name,
            "comparison": comparison,
            "vitis_cycles": vitis_cycles,
            "lightningsim_cycles": ls_cycles,
            "delta_cycles": None,
            "error_percent": None,
            "vitis_source": vitis_source,
            "ls_source": ls_source,
            "status": "pending",
        }
    delta = ls_cycles - vitis_cycles
    err = 100.0 * delta / vitis_cycles if vitis_cycles else None
    return {
        "kernel": name,
        "comparison": comparison,
        "vitis_cycles": vitis_cycles,
        "lightningsim_cycles": ls_cycles,
        "delta_cycles": delta,
        "error_percent": round(err, 3) if err is not None else None,
        "vitis_source": vitis_source,
        "ls_source": ls_source,
        "status": "ok",
    }


def build_validation(mode):
    rows = []

    ls_lat, ls_src = _ls_latency_for_c1()
    vitis_gcn, vitis_src = _find_gcn_vitis_cycles(mode)

    comparison = (
        "C1 thesis row: GNN_LS_LITE Vitis cosim vs LightningSim eval (same RTL stamp)"
        if mode == "ls_lite"
        else "thesis ap_fixed Vitis 2025.2.1 cosim vs LS (cross-build; informational)"
    )
    gate_row = _row("gcn_stream", vitis_gcn, ls_lat, vitis_src, ls_src, comparison)
    gate_row["counts_for_gate"] = True
    rows.append(gate_row)

    captured = _read_json(OUT_DIR / "ls_gcn_eval.json")
    if captured and captured.get("dse_baseline_max_latency") is not None:
        dse_row = _row(
            "gcn_stream_dse_baseline_crosscheck",
            captured.get("dse_baseline_max_latency"),
            captured.get("lightningsim_cycles"),
            str(OUT_DIR / "dse_report.json") + " baseline_max_latency",
            captured.get("source", "ls_gcn_eval.json"),
            "Sanity: DSE sweep baseline vs fresh eval_solution_default (should match)",
        )
        dse_row["counts_for_gate"] = False
        rows.append(dse_row)

    ls_cached = _read_json(OUT_DIR / "cosim_gcn_stream_ls.json")
    if ls_cached and ls_cached.get("status") == "csynth_only":
        cs_row = _row(
            "gcn_stream_csynth_fallback",
            ls_cached.get("latency_cycles"),
            ls_lat,
            str(OUT_DIR / "cosim_gcn_stream_ls.json"),
            ls_src,
            "Cosim failed — csynth number is NOT valid for C1; fix cosim and re-run",
        )
        cs_row["counts_for_gate"] = False
        cs_row["status"] = "blocked"
        rows.append(cs_row)

    thesis = _read_json(OUT_DIR / "cosim_gcn_stream.json")
    if thesis and thesis.get("latency_cycles") is not None and mode == "ls_lite":
        t_row = _row(
            "gcn_stream_thesis_apfixed_e2",
            int(thesis["latency_cycles"]),
            ls_lat,
            str(OUT_DIR / "cosim_gcn_stream.json"),
            ls_src,
            "E2 cross-build (2025.2.1 ap_fixed vs LS 2023.1) — informational",
        )
        t_row["counts_for_gate"] = False
        if t_row["status"] == "ok" and t_row.get("error_percent") is not None:
            t_row["note"] = "Larger delta expected (precision/toolchain); not the C1 gate row"
        rows.append(t_row)

    scatter = _read_json(OUT_DIR / "cosim_stream.json")
    oe_dse = _read_json(OUT_DIR / "dse_report_oe.json")
    ls_scatter_lat = None
    ls_scatter_src = "bash orchestration_engine/run_phase2_lightningsim_oe.sh (C2)"
    if oe_dse and oe_dse.get("baseline_max_latency") is not None:
        ls_scatter_lat = int(oe_dse["baseline_max_latency"])
        ls_scatter_src = "{0} baseline_max_latency (source={1})".format(
            OUT_DIR / "dse_report_oe.json",
            oe_dse.get("source", "?"),
        )
    vitis_scatter = None
    vitis_scatter_src = str(OUT_DIR / "cosim_stream.json")
    if scatter:
        vitis_scatter = scatter.get("per_transaction_cycles") or scatter.get(
            "latency_cycles"
        )
    c2_row = _row(
        "oe_hls_scatter_stream",
        vitis_scatter,
        ls_scatter_lat,
        vitis_scatter_src,
        ls_scatter_src,
        "C2: OE scatter steady-state cosim vs LS DSE on OE engine",
    )
    c2_row["counts_for_gate"] = False
    rows.append(c2_row)

    return rows


def main():
    parser = argparse.ArgumentParser(
        description="LightningSim effectiveness: Vitis cosim vs LS on same GNN_LS_LITE build"
    )
    parser.add_argument(
        "--mode",
        choices=("ls_lite", "thesis_cross"),
        default="ls_lite",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="Max |error| %% for C1 gcn_stream row",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "ls_validation.json",
    )
    args = parser.parse_args()

    rows = build_validation(args.mode)
    gate_rows = [
        r
        for r in rows
        if r.get("counts_for_gate", True)
        and r["kernel"] == "gcn_stream"
        and r["status"] == "ok"
    ]
    gcn_failed = [
        r
        for r in gate_rows
        if r.get("error_percent") is not None and abs(r["error_percent"]) > args.threshold
    ]
    gcn_ok = len(gate_rows) > 0 and len(gcn_failed) == 0

    payload = {
        "mode": args.mode,
        "threshold_percent": args.threshold,
        "rows": rows,
        "passed": gcn_ok,
        "gcn_stream_validated": gcn_ok,
        "note": (
            "C1 proves LightningSim effectiveness: Vitis cosim cycle count on GNN_LS_LITE "
            "must match fifo_advisor eval on gcn_stream_proj/sol1 within {0}%. "
            "This is a thesis pillar alongside OE hardware cosim.".format(args.threshold)
        ),
        "csynth_context": {
            "tb_num_nodes": 6,
            "cosim_thesis_n6_cycles": (
                int(_read_json(OUT_DIR / "cosim_gcn_stream.json")["latency_cycles"])
                if _read_json(OUT_DIR / "cosim_gcn_stream.json")
                else None
            ),
            "interpretation": (
                "Do not substitute csynth min/max for C1. "
                "Trust paired cosim + LS eval only."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))

    if not gate_rows:
        print("C1 BLOCKED: need cosim_gcn_stream_ls.json + ls_gcn_eval.json.", file=sys.stderr)
        print("Run: bash orchestration_engine/run_ls_validate_gcn.sh", file=sys.stderr)
        return 1
    if gcn_failed:
        print(
            "LightningSim validation FAILED: gcn_stream error {0}% exceeds {1}%".format(
                gcn_failed[0]["error_percent"], args.threshold
            ),
            file=sys.stderr,
        )
        return 1
    print("LightningSim validated within {0}% (C1 passed)".format(args.threshold))
    return 0


if __name__ == "__main__":
    sys.exit(main())
