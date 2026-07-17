"""Rev C paired A/B collector.

The CLI defaults to a mock instrumentation run. Live cloud collection is not
implemented here until the rev C budget lock is marked launch-authorized.
Programmatic callers may supply a calibrated local engine for C-P2.
"""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Callable, Sequence

from apu_characterization.turntrace_v2.arms import (
    ArmConfig,
    append_layout_only,
    baseline,
    cache_only,
    optimized_full,
)
from apu_characterization.turntrace_v2.audit import (
    audit_cache_truth,
    audit_pair,
    headline_eligible,
)
from apu_characterization.turntrace_v2.collect_cloud import _mock_engine
from apu_characterization.turntrace_v2.contracts import (
    canonical_json_bytes,
    protocol_sha256,
    sha256_bytes,
)
from apu_characterization.turntrace_v2.derive import (
    RawModelCallEvent,
    derive_call_records,
    derive_trajectory_record,
)
from apu_characterization.turntrace_v2.economics import calculate_model_cost
from apu_characterization.turntrace_v2.engines import Engine
from apu_characterization.turntrace_v2.export import export_parquet
from apu_characterization.turntrace_v2.harnesses import (
    LangGraphHarness,
    RawPythonHarness,
)
from apu_characterization.turntrace_v2.replay import ReplayBundle, save_bundle
from apu_characterization.turntrace_v2.schema import CallRecord, TrajectoryRecord
from apu_characterization.turntrace_v2.workload.rev_c_suite import (
    SEEDS,
    TASK_CLASSES,
    FROZEN_PAYLOAD_MANIFEST_PATH,
    build_payload_catalog,
    PayloadCatalog,
    build_suite_plan,
    payload_manifest_dict,
    to_langgraph_steps,
    to_raw_python_turns,
    validate_frozen_payload_manifest,
)

# Protocol-frozen local ablation classes (must match wall_budget defaults).
ABLATION_CLASSES = frozenset({"TT-EDIT", "TT-RET"})


def _tools() -> dict:
    def return_payload(_name: str, args: dict) -> dict:
        return {
            "result_id": args.get("result_id"),
            "payload": args.get("_payload", ""),
            "from_result": args.get("from_result"),
            "ok": True,
        }

    return {name: return_payload for name in {
        "read_file",
        "edit_file",
        "run_tests",
        "search",
        "fetch",
        "append_summary",
        "read_chunk",
        "transform",
        "synthesize",
    }}


def _run_one(
    *,
    engine: Engine,
    arm_config: ArmConfig,
    task_class: str,
    seed: int,
    harness_id: str,
    deployment_id: str,
    pair_variant: str,
    target: str,
    catalog: PayloadCatalog,
) -> tuple[list[RawModelCallEvent], ReplayBundle, int]:
    plan = build_suite_plan(
        task_class,
        seed=seed,
        arm_config=arm_config,
        harness_id=harness_id,
        deployment_id=deployment_id,
        target=target,
        pair_variant=pair_variant,
        catalog=catalog,
        message_token_count=getattr(engine, "tokenize_messages", None),
    )
    trajectory_id = (
        f"{deployment_id}-{harness_id}-{task_class}-s{seed}-"
        f"{pair_variant}-{arm_config.arm}"
    )
    tools = _tools()
    if harness_id == "raw_python":
        events, bundle = RawPythonHarness(
            engine, tools=tools, arm_config=arm_config
        ).run_trajectory(
            trajectory_id=trajectory_id,
            deployment_id=deployment_id,
            workload_id=plan.workload_id,
            turns=to_raw_python_turns(plan),
            pair_id=plan.pair_id,
        )
    elif harness_id == "langgraph":
        events, bundle = LangGraphHarness(
            engine, tools=tools, arm_config=arm_config
        ).run_trajectory(
            trajectory_id=trajectory_id,
            deployment_id=deployment_id,
            workload_id=plan.workload_id,
            steps=to_langgraph_steps(plan),
            pair_id=plan.pair_id,
        )
    else:
        raise ValueError(f"unsupported rev C harness: {harness_id}")
    bundle.meta.update(
        {
            "task_class": task_class,
            "seed": seed,
            "pair_variant": pair_variant,
            "payload_manifest_sha256": plan.payload_manifest_sha256,
            "task_success": True,
            "success_metric": "script_completed_and_step_sequence_exact",
        }
    )
    return events, bundle, plan.target_tokens


