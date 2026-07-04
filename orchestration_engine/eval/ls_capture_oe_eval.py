"""Capture fresh LightningSim eval for C2 (OE engine trace solution).

The solution comes ONLY from a validated dse_report_oe.json (full trace-backed
DSE). No fallback to partial builds (e.g. scatter-only projects): C2 must pair
the OE cosim number with LightningSim on the SAME full-engine trace the DSE ran on.
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

    parser = argparse.ArgumentParser(description="Capture LS eval for C2 OE engine")
    parser.add_argument("--output", type=Path, default=OUT_DIR / "ls_oe_eval.json")
    args = parser.parse_args()

    from orchestration_engine.phase2_gate.ls_gate import (
        dse_report_valid,
        resolve_solution_dir,
    )

    dse_path = OUT_DIR / "dse_report_oe.json"
    ok, detail = dse_report_valid(dse_path, REPO)
    if not ok:
        print(
            "ERROR: cannot capture C2 eval without a valid full DSE report: {0}".format(detail),
            file=sys.stderr,
        )
        print("Run run_phase2_lightningsim_oe.sh first (no partial builds).", file=sys.stderr)
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
            "ERROR: live LS eval ({0} cyc) diverges {1}% from dse_report_oe baseline "
            "({2} cyc); max {3}%. Not writing ls_oe_eval.json.".format(
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
            "C2 LS anchor on OE engine trace (same solution as dse_report_oe.json); "
            "pair with cosim_stream.json (cross-toolchain threshold in ls_validate)"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
