"""C-P2 gates: model lock, calibration R², wall-projection abort path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apu_characterization.turntrace_v2.collect_rev_c import _variant_configs
from apu_characterization.turntrace_v2.model_lock import (
    MODEL_LOCK_PATH,
    validate_model_lock,
)
from apu_characterization.turntrace_v2.wall_budget import (
    main as wall_main,
    project_cpu_wall,
)


def test_model_lock_file_exists_and_schema() -> None:
    assert MODEL_LOCK_PATH.is_file()
    lock = json.loads(MODEL_LOCK_PATH.read_text(encoding="utf-8"))
    assert lock["schema_version"] == "turntrace_rev_c_model_lock_v1"
    assert lock["quantization"] == "Q4_K_M"
    assert int(lock["n_ctx_pinned"]) >= 16384
    assert lock["tool_role_remap"] is False
    assert len(lock["sha256"]) == 64


def test_model_lock_validates_against_pinned_gguf() -> None:
    errors = validate_model_lock(require_file=True)
    assert errors == [], errors


def test_model_lock_detects_sha_tamper(tmp_path: Path) -> None:
    lock = json.loads(MODEL_LOCK_PATH.read_text(encoding="utf-8"))
    lock["sha256"] = "0" * 64
    path = tmp_path / "bad_lock.json"
    path.write_text(json.dumps(lock), encoding="utf-8")
    errors = validate_model_lock(path, require_file=True)
    assert any("sha256 mismatch" in err for err in errors)


def test_class_i_wall_projection_counts_edit_ret_pairs_only() -> None:
    projection = project_cpu_wall(
        lambda n: float(n),
        model_id="Qwen2.5-1.5B-Instruct",
        quantization="Q4_K_M",
        engine="llama.cpp",
        hardware="cpu-host",
        seeds=1,
        harnesses=1,
        plan="class_i",
        task_classes=("TT-EDIT", "TT-RET"),
        include_ablations=True,
        profile_r2_passed=True,
    )
    # 2 arms × (cache_only + append_layout) × seeds×harnesses × (EDIT+RET turns)
    assert projection.total_calls == 2 * 2 * 1 * (20 + 18)
    assert projection.exceeds_24h is False


def test_wall_projection_aborts_when_over_24h_without_allow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = {
        "model_id": "slow",
        "quantization": "Q4_K_M",
        "engine": "llama.cpp",
        "hardware": "cpu-host",
        "quadratic": {
            "passed_r2_gate": True,
            "params": {"a": 0.0, "b": 50.0, "c": 1000.0},
        },
        "piecewise": {"passed_r2_gate": False},
    }
    profile_path = tmp_path / "prefill_profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    out = tmp_path / "wall.json"
    code = wall_main(
        [
            "--profile",
            str(profile_path),
            "--out",
            str(out),
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
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "G-BUDGET-WALL ABORT" in captured.out
    assert not out.is_file()


def test_wall_projection_refuses_uncalibrated_profile(tmp_path: Path) -> None:
    profile = {
        "model_id": "x",
        "quantization": "Q4_K_M",
        "engine": "llama.cpp",
        "hardware": "cpu",
        "quadratic": {"passed_r2_gate": False, "params": {"a": 0, "b": 1, "c": 0}},
        "piecewise": {"passed_r2_gate": False},
    }
    profile_path = tmp_path / "prefill_profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        wall_main(
            [
                "--profile",
                str(profile_path),
                "--out",
                str(tmp_path / "wall.json"),
            ]
        )
    assert "R2" in str(exc.value)


def test_class_i_only_variants_are_cache_and_append_layout() -> None:
    variants = _variant_configs(
        cloud=False, include_ablations=True, class_i_only=True
    )
    assert [row[0] for row in variants] == ["cache_only", "append_layout"]
    assert variants[0][2] == "Class_I"
    assert set(variants[0][1].interventions_active) == {"B-CACHE"}
    assert set(variants[1][1].interventions_active) == {"B-APPEND", "B-LAYOUT"}
