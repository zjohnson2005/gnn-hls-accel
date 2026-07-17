from __future__ import annotations

import hashlib
import json
from pathlib import Path

from apu_characterization.turntrace_v2.arms import (
    append_layout_only,
    baseline,
    cache_only,
)
from apu_characterization.turntrace_v2.audit import audit_pair
from apu_characterization.turntrace_v2.collect_cloud import _mock_engine
from apu_characterization.turntrace_v2.collect_rev_c import collect_rev_c
from apu_characterization.turntrace_v2.contracts import (
    canonical_json_bytes,
    validate_protocol_lock,
)
from apu_characterization.turntrace_v2.derive import (
    RawModelCallEvent,
    derive_call_records,
    derive_trajectory_record,
)
from apu_characterization.turntrace_v2.exchange import (
    aggregate_exchange,
    derive_pair_exchange,
)
from apu_characterization.turntrace_v2.engines.openai_compat import (
    cached_tokens_from_usage,
)
from apu_characterization.turntrace_v2.economics import (
    calculate_model_cost,
    provider_three_way_split,
)
from apu_characterization.turntrace_v2.replay import (
    EnvSnapshotRef,
    ReplayBundle,
    TurnBundle,
)
from apu_characterization.turntrace_v2.schema import TrajectoryRecord
from apu_characterization.turntrace_v2.spend_guard import (
    BudgetLock,
    SpendLockNotAuthorized,
)
from apu_characterization.turntrace_v2.workload.rev_c_suite import (
    TASK_CLASSES,
    build_payload_catalog,
    build_suite_plan,
    validate_frozen_payload_manifest,
)
from apu_characterization.turntrace_v2.wall_budget import project_cpu_wall


def _calls(arm: str, pair_id: str, redundant_ms: float, orch_ms: float):
    events = []
    ids: list[int] = []
    for turn in range(2):
        ids.extend(range(turn * 10, turn * 10 + 10))
        events.append(
            RawModelCallEvent(
                trajectory_id=f"{pair_id}:{arm}",
                turn_index=turn,
                harness_id="raw_python",
                deployment_id="CPU0",
                assembled_context="x " * len(ids),
                raw_model_output="ok",
                tool_names=("read_file",),
                t_orch_pre_ms=orch_ms / 2,
                t_orch_post_ms=orch_ms / 2,
                t_prefill_ms=5.0 + redundant_ms / 2,
                t_decode_ms=1.0,
                engine_tokens_in=len(ids),
                requested_tokens_in=len(ids),
                engine_token_ids=tuple(ids),
                tokens_out=1,
                model_id="mock",
                quantization="n/a",
                reasoning_mode="off",
                engine="mock",
                engine_version="0",
                wall_clock_start=float(turn),
                wall_clock_end=float(turn) + (orch_ms + 6.0 + redundant_ms / 2) / 1000,
                arm=arm,
                interventions_active=("B-CACHE",) if arm == "orchestration_optimized" else (),
                pair_id=pair_id,
                expected_horizon=2,
            )
        )
    return derive_call_records(events, f_prefill=lambda _n: 5.0)


def _bundle(trajectory_id: str, pair_id: str, arm: str) -> ReplayBundle:
    bundle = ReplayBundle(
        trajectory_id=trajectory_id,
        workload_id="turntrace_rev_c:TT-EDIT",
        harness_id="raw_python",
        deployment_id="CPU0",
        meta={"pair_id": pair_id, "arm": arm},
    )
    for turn in range(2):
        bundle.append_turn(
            TurnBundle(
                turn_index=turn,
                assembled_context=[{"role": "user", "content": f"turn {turn}"}],
                raw_model_output="ok",
                tool_calls=[],
                tool_results=[],
                sampling_params={"temperature": 0},
                reasoning_mode="off",
                env_snapshot_ref=EnvSnapshotRef("abc", "local:no-container"),
                tokenizer_id="mock",
            )
        )
    return bundle


def test_rev_c_protocol_lock_validates() -> None:
    assert validate_protocol_lock() == []


def test_suite_has_five_classes_and_class_i_is_byte_identical() -> None:
    assert set(TASK_CLASSES) == {
        "TT-EDIT",
        "TT-RET",
        "TT-FAN",
        "TT-DOC",
        "TT-CHAIN",
    }
    catalog = build_payload_catalog()
    arm_a = build_suite_plan(
        "TT-EDIT",
        seed=0,
        arm_config=baseline(causal_class="Class_I"),
        harness_id="raw_python",
        deployment_id="CPU0",
        catalog=catalog,
    )
    arm_b = build_suite_plan(
        "TT-EDIT",
        seed=0,
        arm_config=cache_only(),
        harness_id="raw_python",
        deployment_id="CPU0",
        catalog=catalog,
    )
    assert arm_a.messages_by_turn == arm_b.messages_by_turn
    class_ii = build_suite_plan(
        "TT-EDIT",
        seed=0,
        arm_config=append_layout_only(),
        harness_id="raw_python",
        deployment_id="CPU0",
        catalog=catalog,
    )
    assert class_ii.messages_by_turn != arm_a.messages_by_turn


