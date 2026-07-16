from __future__ import annotations

from pathlib import Path

from apu_characterization.turntrace_v2.calibration import synthesize_prefill_sweep
from apu_characterization.turntrace_v2.derive import (
    RawModelCallEvent,
    derive_call_records,
    derive_trajectory_record,
)
from apu_characterization.turntrace_v2.export import export_parquet, load_call_records_jsonl


def _events(traj_id: str = "d1") -> list[RawModelCallEvent]:
    events = []
    # Engine-token ids grow each turn (post-template currency).
    ids: list[int] = list(range(64))
    t0 = 0.0
    for i in range(4):
        ids = ids + list(range(1000 + i * 10, 1000 + i * 10 + 32))
        n = len(ids)
        # Timings roughly match synthesize_prefill_sweep f(n)=1e-8 n^2 + 2e-3 n + 0.5
        prefill = 1e-8 * (n**2) + 2e-3 * n + 0.5
        decode = 2.0
        orch_pre, orch_post = 1.0, 1.0
        wall = (orch_pre + prefill + decode + orch_post) / 1000.0
        events.append(
            RawModelCallEvent(
                trajectory_id=traj_id,
                turn_index=i,
                harness_id="raw_python",
                deployment_id="L1b",
                assembled_context=" ".join(f"t{j}" for j in ids),
                raw_model_output="ok answer",
                tool_names=("read_file",) if i % 2 == 0 else ("edit_file",),
                t_orch_pre_ms=orch_pre,
                t_orch_post_ms=orch_post,
                t_network_ms=0.0,
                t_prefill_ms=prefill,
                t_decode_ms=decode,
                engine_tokens_in=n,
                requested_tokens_in=n,
                engine_token_ids=tuple(ids),
                tokens_out=2,
                cache_state="disabled",
                model_id="synthetic-local",
                quantization="fp16",
                reasoning_mode="off",
                engine="mock",
                engine_version="0.1",
                wall_clock_start=t0 + i,
                wall_clock_end=t0 + i + wall,
                expected_horizon=4,
            )
        )
    return events


def test_derive_call_records_and_trajectory(tmp_path: Path) -> None:
    profile = synthesize_prefill_sweep(
        seed=5, n_grid=(32, 64, 128, 256, 512, 1024), reps=10
    )
    gmin = min(n for n, _ in profile.points)
    gmax = max(n for n, _ in profile.points)
    calls = derive_call_records(
        _events(), f_prefill=profile.predict_ms, grid_min=gmin, grid_max=gmax
    )
    assert len(calls) == 4
    assert calls[0].step_type_semantic == "read_file"
    assert calls[1].step_features.tool_class == "state_mutating"
    assert calls[0].engine_tokens_in == calls[0].context_tokens_in
    assert calls[-1].prefill_redundant_tokens >= calls[0].prefill_redundant_tokens
    traj = derive_trajectory_record(
        calls,
        workload_id="swebench_lite_synthetic",
        cache_mode="cache-disabled",
        task_success=True,
        success_metric="swebench_pass",
        replay_bundle_path=str(tmp_path / "bundle.ttbundle"),
        headline=True,
    )
    assert traj.n_turns == 4
    assert traj.replay_bundle_path


def test_export_roundtrip(tmp_path: Path) -> None:
    profile = synthesize_prefill_sweep(
        seed=5, n_grid=(32, 64, 128, 256, 512, 1024), reps=10
    )
    calls = derive_call_records(_events("e1"), f_prefill=profile.predict_ms)
    traj = derive_trajectory_record(
        calls,
        workload_id="swebench_lite_synthetic",
        cache_mode="cache-disabled",
        task_success=False,
        success_metric="swebench_pass",
        replay_bundle_path=None,
        headline=False,
    )
    paths = export_parquet(calls, [traj], tmp_path)
    loaded = load_call_records_jsonl(paths["calls"])
    assert len(loaded) == len(calls)
    assert loaded[0].trajectory_id == "e1"
    assert loaded[0].engine_tokens_in == loaded[0].context_tokens_in
    assert (tmp_path / "SCHEMA.md").exists()
