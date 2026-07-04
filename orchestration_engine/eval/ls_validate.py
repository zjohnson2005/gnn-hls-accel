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


def _ls_latency_from_trace(solution_dir):
    solution_dir = Path(solution_dir)
    trace_pkl = solution_dir / "trace.pkl"
    if not trace_pkl.exists():
        return None, "missing trace.pkl"
    try:
        import pickle

        with trace_pkl.open("rb") as f:
            trace = pickle.load(f)
        if hasattr(trace, "max_latency"):
            return int(trace.max_latency), str(trace_pkl)
        if isinstance(trace, dict) and "max_latency" in trace:
            return int(trace["max_latency"]), str(trace_pkl)
        if isinstance(trace, list) and trace:
            return int(max(trace)), str(trace_pkl)
    except Exception as exc:
        return None, "trace read failed: {0}".format(exc)
    return None, "unsupported trace.pkl layout"


def _find_gcn_vitis_cycles():
    cached = _read_json(OUT_DIR / "cosim_gcn_stream.json")
    if cached and cached.get("passed") and cached.get("latency_cycles") is not None:
        return int(cached["latency_cycles"]), str(OUT_DIR / "cosim_gcn_stream.json")

    search_roots = [
        REPO / "gcn_stream_cosim_proj",
        REPO / "gcn_stream_proj",
        REPO / "gcn_proj",
    ]
    reports = []
    for root in search_roots:
        if root.exists():
            reports.extend(root.glob("**/sim/report/*_cosim.rpt"))

    if not reports:
        return None, "run orchestration_engine/run_gcn_stream_cosim.sh (2025.2.1 cosim)"

    from orchestration_engine.phase2_gate.cosim_parser import parse_cosim_report

    report_path = sorted(reports)[0]
    rep = parse_cosim_report(report_path)
    if rep.passed and rep.latency_cycles is not None:
        return int(rep.latency_cycles), str(report_path)
    return None, str(report_path)


def _row(name, vitis_cycles, ls_cycles, vitis_source, ls_source):
    if vitis_cycles is None or ls_cycles is None:
        return {
            "kernel": name,
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
        "vitis_cycles": vitis_cycles,
        "lightningsim_cycles": ls_cycles,
        "delta_cycles": delta,
        "error_percent": round(err, 3) if err is not None else None,
        "vitis_source": vitis_source,
        "ls_source": ls_source,
        "status": "ok",
    }


def build_validation():
    rows = []

    gcn_ls = REPO / "gcn_stream_proj" / "sol1"
    ls_lat, ls_src = _ls_latency_from_trace(gcn_ls)
    if ls_lat is None:
        dse = _read_json(OUT_DIR / "dse_report.json")
        if dse and dse.get("baseline_max_latency") is not None:
            ls_lat = int(dse["baseline_max_latency"])
            ls_src = str(OUT_DIR / "dse_report.json") + " baseline_max_latency"

    vitis_gcn, vitis_src = _find_gcn_vitis_cycles()
    rows.append(_row("gcn_stream", vitis_gcn, ls_lat, vitis_src, ls_src or "trace.pkl"))

    scatter = _read_json(OUT_DIR / "cosim_stream.json")
    rows.append(
        _row(
            "oe_hls_scatter_stream",
            scatter.get("latency_cycles") if scatter else None,
            None,
            str(OUT_DIR / "cosim_stream.json"),
            "pending LS on oe engine kernel (C2)",
        )
    )

    return rows


def main():
    parser = argparse.ArgumentParser(description="LS vs Vitis cosim validation")
    parser.add_argument("--threshold", type=float, default=5.0, help="Max |error| %")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "ls_validation.json",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Exit 0 when gcn_stream row validates even if scatter row pending",
    )
    args = parser.parse_args()

    rows = build_validation()
    ok_rows = [r for r in rows if r["status"] == "ok" and r["error_percent"] is not None]
    failed = [r for r in ok_rows if abs(r["error_percent"]) > args.threshold]
    gcn_ok = any(r["kernel"] == "gcn_stream" and r["status"] == "ok" for r in rows)

    payload = {
        "threshold_percent": args.threshold,
        "rows": rows,
        "passed": len(failed) == 0 and len(ok_rows) > 0,
        "gcn_stream_validated": gcn_ok and not any(
            r["kernel"] == "gcn_stream" and r["status"] == "ok" and abs(r["error_percent"]) > args.threshold
            for r in rows
            if r.get("error_percent") is not None
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))

    if not ok_rows:
        print("No comparable rows yet (need gcn_stream Vitis cosim + LS trace).", file=sys.stderr)
        print("Run: bash orchestration_engine/run_gcn_stream_cosim.sh", file=sys.stderr)
        return 1
    if failed:
        print("Validation FAILED: {0} rows exceed threshold".format(len(failed)), file=sys.stderr)
        return 1
    if args.allow_partial:
        return 0
    pending = [r for r in rows if r["status"] == "pending"]
    if pending:
        print("{0} row(s) still pending (expected for scatter until C2).".format(len(pending)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