def _variant_configs(*, cloud: bool, include_ablations: bool) -> list[tuple[str, ArmConfig, str]]:
    configs = [
        (
            "full",
            optimized_full(cloud=cloud, causal_class="Class_II"),
            "Class_II",
        )
    ]
    if include_ablations and not cloud:
        configs.extend(
            [
                ("cache_only", cache_only(), "Class_I"),
                (
                    "append_layout",
                    append_layout_only(cloud=False),
                    "Class_II",
                ),
            ]
        )
    return configs


def _script_success(
    *,
    bundle: ReplayBundle,
    calls: Sequence[CallRecord],
    task_class: str,
    target_tokens: int,
) -> bool:
    if (
        len(calls) != TASK_CLASSES[task_class].turns
        or calls[-1].engine_tokens_in < target_tokens
        or len(bundle.turns) != len(calls)
    ):
        return False
    prior_result_id: str | None = None
    saw_passing_tests = task_class != "TT-EDIT"
    spec = TASK_CLASSES[task_class]
    for turn in bundle.turns:
        if task_class == "TT-FAN":
            expected_names = (
                ("synthesize",)
                if turn.turn_index == spec.turns - 1
                else ("search", "read_file")
            )
        else:
            expected_names = (
                spec.tool_cycle[turn.turn_index % len(spec.tool_cycle)],
            )
        if tuple(call.name for call in turn.tool_calls) != expected_names:
            return False
        if len(turn.tool_calls) != len(turn.tool_results):
            return False
        for call, result in zip(turn.tool_calls, turn.tool_results):
            if not isinstance(result, dict) or result.get("ok") is not True:
                return False
            if result.get("result_id") != call.arguments.get("result_id"):
                return False
            if result.get("payload") != call.arguments.get("_payload", ""):
                return False
            if task_class == "TT-CHAIN" and prior_result_id is not None:
                if call.arguments.get("from_result") != prior_result_id:
                    return False
            if call.name == "run_tests":
                payload = str(result.get("payload") or "")
                saw_passing_tests = "Exit code: 0" in payload and "passed" in payload
            prior_result_id = str(result.get("result_id") or prior_result_id or "")
    return saw_passing_tests


