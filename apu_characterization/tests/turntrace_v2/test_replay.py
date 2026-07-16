from __future__ import annotations

from pathlib import Path

from apu_characterization.turntrace_v2.mock_engine import MockEngine
from apu_characterization.turntrace_v2.replay import (
    EnvSnapshotRef,
    ReplayBundle,
    ToolCall,
    TurnBundle,
    context_delta_tokens,
    estimate_bundle_bytes,
    load_bundle,
    reconstruct_context_tokens,
    save_bundle,
    swapped_step_replay,
)


def _bundle(traj_id: str = "r1") -> ReplayBundle:
    env = EnvSnapshotRef(git_commit="abc", container_image_id="img")
    bundle = ReplayBundle(
        trajectory_id=traj_id,
        workload_id="swebench_lite_synthetic",
        harness_id="raw_python",
        deployment_id="L1b",
        meta={"task_success": True},
    )
    contexts = [
        "sys task",
        "sys task user look",
        "sys task user look tool ok",
    ]
    prior: list[str] = []
    for i, ctx in enumerate(contexts):
        tokens = ctx.split()
        delta = context_delta_tokens(prior, tokens)
        bundle.append_turn(
            TurnBundle(
                turn_index=i,
                assembled_context=ctx,
                raw_model_output=f"out{i}",
                tool_calls=[ToolCall(name="read_file", arguments={"i": i})],
                tool_results=[{"i": i}],
                sampling_params={"temperature": 0, "seed": 0, "max_tokens": 4},
                reasoning_mode="off",
                env_snapshot_ref=env,
                tokenizer_id="whitespace_v0",
                context_delta_tokens=delta,
                context_full_tokens=tokens,
            )
        )
        prior = tokens
    return bundle


def test_context_delta_roundtrip() -> None:
    prior = "a b c".split()
    current = "a b c d e".split()
    delta = context_delta_tokens(prior, current)
    assert reconstruct_context_tokens(prior, delta) == current


def test_append_only_bundle(tmp_path: Path) -> None:
    bundle = _bundle()
    path = tmp_path / "r1.ttbundle"
    save_bundle(bundle, path)
    loaded = load_bundle(path)
    assert loaded.trajectory_id == "r1"
    assert len(loaded.turns) == 3
    try:
        loaded.append_turn(loaded.turns[0])
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_swapped_step_replay_from_archive_alone(tmp_path: Path) -> None:
    bundle = _bundle("r2")
    path = tmp_path / "r2.ttbundle"
    save_bundle(bundle, path)
    # Reload — no reference to original in-memory objects beyond path.
    archived = load_bundle(path)
    engine = MockEngine()
    result = swapped_step_replay(
        archived,
        swap_turn=1,
        model_fn=engine.as_model_fn(fixed_output="swapped"),
        model_id="swap-model",
        reasoning_mode="on",
    )
    assert result.success is True
    assert result.outputs[0] == "out0"  # prefix from archive
    assert result.outputs[1] == "swapped"
    assert result.tool_replay_modes
    assert any(m["mode"] in ("live", "archived") for m in result.tool_replay_modes)


def test_delta_storage_smaller() -> None:
    bundle = _bundle("r3")
    sizes = estimate_bundle_bytes(bundle, use_deltas=True)
    assert sizes["delta_json_bytes"] <= sizes["full_json_bytes"]
