"""Capture fresh LightningSim eval for C2 (OE engine trace solution)."""

import json
import sys
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
REPO = OE_ROOT.parent


def _default_solution():
    dse = OUT_DIR / "dse_report_oe.json"
    if dse.is_file():
        data = json.loads(dse.read_text(encoding="utf-8"))
        sol = data.get("solution_dir")
        if sol:
            p = Path(sol)
            if not p.is_absolute():
                p = (REPO / p).resolve()
            if (p / "trace.pkl").is_file():
                return p
    for cand in (
        REPO / "oe_engine_ls_proj" / "sol1",
        REPO / "oe_stream_ls_proj" / "sol1",
    ):
        if (cand / "trace.pkl").is_file():
            return cand
    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Capture LS eval for C2 OE engine")
    parser.add_argument("--solution-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=OUT_DIR / "ls_oe_eval.json")
    args = parser.parse_args()

    sol = args.solution_dir.resolve() if args.solution_dir else _default_solution()
    if sol is None or not (sol / "trace.pkl").is_file():
        print("ERROR: no OE trace solution (run run_phase2_lightningsim_oe.sh first)", file=sys.stderr)
        return 1

    from fifo_advisor.opt_env import LSEnv

    env = LSEnv(str(sol))
    result = env.eval_solution_default()
    if result.latency is None:
        print("ERROR: eval_solution_default returned no latency", file=sys.stderr)
        return 1

    dse_lat = None
    dse_div = None
    dse_path = OUT_DIR / "dse_report_oe.json"
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
        "note": "C2 LS anchor on OE engine trace; pair with cosim_stream.json (cross-toolchain threshold in ls_validate)",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if dse_div is not None and abs(dse_div) > 5.0:
        print(
            "ERROR: live LS eval diverges {0}% from dse_report_oe baseline".format(dse_div),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