def test_pair_gate_and_exchange_rate() -> None:
    pair_id = "TT-EDIT:0:raw_python:CPU0:cache_only"
    calls_a = _calls("baseline_naive", pair_id, redundant_ms=10.0, orch_ms=2.0)
    calls_b = _calls("orchestration_optimized", pair_id, redundant_ms=2.0, orch_ms=3.0)
    bundle_a = _bundle(calls_a[0].trajectory_id, pair_id, "baseline_naive")
    bundle_b = _bundle(calls_b[0].trajectory_id, pair_id, "orchestration_optimized")
    traj_a = derive_trajectory_record(
        calls_a,
        workload_id="turntrace_rev_c:TT-EDIT",
        cache_mode="cache-disabled",
        task_success=True,
        success_metric="exact",
        replay_bundle_path="a.ttbundle",
        total_cost_usd=1.0,
    )
    traj_b = derive_trajectory_record(
        calls_b,
        workload_id="turntrace_rev_c:TT-EDIT",
        cache_mode="engine-retained",
        task_success=True,
        success_metric="exact",
        replay_bundle_path="b.ttbundle",
        total_cost_usd=0.4,
    )
    gate = audit_pair(
        calls_a,
        calls_b,
        trajectory_a=traj_a,
        trajectory_b=traj_b,
        causal_class="Class_I",
        bundle_a=bundle_a,
        bundle_b=bundle_b,
    )
    assert gate.passed
    row = derive_pair_exchange(
        calls_a,
        calls_b,
        trajectory_a=traj_a,
        trajectory_b=traj_b,
        redundant_ideal_ms=0.0,
    )
    assert row.recovered_fraction is not None and row.recovered_fraction > 0
    assert row.exchange_rate_ms_per_ms is not None
    assert aggregate_exchange([row]) == []
    aggregate = aggregate_exchange([row], include_sparse=True)
    assert aggregate[0]["sparse_n_lt_5"] is True


def test_rev_c_mock_collection_is_paired(tmp_path: Path) -> None:
    engine = _mock_engine("CPU0", "rev-c-mock")
    report = collect_rev_c(
        out_dir=tmp_path,
        engine=engine,
        deployment_id="CPU0",
        f_prefill=lambda n: 0.5 + 0.002 * n + 1e-8 * n**2,
        task_classes=["TT-FAN"],
        seeds=[0],
        harnesses=["raw_python"],
        target="cpu_prebox",
        include_ablations=False,
    )
    assert report["n_pairs"] == 1
    assert report["all_pairs_pass"] is True
    assert report["cache_truth_pass"] is True
    assert report["arm_a_honesty_pass"] is True
    assert (tmp_path / "payload_manifest.json").is_file()
    assert (tmp_path / "corpus" / "call_records.jsonl").is_file()


def test_cpu_wall_projection_counts_full_and_ablation_calls() -> None:
    projection = project_cpu_wall(
        lambda n: float(n),
        model_id="candidate",
        quantization="Q4_K_M",
        engine="llama.cpp",
        hardware="cpu",
        seeds=1,
        harnesses=1,
    )
    assert projection.total_calls == 314
    assert projection.projected_wall_hours > 0


def test_cloud_economics_uses_provider_cached_tokens() -> None:
    assert cached_tokens_from_usage(
        {"prompt_tokens_details": {"cached_tokens": 128}}
    ) == 128
    assert cached_tokens_from_usage(
        {"input_tokens_details": {"cached_tokens": 256}}
    ) == 256
    pair_id = "TT-EDIT:0:raw_python:C1:full"
    calls = _calls("baseline_naive", pair_id, redundant_ms=10.0, orch_ms=2.0)
    calls[1].provider_cached_tokens = 5
    calls[1].structurally_redundant_tokens = 10
    calls[1].actually_recomputed_tokens = 5
    cost = calculate_model_cost(
        calls,
        usd_per_1m_input=2.0,
        usd_per_1m_cached_input=0.5,
        usd_per_1m_output=8.0,
    )
    assert cost.cached_input_tokens == 5
    split = provider_three_way_split(calls)
    assert split["provider_recovered_tokens"] == 5
    assert split["reconciliation_delta_tokens"] == 0


