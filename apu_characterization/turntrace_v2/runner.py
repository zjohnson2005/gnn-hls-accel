"""CLI entrypoints: synthetic calibration smoke + replay acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apu_characterization.turntrace_v2.attribution import harness_tax_ms
from apu_characterization.turntrace_v2.calibration import (
    NetworkBaseline,
    synthesize_decode_profile,
    synthesize_prefill_sweep,
)
from apu_characterization.turntrace_v2.contracts import PROTOCOL_VERSION, load_protocol, validate_protocol
from apu_characterization.turntrace_v2.derive import (
    RawModelCallEvent,
    derive_call_records,
    derive_trajectory_record,
)
from apu_characterization.turntrace_v2.export import export_parquet
from apu_characterization.turntrace_v2.mock_engine import MockEngine
from apu_characterization.turntrace_v2.replay import (
    EnvSnapshotRef,
    ReplayBundle,
    ToolCall,
    TurnBundle,
    save_bundle,
    swapped_step_replay,
)


def run_calibration_smoke(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefill = synthesize_prefill_sweep(seed=7)
    decode = synthesize_decode_profile(seed=7)
    net = NetworkBaseline(endpoint_id="C1-synthetic")
    for slot in ("morning", "afternoon", "evening"):
        for i in range(40):
            net.add_probe(20.0 + (i % 5), tod_slot=slot)
    # Pad to >=100
    for i in range(20):
        net.add_probe(22.0, tod_slot="morning")
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "prefill": prefill.to_dict(),
        "decode": decode.to_dict(),
        "network": net.summary(),
        "prefill_acceptance_passed": prefill.acceptance_passed(),
    }
    path = out_dir / "calibration_smoke.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if not prefill.acceptance_passed():
        raise SystemExit("prefill R² gate failed on synthetic sweep")
    return report


def _make_synthetic_trajectory(traj_id: str, n_turns: int = 6) -> tuple[list[RawModelCallEvent], ReplayBundle]:
    engine = MockEngine()
    env = EnvSnapshotRef(git_commit="deadbeef", container_image_id="sha256:ci")
    bundle = ReplayBundle(
        trajectory_id=traj_id,
        workload_id="swebench_lite_synthetic",
        harness_id="raw_python",
        deployment_id="L1b",
        meta={"task_success": True},
    )
    events: list[RawModelCallEvent] = []
    context_parts = ["system: fix the bug"]
    t0 = 1000.0
    for i in range(n_turns):
        if i % 2 == 0:
            tools = ("read_file",)
            context_parts.append(f"user: inspect file_{i}.py")
            output = f"tool: read_file path=file_{i}.py"
        else:
            tools = ("edit_file",)
            context_parts.append(f"tool_result: contents_{i}")
            output = f"tool: edit_file path=file_{i}.py patch=p{i}"
        context = " ".join(context_parts)
        result = engine.complete(context, max_tokens=6, use_cache=False, output_text=output)
        orch_pre, orch_post = 2.0, 1.5
        t_start = t0 + i * 10.0
        wall = (
            orch_pre
            + result["t_prefill_ms"]
            + result["t_decode_ms"]
            + orch_post
        ) / 1000.0
        events.append(
            RawModelCallEvent(
                trajectory_id=traj_id,
                turn_index=i,
                harness_id="raw_python",
                deployment_id="L1b",
                assembled_context=context,
                raw_model_output=output,
                tool_names=tools,
                t_orch_pre_ms=orch_pre,
                t_orch_post_ms=orch_post,
                t_network_ms=0.0,
                network_method="measured",
                t_prefill_ms=result["t_prefill_ms"],
                prefill_method="direct",
                t_decode_ms=result["t_decode_ms"],
                engine_tokens_in=result["context_tokens_in"],
                requested_tokens_in=result["context_tokens_in"],
                engine_token_ids=tuple(range(result["context_tokens_in"])),
                tokens_out=result["tokens_out"],
                cache_state="disabled",
                prefix_hit_tokens=0,
                model_id=result["model_id"],
                quantization=result["quantization"],
                reasoning_mode="off",
                engine=result["engine"],
                engine_version=result["engine_version"],
                wall_clock_start=t_start,
                wall_clock_end=t_start + wall,
                tokenizer_id="whitespace_v0",
                expected_horizon=n_turns,
            )
        )
        bundle.append_turn(
            TurnBundle(
                turn_index=i,
                assembled_context=context,
                raw_model_output=output,
                tool_calls=[ToolCall(name=tools[0], arguments={"i": i})],
                tool_results=[{"ok": True, "i": i}],
                sampling_params={"temperature": 0, "seed": 0, "max_tokens": 6},
                reasoning_mode="off",
                env_snapshot_ref=env,
                tokenizer_id="whitespace_v0",
                context_full_tokens=context.split(),
            )
        )
    return events, bundle


def run_replay_acceptance(out_dir: Path, *, n_trajectories: int = 3) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefill = synthesize_prefill_sweep(seed=3)
    decode = synthesize_decode_profile(seed=3)
    all_calls = []
    all_traj = []
    swap_results = []
    for t in range(n_trajectories):
        traj_id = f"syn-{t:03d}"
        events, bundle = _make_synthetic_trajectory(traj_id, n_turns=6)
        bundle_path = out_dir / "bundles" / f"{traj_id}.ttbundle"
        save_bundle(bundle, bundle_path)
        calls = derive_call_records(
            events,
            f_prefill=prefill.predict_ms,
            predict_decode_ms=lambda m, depth: decode.predict_decode_ms(m, kv_depth=depth),
        )
        traj = derive_trajectory_record(
            calls,
            workload_id="swebench_lite_synthetic",
            cache_mode="cache-disabled",
            task_success=True,
            success_metric="swebench_pass",
            replay_bundle_path=str(bundle_path),
            headline=True,
        )
        all_calls.extend(calls)
        all_traj.append(traj)
        engine = MockEngine()
        result = swapped_step_replay(
            bundle,
            swap_turn=2,
            model_fn=engine.as_model_fn(fixed_output="swapped ok"),
            model_id="synthetic-swap",
            reasoning_mode="on",
        )
        swap_results.append(
            {
                "trajectory_id": result.trajectory_id,
                "success": result.success,
                "swap_turn": result.swap_turn,
                "tool_replay_modes": result.tool_replay_modes,
            }
        )
        # harness tax sanity
        _ = [
            harness_tax_ms(
                t_orch_pre_ms=c.t_orch_pre_ms,
                t_orch_post_ms=c.t_orch_post_ms,
                t_prefill_redundant_ms=c.t_prefill_redundant_ms,
            )
            for c in calls
        ]
    export_parquet(all_calls, all_traj, out_dir / "corpus")
    report = {
        "n_trajectories": n_trajectories,
        "n_calls": len(all_calls),
        "swap_results": swap_results,
        "all_swaps_ok": all(r["success"] for r in swap_results),
    }
    (out_dir / "replay_acceptance.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    if not report["all_swaps_ok"]:
        raise SystemExit("swapped-step replay acceptance failed")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="turntrace_v2")
    parser.add_argument(
        "--synthetic-debug",
        action="store_true",
        help="Run calibration smoke + replay acceptance (debug_only)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/turntrace_v2/_gate_smoke"),
    )
    args = parser.parse_args(argv)
    errors = validate_protocol(load_protocol())
    if errors:
        raise SystemExit("protocol invalid: " + "; ".join(errors))
    if args.synthetic_debug:
        run_calibration_smoke(args.out / "calibration")
        run_replay_acceptance(args.out / "replay", n_trajectories=3)
        print("turntrace_v2 synthetic smoke OK")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
