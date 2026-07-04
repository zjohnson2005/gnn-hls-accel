"""Compare Vitis cosim cycle counts with LightningSim trace latency."""

import argparse
import json
import sys
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
REPO = OE_ROOT.parent


def _read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _ls_latency_from_fifo_advisor(solution_dir):
    solution_dir = Path(solution_dir)
    try:
        from fifo_advisor.opt_env import LSEnv

        env = LSEnv(str(solution_dir.resolve()))
        result = env.eval_solution_default()
        if result.latency is not None:
            return int(result.latency), "fifo_advisor eval_solution_default({0})".format(
                solution_dir
            )
    except Exception as exc:
        return None, "fifo_advisor failed: {0}".format(exc)
    return None, "fifo_advisor unavailable"


def _ls_latency_from_trace(solution_dir):
    solution_dir = Path(solution_dir)
    trace_pkl = solution_dir / "trace.pkl"
    if not trace_pkl.exists():
        return None, "missing trace.pkl"

    fa_lat, fa_src = _ls_latency_from_fifo_advisor(solution_dir)
    if fa_lat is not None:
        return fa_lat, fa_src

    try:
        import pickle

        with trace_pkl.open("rb") as f:
            trace = pickle.load(f)
        for attr in ("max_latency", "latency", "cycle_count", "total_cycles"):
            if hasattr(trace, attr):
                val = getattr(trace, attr)
                if val is not None:
                    return int(val), "{0}.{1}".format(trace_pkl, attr)
        if isinstance(trace, dict):
            for key in ("max_latency", "latency", "cycle_count"):
                if key in trace and trace[key] is not None:
                    return int(trace[key]), "{0}[{1}]".format(trace_pkl, key)
    except Exception as exc:
        return None, "trace read failed: {0}".format(exc)
    return None, "unsupported trace.pkl layout"


def _find_gcn_vitis_cycles(mode):
    if mode == "ls_lite":
        cached = _read_json(OUT_DIR / "cosim_gcn_stream_ls.json")
        if cached and cached.get("passed") and cached.get("latency_cycles") is not None:
            return int(cached["latency_cycles"]), str(OUT_DIR / "cosim_gcn_stream_ls.json")
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

    gcn_ls = REPO / "gcn_stream_proj" / "sol1"
    ls_lat, ls_src = _ls_latency_from_trace(gcn_ls)
    if ls_lat is None:
        dse = _read_json(OUT_DIR / "dse_report.json")
        if dse and dse.get("baseline_max_latency") is not None:
            ls_lat = int(dse["baseline_max_latency"])
            ls_src = str(OUT_DIR / "dse_report.json") + " baseline_max_latency"

    vitis_gcn, vitis_src = _find_gcn_vitis_cycles(mode)
    comparison = (
        "GNN_LS_LITE Vitis 2023.1 cosim vs LS trace/DSE (C1 paired)"
        if mode == "ls_lite"
        else "thesis ap_fixed Vitis 2025.2.1 cosim vs LS (cross-build; informational)"
    )
    rows.append(_row("gcn_stream", vitis_gcn, ls_lat, vitis_src, ls_src or "trace.pkl", comparison))

    if mode == "thesis_cross":
        thesis_vitis, thesis_src = _find_gcn_vitis_cycles("thesis")
        rows.append(
            _row(
                "gcn_stream_thesis_apfixed",
                thesis_vitis,
                ls_lat,
                thesis_src,
                ls_src or "trace.pkl",
                "cross-build thesis 2025.2.1 vs LS 2023.1 (expected larger delta)",
            )
        )

    scatter = _read_json(OUT_DIR / "cosim_stream.json")
    rows.append(
        _row(
            "oe_hls_scatter_stream",
            scatter.get("latency_cycles") if scatter else None,
            None,
            str(OUT_DIR / "cosim_stream.json"),
            "pending LS on oe engine kernel (C2)",
            "pending C2",
        )
    )

    return rows


def main():
    parser = argparse.ArgumentParser(description="LS vs Vitis cosim validation")
    parser.add_argument(
        "--mode",
        choices=("ls_lite", "thesis_cross"),
        default="ls_lite",
        help="ls_lite: same GNN_LS_LITE build (C1). thesis_cross: adds cross-build row.",
    )
    parser.add_argument("--threshold", type=float, default=5.0, help="Max |error| % for gcn_stream")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "ls_validation.json",
    )
    args = parser.parse_args()

    rows = build_validation(args.mode)
    gcn_rows = [r for r in rows if r["kernel"] == "gcn_stream" and r["status"] == "ok"]
    gcn_failed = [
        r for r in gcn_rows if r.get("error_percent") is not None and abs(r["error_percent"]) > args.threshold
    ]
    gcn_ok = len(gcn_rows) > 0 and len(gcn_failed) == 0

    payload = {
        "mode": args.mode,
        "threshold_percent": args.threshold,
        "rows": rows,
        "passed": gcn_ok,
        "gcn_stream_validated": gcn_ok,
        "note": (
            "C1 requires run_ls_validate_gcn.sh (GNN_LS_LITE 2023.1 cosim). "
            "Thesis ap_fixed cosim (340 cyc) is not comparable to LS trace (315 cyc)."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))

    if not gcn_rows:
        print("No comparable gcn_stream row yet.", file=sys.stderr)
        print("Run: bash orchestration_engine/run_ls_validate_gcn.sh", file=sys.stderr)
        return 1
    if gcn_failed:
        print(
            "Validation FAILED: gcn_stream error {0}% exceeds {1}%".format(
                gcn_failed[0]["error_percent"], args.threshold
            ),
            file=sys.stderr,
        )
        return 1
    print("gcn_stream validated within {0}%".format(args.threshold))
    return 0


if __name__ == "__main__":
    sys.exit(main())
