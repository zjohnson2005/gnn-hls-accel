"""Orchestrate C-P2 Class I collection after calibrated wall projection.

Prints the wall projection first. Aborts (exit 2) if projected wall > 24h
unless --allow-over-24h is set after explicit operator confirmation.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from apu_characterization.turntrace_v2.calibrate_rev_c import run_rev_c_calibration
from apu_characterization.turntrace_v2.collect_rev_c import collect_rev_c
from apu_characterization.turntrace_v2.cpu_dryrun import wait_for_server
from apu_characterization.turntrace_v2.engines import EngineIdentity
from apu_characterization.turntrace_v2.engines.llamacpp import LlamaCppServerEngine
from apu_characterization.turntrace_v2.exchange import (
    derive_corpus_exchange,
    load_call_records,
    load_trajectory_records,
)
from apu_characterization.turntrace_v2.model_lock import assert_model_lock
from apu_characterization.turntrace_v2.wall_budget import (
    main as wall_main,
    quadratic_prefill_from_profile,
)


CLASS_I_TASKS = ("TT-EDIT", "TT-RET")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/turntrace_v2/rev_c_cp2"),
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--skip-calibrate", action="store_true")
    parser.add_argument("--allow-over-24h", action="store_true")
    parser.add_argument("--project-only", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.out)
    cal_dir = out / "calibration"
    wall_path = out / "wall_projection_class_i.json"
    collect_dir = out / "class_i"
    lock = assert_model_lock(require_file=True)

    if not args.skip_calibrate:
        print("=== C-P2 calibrate ===", flush=True)
        print(json.dumps(run_rev_c_calibration(out_dir=cal_dir, base_url=args.base_url), indent=2))
    profile_path = cal_dir / "prefill_profile.json"
    if not profile_path.is_file():
        raise SystemExit(f"missing prefill profile: {profile_path}")

    print("=== C-P2 wall projection (Class I) ===", flush=True)
    wall_argv = [
        "--profile",
        str(profile_path),
        "--out",
        str(wall_path),
        "--plan",
        "class_i",
        "--task-class",
        "TT-EDIT",
        "--task-class",
        "TT-RET",
        "--seeds",
        "5",
        "--harnesses",
        "2",
        "--target",
        "cpu_prebox",
    ]
    if args.allow_over_24h:
        wall_argv.append("--allow-over-24h")
    wall_code = wall_main(wall_argv)
    if wall_code == 2 and not args.allow_over_24h:
        return 2
    if args.project_only:
        return wall_code

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    f_prefill = quadratic_prefill_from_profile(profile)
    wait_for_server(args.base_url)
    identity = EngineIdentity(
        deployment_id="CPU0",
        model_id=str(lock["model_id"]),
        quantization=str(lock["quantization"]),
        engine=str(lock["engine"]),
        engine_version=str(lock["engine_version"]),
        hardware="cpu-host",
        reasoning_mode="off",
        provisional=True,
    )
    engine = LlamaCppServerEngine(base_url=args.base_url, identity=identity)
    started = time.time()
    print("=== C-P2 Class I + ablations collect ===", flush=True)
    report = collect_rev_c(
        out_dir=collect_dir,
        engine=engine,
        deployment_id="CPU0",
        f_prefill=f_prefill,
        task_classes=CLASS_I_TASKS,
        seeds=(0, 1, 2, 3, 4),
        harnesses=("raw_python", "langgraph"),
        target="cpu_prebox",
        cloud=False,
        wall_projection_path=wall_path,
        include_ablations=True,
        class_i_only=True,
        allow_over_24h=args.allow_over_24h,
    )
    elapsed_h = (time.time() - started) / 3600.0
    report["actual_wall_hours"] = elapsed_h
    report["projected_wall_hours"] = json.loads(wall_path.read_text(encoding="utf-8")).get(
        "projected_wall_hours"
    )
    (collect_dir / "collect_rev_c_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    calls = load_call_records(collect_dir / "corpus" / "call_records.jsonl")
    trajectories = load_trajectory_records(
        collect_dir / "corpus" / "trajectory_records.jsonl"
    )
    pairs, bands = derive_corpus_exchange(calls, trajectories)
    class_i_pairs = [row for row in pairs if "cache_only" in row.pair_id]
    from apu_characterization.turntrace_v2.exchange import aggregate_exchange

    class_i_bands = aggregate_exchange(class_i_pairs)
    payload = {
        "pair_rows": [row.to_dict() for row in pairs],
        "aggregate_rows": bands,
        "class_i_aggregate_rows": class_i_bands,
        "note": "CLASS-I-ONLY bands are provisional-local; not a rung.",
    }
    (collect_dir / "class_i_exchange_bands.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"collect": report, "class_i_bands": class_i_bands}, indent=2, sort_keys=True))
    return 0 if report.get("all_pairs_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
