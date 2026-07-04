"""Capture fresh LightningSim latency for C1 (same solution as trace.pkl / DSE)."""

import json
import sys
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
REPO = OE_ROOT.parent
DEFAULT_SOL = REPO / "gcn_stream_proj" / "sol1"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Capture LS eval_solution_default for C1")
    parser.add_argument(
        "--solution-dir",
        type=Path,
        default=DEFAULT_SOL,
        help="GNN_LS_LITE trace solution (default gcn_stream_proj/sol1)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "ls_gcn_eval.json",
    )
    args = parser.parse_args()

    sol = args.solution_dir.resolve()
    if not (sol / "trace.pkl").is_file():
        print("ERROR: missing trace.pkl under {0}".format(sol), file=sys.stderr)
        return 1

    from fifo_advisor.opt_env import LSEnv

    env = LSEnv(str(sol))
    result = env.eval_solution_default()
    if result.latency is None:
        print("ERROR: eval_solution_default returned no latency", file=sys.stderr)
        return 1

    dse_path = OUT_DIR / "dse_report.json"
    dse_lat = None
    dse_div = None
    if dse_path.is_file():
        dse = json.loads(dse_path.read_text(encoding="utf-8"))
        dse_lat = dse.get("baseline_max_latency")
        if dse_lat is not None and int(dse_lat) > 0:
            dse_div = round(100.0 * (int(result.latency) - int(dse_lat)) / int(dse_lat), 3)

    payload = {
        "solution_dir": str(sol),
        "lightningsim_cycles": int(result.latency),
        "bram": result.bram_usage_total,
        "deadlock": result.deadlock,
        "source": "fifo_advisor.eval_solution_default",
        "dse_baseline_max_latency": dse_lat,
        "dse_divergence_percent": dse_div,
        "note": (
            "C1 LS anchor: live eval on trace solution. "
            "Must pair with cosim_gcn_stream_ls.json from the same GNN_LS_LITE RTL stamp."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if dse_div is not None and abs(dse_div) > 5.0:
        print(
            "WARN: live LS eval diverges {0}% from dse_report baseline".format(dse_div),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
