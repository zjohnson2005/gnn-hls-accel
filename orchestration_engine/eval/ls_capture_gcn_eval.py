"""Capture fresh LightningSim latency for C1 (same solution as trace.pkl / DSE).

Requires a valid full dse_report.json (trace-backed, source=lightningsim) and
evaluates the SAME solution the DSE ran on. If the live eval diverges from the
DSE baseline, nothing is written — a divergent eval must never feed C1.
"""

import json
import sys
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
REPO = OE_ROOT.parent

MAX_DSE_DIVERGENCE_PERCENT = 5.0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Capture LS eval_solution_default for C1")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "ls_gcn_eval.json",
    )
    args = parser.parse_args()

    from orchestration_engine.phase2_gate.ls_gate import (
        dse_report_valid,
        resolve_solution_dir,
    )

    dse_path = OUT_DIR / "dse_report.json"
    ok, detail = dse_report_valid(dse_path, REPO)
    if not ok:
        print(
            "ERROR: cannot capture C1 eval without a valid full DSE report: {0}".format(detail),
            file=sys.stderr,
        )
        print("Run run_phase2_lightningsim.sh first (full trace-backed DSE).", file=sys.stderr)
        return 1

    dse = json.loads(dse_path.read_text(encoding="utf-8"))
    sol = resolve_solution_dir(dse.get("solution_dir"), REPO)

    from fifo_advisor.opt_env import LSEnv

    env = LSEnv(str(sol))
    result = env.eval_solution_default()
    if result.latency is None:
        print("ERROR: eval_solution_default returned no latency", file=sys.stderr)
        return 1

    dse_lat = dse.get("baseline_max_latency")
    dse_div = None
    if dse_lat is not None and int(dse_lat) > 0:
        dse_div = round(100.0 * (int(result.latency) - int(dse_lat)) / int(dse_lat), 3)

    if dse_div is not None and abs(dse_div) > MAX_DSE_DIVERGENCE_PERCENT:
        print(
            "ERROR: live LS eval ({0} cyc) diverges {1}% from dse_report baseline "
            "({2} cyc); max {3}%. Not writing ls_gcn_eval.json.".format(
                int(result.latency), dse_div, dse_lat, MAX_DSE_DIVERGENCE_PERCENT
            ),
            file=sys.stderr,
        )
        if args.output.is_file():
            args.output.unlink()
        return 1

    payload = {
        "solution_dir": str(sol),
        "lightningsim_cycles": int(result.latency),
        "bram": result.bram_usage_total,
        "deadlock": result.deadlock,
        "source": "fifo_advisor.eval_solution_default",
        "dse_baseline_max_latency": dse_lat,
        "dse_divergence_percent": dse_div,
        "note": (
            "C1 LS anchor: live eval on the DSE trace solution. "
            "Must pair with cosim_gcn_stream_ls.json from the same GNN_LS_LITE RTL stamp."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