def test_class_i_rejects_stale_context_hash() -> None:
    pair_id = "TT-EDIT:0:raw_python:CPU0:cache_only"
    calls_a = _calls("baseline_naive", pair_id, redundant_ms=1.0, orch_ms=1.0)
    calls_b = _calls("orchestration_optimized", pair_id, redundant_ms=0.0, orch_ms=1.0)
    traj_a = derive_trajectory_record(
        calls_a,
        workload_id="turntrace_rev_c:TT-EDIT",
        cache_mode="cache-disabled",
        task_success=True,
        success_metric="exact",
        replay_bundle_path="a",
    )
    traj_b = derive_trajectory_record(
        calls_b,
        workload_id="turntrace_rev_c:TT-EDIT",
        cache_mode="engine-retained",
        task_success=True,
        success_metric="exact",
        replay_bundle_path="b",
    )
    bundle_a = _bundle(calls_a[0].trajectory_id, pair_id, "baseline_naive")
    bundle_b = _bundle(calls_b[0].trajectory_id, pair_id, "orchestration_optimized")
    bundle_b.turns[0].context_byte_sha256 = "stale"
    result = audit_pair(
        calls_a,
        calls_b,
        trajectory_a=traj_a,
        trajectory_b=traj_b,
        causal_class="Class_I",
        bundle_a=bundle_a,
        bundle_b=bundle_b,
    )
    assert not result.passed
    assert "pair_context_divergence" in result.flags


def test_payload_source_tampering_is_detected(tmp_path: Path) -> None:
    source = tmp_path / "payload.txt"
    source.write_text("real payload", encoding="utf-8")
    raw = source.read_bytes()
    rel = "payload.txt"
    corpus = f"\n\n--- SOURCE: {rel} ---\nreal payload"
    manifest = {
        "schema_version": "turntrace_rev_c_payload_v1",
        "source_kind": "real_repository_content",
        "sources": [
            {
                "path": rel,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        ],
        "corpus_sha256": hashlib.sha256(corpus.encode()).hexdigest(),
        "corpus_bytes": len(corpus.encode()),
        "task_classes": {},
        "seeds": [0],
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        canonical_json_bytes(manifest)
    ).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_frozen_payload_manifest(path, repo_root=tmp_path) == []
    source.write_text("tampered", encoding="utf-8")
    assert any(
        "payload source" in error
        for error in validate_frozen_payload_manifest(path, repo_root=tmp_path)
    )


def test_legacy_trajectory_aliases_migrate() -> None:
    legacy = {
        "trajectory_id": "legacy",
        "workload_id": "old",
        "harness_id": "raw_python",
        "deployment_id": "C1",
        "cache_mode": "provider_default",
        "task_success": True,
        "success_metric": "old",
        "n_turns": 1,
        "total_wall_clock_ms": 1.0,
        "total_cost_usd": 2.5,
        "total_energy_j": 3.5,
        "replay_bundle_path": "legacy.ttbundle",
    }
    record = TrajectoryRecord.from_dict(legacy)
    assert record.usd_model_cost == 2.5
    assert record.joules_total == 3.5


def test_ablations_bind_to_edit_and_ret_only(tmp_path: Path) -> None:
    """Ablations must follow frozen TT-EDIT/TT-RET, not the caller's class order."""
    engine = _mock_engine("CPU0", "rev-c-mock")
    report = collect_rev_c(
        out_dir=tmp_path,
        engine=engine,
        deployment_id="CPU0",
        f_prefill=lambda n: 0.5 + 0.002 * n + 1e-8 * n**2,
        task_classes=["TT-FAN", "TT-EDIT"],
        seeds=[0],
        harnesses=["raw_python"],
        target="cpu_prebox",
        include_ablations=True,
    )
    # TT-FAN full only (1 pair); TT-EDIT full + cache_only + append_layout (3).
    assert report["n_pairs"] == 4
    variants = {
        str(row["pair_id"]).rsplit(":", 1)[-1]
        for row in report["pair_audits"]
    }
    assert variants == {"full", "cache_only", "append_layout"}
    fan_pairs = [
        row for row in report["pair_audits"] if "TT-FAN" in str(row["pair_id"])
    ]
    assert len(fan_pairs) == 1
    assert str(fan_pairs[0]["pair_id"]).endswith(":full")


def test_budget_authorization_binds_campaign(tmp_path: Path) -> None:
    raw = json.loads(
        Path("apu_characterization/turntrace_v2/budget_lock.json").read_text(
            encoding="utf-8"
        )
    )
    raw["live_authorized"] = True
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    lock = BudgetLock.load(path)
    try:
        lock.assert_live_authorized(expected_campaign="turntrace_rev_b_p2_historical")
    except SpendLockNotAuthorized:
        pass
    else:
        raise AssertionError("campaign mismatch must block live use")
