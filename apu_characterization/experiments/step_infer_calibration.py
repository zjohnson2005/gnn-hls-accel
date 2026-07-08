"""Mock-backend calibration: false step-inferred CLIENT_HTTP rate.

True CLIENT_HTTP CPU should be ~0 when LLM is pure sleep (mock backend).
Any step-inferred CLIENT_HTTP mass is the heuristic's false-attribution rate.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..experiments.real_agent_breakdown import run_real_batch
from ..instr import measure_timer_overhead_ns
from ..profiles import LOCALITY_ABLATION_PROFILE
from ..provenance import STEP_INFERRED
from ..tasks import assign_task
from ..validity import DEBUG_ONLY


def run_calibration(
    *,
    profile: str = "mixed",
    seed: int = 0,
    sessions: int = 10,
    search_locality: str = "remote",
    instr_version: int = 2,
) -> dict[str, Any]:
    run = run_real_batch(
        sessions,
        profile,
        seed,
        "scripted",
        llm_scale=0.05,
        search_locality=search_locality,
        payload_profile=LOCALITY_ABLATION_PROFILE.name,
        instr_version=instr_version,
    )
    total = run["totals"]["thread_cpu_ns"] or 1
    step_infer_ns = 0
    client_http_infer_ns = 0
    for key, ns in (run.get("provenance_detail") or {}).items():
        parts = key.split("|")
        if len(parts) == 4 and parts[3] == STEP_INFERRED and parts[0] == "CLIENT_HTTP":
            client_http_infer_ns += ns
    step_infer_ns = (run.get("provenance_totals") or {}).get(STEP_INFERRED, 0)

    false_client_http_pct = 100 * client_http_infer_ns / total
    step_inferred_pct = 100 * step_infer_ns / total
    return {
        "experiment": "step_infer_calibration",
        "result_validity": DEBUG_ONLY,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "backend": "scripted",
            "profile": profile,
            "seed": seed,
            "sessions": sessions,
            "search_locality": search_locality,
            "instr_version": instr_version,
        },
        "run": run,
        "calibration": {
            "batch_host_cpu_ns": total,
            "step_inferred_pct": step_inferred_pct,
            "false_client_http_step_inferred_pct": false_client_http_pct,
            "pass": false_client_http_pct <= 5.0,
            "note": (
                "Mock LLM has ~zero HTTP transport CPU; step-inferred CLIENT_HTTP "
                "during agent steps is false attribution."
            ),
        },
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out/step_infer_calibration.json"))
    args = parser.parse_args()
    artifact = run_calibration(seed=args.seed, sessions=args.sessions)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    cal = artifact["calibration"]
    print(f"wrote {args.out}")
    print(f"false CLIENT_HTTP step-inferred: {cal['false_client_http_step_inferred_pct']:.2f}%")
    print(f"step-inferred total: {cal['step_inferred_pct']:.2f}%")
    print(f"calibration pass (false rate <= 5%): {cal['pass']}")


if __name__ == "__main__":
    main()