def collect_rev_c(
    *,
    out_dir: Path,
    engine: Engine,
    deployment_id: str,
    f_prefill: Callable[[int], float],
    task_classes: Sequence[str],
    seeds: Sequence[int],
    harnesses: Sequence[str] = ("raw_python", "langgraph"),
    target: str = "cpu_prebox",
    cloud: bool = False,
    live: bool = False,
    budget_lock_path: Path | None = None,
    spent_usd: float = 0.0,
    allow_spend_override: bool = False,
    wall_projection_path: Path | None = None,
    include_ablations: bool = True,
) -> dict[str, object]:
    out_dir = Path(out_dir)
    corpus_dir = out_dir / "corpus"
    bundle_dir = out_dir / "bundles"
    event_dir = out_dir / "events"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    event_dir.mkdir(parents=True, exist_ok=True)
    payload_errors = validate_frozen_payload_manifest()
    if payload_errors:
        raise ValueError(
            "frozen rev C payload integrity failed: " + "; ".join(payload_errors)
        )
    cloud_pricing: dict[str, object] | None = None
    if cloud and not live and not engine.identity.provisional:
        raise ValueError(
            "non-provisional cloud collection requires live=True and an authorized rev C lock"
        )
    if live:
        if not cloud:
            raise ValueError("live=True is reserved for rev C cloud collection")
        from apu_characterization.turntrace_v2.spend_guard import BudgetLock

        lock = BudgetLock.load(
            budget_lock_path
            or Path(__file__).resolve().with_name("budget_lock.json")
        )
        lock.assert_live_authorized(
            expected_campaign="turntrace_rev_c_cloud_class_ii",
            payload_manifest_sha256=str(
                json.loads(
                    FROZEN_PAYLOAD_MANIFEST_PATH.read_text(encoding="utf-8")
                )["manifest_sha256"]
            ),
        )
        lock.assert_under_ceiling(
            planned_usd=lock.projected_usd,
            spent_usd=spent_usd,
            allow_override=allow_spend_override,
            label="collect_rev_c cloud campaign",
        )
        cloud_pricing = lock.cell(deployment_id)
        if str(cloud_pricing["model_id"]) != engine.identity.model_id:
            raise ValueError(
                "authorized cloud model does not match budget-lock cell model_id"
            )
        engine_base_url = getattr(engine, "base_url", None)
        lock_base_url = str(cloud_pricing.get("base_url") or "").rstrip("/")
        if engine_base_url is not None and lock_base_url:
            if str(engine_base_url).rstrip("/") != lock_base_url:
                raise ValueError(
                    "authorized cloud base_url does not match budget-lock cell base_url"
                )
        engine_provider = getattr(engine, "provider", None)
        lock_provider = cloud_pricing.get("provider")
        if engine_provider is not None and lock_provider is not None:
            if str(engine_provider) != str(lock_provider):
                raise ValueError(
                    "authorized cloud provider does not match budget-lock cell provider"
                )
    if not cloud and not engine.identity.provisional:
        if wall_projection_path is None or not Path(wall_projection_path).is_file():
            raise ValueError(
                "G-BUDGET-WALL: calibrated local collection requires a wall projection artifact"
            )
        wall_projection = json.loads(
            Path(wall_projection_path).read_text(encoding="utf-8")
        )
        frozen_payload_hash = str(
            json.loads(
                FROZEN_PAYLOAD_MANIFEST_PATH.read_text(encoding="utf-8")
            )["manifest_sha256"]
        )
        if wall_projection.get("schema_version") != "turntrace_rev_c_cpu_wall_v1":
            raise ValueError("G-BUDGET-WALL: unknown wall projection schema")
        if not wall_projection.get("profile_r2_passed"):
            raise ValueError("G-BUDGET-WALL: profile R2 gate not recorded as passed")
        if not wall_projection.get("prefill_profile_sha256"):
            raise ValueError("G-BUDGET-WALL: prefill profile hash missing")
        if wall_projection.get("protocol_sha256") != protocol_sha256():
            raise ValueError("G-BUDGET-WALL: protocol hash mismatch")
        if wall_projection.get("payload_manifest_sha256") != frozen_payload_hash:
            raise ValueError("G-BUDGET-WALL: payload manifest hash mismatch")
        if wall_projection.get("exceeds_24h"):
            raise ValueError(
                "G-BUDGET-WALL: projection exceeds 24h; record a CPU-only cut before launch"
            )
        for key, observed in (
            ("model_id", engine.identity.model_id),
            ("quantization", engine.identity.quantization),
            ("engine", engine.identity.engine),
            ("hardware", engine.identity.hardware),
        ):
            if str(wall_projection.get(key)) != str(observed):
                raise ValueError(f"G-BUDGET-WALL: projection {key} mismatch")
    catalog = build_payload_catalog()
    manifest = json.loads(
        FROZEN_PAYLOAD_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    observed_manifest = payload_manifest_dict(catalog)
    if observed_manifest["manifest_sha256"] != manifest.get("manifest_sha256"):
        raise ValueError("current suite definition does not match frozen payload manifest")
    (out_dir / "payload_manifest.json").write_text(
        FROZEN_PAYLOAD_MANIFEST_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    use_cache_parameter = inspect.signature(engine.complete).parameters.get(
        "use_cache"
    )
    baseline_default_is_disabled = bool(
        use_cache_parameter is not None
        and use_cache_parameter.default is False
    )
    if cloud:
        # Cloud Arm A keeps incidental provider cache hits; never force them to
        # zero. Local use_cache defaults are not the honesty axis here.
        arm_a_honesty_pass = True
        baseline_settings = {
            "cache_control": "provider_default_incidental_hits_allowed",
            "source": (
                "OpenAI automatic prompt caching; baseline makes no "
                "prefix-stability effort and records reported cached_tokens"
            ),
            "context_assembly": "fresh complete message list per turn",
            "dynamic_prefix_injected": False,
            "forced_cache_miss": False,
        }
        arm_a_honesty_note = (
            "Cloud Arm A preserves provider-default caching with no artificial "
            "cache zeroing and no injected timestamps/counters."
        )
    else:
        arm_a_honesty_pass = baseline_default_is_disabled
        baseline_settings = {
            "use_cache": False,
            "source": "existing Engine.complete default and pre-rev-C harness call path",
            "context_assembly": "fresh complete message list per turn",
            "dynamic_prefix_injected": False,
        }
        arm_a_honesty_note = (
            "No timestamps/counters or artificial cache misses are injected; "
            "the baseline preserves this repository's adapter defaults."
        )
    effective_settings = {
        "schema_version": "turntrace_rev_c_effective_settings_v1",
        "deployment_id": deployment_id,
        "engine": engine.identity.engine,
        "engine_version": engine.identity.engine_version,
        "model_id": engine.identity.model_id,
        "quantization": engine.identity.quantization,
        "hardware": engine.identity.hardware,
        "harnesses": list(harnesses),
        "cloud": bool(cloud),
        "baseline_naive": baseline_settings,
        "orchestration_optimized": {
            "full_local": ["B-CACHE", "B-APPEND", "B-LAYOUT"],
            "full_cloud": ["B-APPEND", "B-LAYOUT", "B-SHAPE"],
        },
        "arm_a_honesty": arm_a_honesty_note,
        "arm_a_honesty_pass": arm_a_honesty_pass,
        "local_use_cache_default_disabled": baseline_default_is_disabled,
    }
    effective_settings["sha256"] = sha256_bytes(
        canonical_json_bytes(effective_settings)
    )
    (out_dir / "effective_settings.json").write_text(
        json.dumps(effective_settings, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if (
        not cloud
        and not baseline_default_is_disabled
        and not engine.identity.provisional
    ):
        raise ValueError(
            "G-ARM-A-HONESTY: engine use_cache default is not cache-disabled"
        )

    all_calls: list[CallRecord] = []
    all_trajectories: list[TrajectoryRecord] = []
    pair_audits: list[dict[str, object]] = []

    for task_class in task_classes:
        if task_class not in TASK_CLASSES:
            raise ValueError(f"unknown task class: {task_class}")
        for seed in seeds:
            if seed not in SEEDS:
                raise ValueError(f"seed {seed} not in frozen seed set {SEEDS}")
            for harness_id in harnesses:
                variants = _variant_configs(
                    cloud=cloud,
                    include_ablations=include_ablations
                    and task_class in ABLATION_CLASSES,
                )
                for variant, optimized, causal_class in variants:
                    baseline_config = baseline(causal_class=causal_class)
                    arm_data: dict[
                        str,
                        tuple[
                            list[CallRecord],
                            TrajectoryRecord,
                            ReplayBundle,
                            list[RawModelCallEvent],
                        ],
                    ] = {}
                    for config in (baseline_config, optimized):
                        events, bundle, target_tokens = _run_one(
                            engine=engine,
                            arm_config=config,
                            task_class=task_class,
                            seed=seed,
                            harness_id=harness_id,
                            deployment_id=deployment_id,
                            pair_variant=variant,
                            target=target,
                            catalog=catalog,
                        )
                        bundle_path = bundle_dir / f"{bundle.trajectory_id}.ttbundle"
                        calls = derive_call_records(events, f_prefill=f_prefill)
                        task_success = _script_success(
                            bundle=bundle,
                            calls=calls,
                            task_class=task_class,
                            target_tokens=target_tokens,
                        )
                        bundle.meta["task_success"] = task_success
                        save_bundle(bundle, bundle_path)
                        model_cost = 0.0
                        if cloud_pricing is not None:
                            model_cost = calculate_model_cost(
                                calls,
                                usd_per_1m_input=float(
                                    cloud_pricing["usd_per_1m_in"]
                                ),
                                usd_per_1m_cached_input=float(
                                    cloud_pricing["usd_per_1m_cached_in"]
                                ),
                                usd_per_1m_output=float(
                                    cloud_pricing["usd_per_1m_out"]
                                ),
                            ).total_usd
                        trajectory = derive_trajectory_record(
                            calls,
                            workload_id=f"turntrace_rev_c:{task_class}",
                            cache_mode=(
                                "engine-retained"
                                if config.use_cache
                                else "engine-default"
                                if cloud
                                else "cache-disabled"
                            ),
                            task_success=task_success,
                            success_metric="script_completed_context_target_reached",
                            replay_bundle_path=str(bundle_path),
                            total_cost_usd=model_cost,
                            usd_model_cost=model_cost,
                            headline=False,
                        )
                        arm_data[config.arm] = (calls, trajectory, bundle, events)
                        all_calls.extend(calls)
                        all_trajectories.append(trajectory)
                        (event_dir / f"{bundle.trajectory_id}.events.json").write_text(
                            json.dumps(
                                [event.__dict__ for event in events],
                                indent=2,
                                sort_keys=True,
                                default=str,
                            ),
                            encoding="utf-8",
                        )
                    calls_a, traj_a, bundle_a, _ = arm_data["baseline_naive"]
                    calls_b, traj_b, bundle_b, _ = arm_data[
                        "orchestration_optimized"
                    ]
                    pair_audits.append(
                        audit_pair(
                            calls_a,
                            calls_b,
                            trajectory_a=traj_a,
                            trajectory_b=traj_b,
                            causal_class=causal_class,
                            bundle_a=bundle_a,
                            bundle_b=bundle_b,
                        ).to_dict()
                    )

    cache_truth_flags = (
        []
        if cloud
        else audit_cache_truth(all_calls, f_prefill=f_prefill)
    )
    export_parquet(all_calls, all_trajectories, corpus_dir)
    all_pairs_pass = all(bool(row["passed"]) for row in pair_audits)
    all_tasks_success = all(bool(trajectory.task_success) for trajectory in all_trajectories)
    replication_pass = len(set(seeds)) >= 5
    suite_complete = set(task_classes) == set(TASK_CLASSES)
    harnesses_complete = set(harnesses) == {"raw_python", "langgraph"}
    calls_headline_clean = len(headline_eligible(all_calls)) == len(all_calls)
    validity = (
        "debug_only"
        if engine.identity.provisional
        else "headline_candidate"
        if (
            all_pairs_pass
            and all_tasks_success
            and replication_pass
            and suite_complete
            and harnesses_complete
            and not cache_truth_flags
            and arm_a_honesty_pass
            and calls_headline_clean
        )
        else "audit_failed"
    )
    report: dict[str, object] = {
        "validity": validity,
        "deployment_id": deployment_id,
        "task_classes": list(task_classes),
        "seeds": list(seeds),
        "harnesses": list(harnesses),
        "target": target,
        "n_calls": len(all_calls),
        "n_trajectories": len(all_trajectories),
        "n_pairs": len(pair_audits),
        "all_pairs_pass": all_pairs_pass,
        "all_tasks_success": all_tasks_success,
        "replication_pass": replication_pass,
        "suite_complete": suite_complete,
        "harnesses_complete": harnesses_complete,
        "calls_headline_clean": calls_headline_clean,
        "cache_truth_pass": not cache_truth_flags,
        "cache_truth_flags": cache_truth_flags,
        "pair_audits": pair_audits,
        "payload_manifest_sha256": manifest["manifest_sha256"],
        "effective_settings_sha256": effective_settings["sha256"],
        "arm_a_honesty_pass": arm_a_honesty_pass,
        "note": "No rev C result is headline until all gates and n>=5 bands pass.",
    }
    (out_dir / "collect_rev_c_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task-class", action="append", choices=sorted(TASK_CLASSES))
    parser.add_argument("--seed", action="append", type=int)
    parser.add_argument("--harness", action="append", choices=("raw_python", "langgraph"))
    parser.add_argument("--target", choices=("cpu_prebox", "box"), default="cpu_prebox")
    parser.add_argument("--no-ablations", action="store_true")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Reserved: rev C live collection is blocked until its budget lock is authorized.",
    )
    args = parser.parse_args(argv)
    if args.live:
        raise SystemExit(
            "rev C --live is blocked: use the future authorized cloud entrypoint "
            "after payload/token lock and G-BUDGET-WALL"
        )
    engine = _mock_engine("CPU0", "rev-c-mock")
    report = collect_rev_c(
        out_dir=args.out,
        engine=engine,
        deployment_id="CPU0",
        f_prefill=lambda n: 0.5 + 0.002 * float(n) + 1e-8 * float(n) ** 2,
        task_classes=args.task_class or ["TT-EDIT"],
        seeds=args.seed or [0],
        harnesses=args.harness or ["raw_python", "langgraph"],
        target=args.target,
        include_ablations=not args.no_ablations,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
