"""INF-5 / AM-040: run_environment required on seal; refuse if any field absent."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest

from seam.config import ResolvedConfig
from seam.errors import ManifestValidationError
from seam.gitinfo import GitState
from seam.manifest import build_manifest, emit, load_schema, validate_manifest
from seam.run_environment import REQUIRED_RUN_ENVIRONMENT_FIELDS, require_run_environment
from tests.conftest import INF5_TEST_RUN_ENVIRONMENT

VERIFIED_TOPOLOGY = {"p_cpus": [0, 1, 2, 3], "lpe_cpus": [4, 5, 6, 7], "verified": True}


def _complete_env() -> dict[str, Any]:
    return dict(INF5_TEST_RUN_ENVIRONMENT)


def test_schema_version_enum_includes_1_1() -> None:
    load_schema.cache_clear()
    schema = load_schema()
    assert schema["properties"]["spec_version"]["enum"] == ["1.0", "1.1"]
    assert "run_environment" in schema["properties"]


def test_spec_1_0_manifest_valid_without_run_environment(
    fake_config: ResolvedConfig,
    fake_repo: Path,
    clean_git_state: GitState,
    minimal_workload: dict[str, Any],
) -> None:
    """Historical seals stay schema-valid; raw/ is never rewritten."""
    load_schema.cache_clear()
    manifest = build_manifest(
        run_id=str(uuid.uuid4()),
        config=fake_config,
        git_state=clean_git_state,
        allow_dirty=False,
        target="npu",
        workload=minimal_workload,
        condition_label="A",
        blinded_label="cond_0123456789ab",
        repo_root=fake_repo,
        topology_override=VERIFIED_TOPOLOGY,
        run_environment=_complete_env(),
        capture_run_environment_host=False,
    )
    manifest["spec_version"] = "1.0"
    del manifest["run_environment"]
    validate_manifest(manifest)


@pytest.mark.parametrize("missing_field", list(REQUIRED_RUN_ENVIRONMENT_FIELDS))
def test_require_run_environment_refuses_each_absent_field(missing_field: str) -> None:
    env = _complete_env()
    env[missing_field] = None
    with pytest.raises(ManifestValidationError, match=missing_field):
        require_run_environment(env)


@pytest.mark.parametrize("missing_field", list(REQUIRED_RUN_ENVIRONMENT_FIELDS))
def test_build_manifest_refuses_seal_when_field_absent(
    missing_field: str,
    fake_config: ResolvedConfig,
    fake_repo: Path,
    clean_git_state: GitState,
    minimal_workload: dict[str, Any],
) -> None:
    env = _complete_env()
    env[missing_field] = None
    with pytest.raises(ManifestValidationError, match="INF-5 refuse seal"):
        build_manifest(
            run_id=str(uuid.uuid4()),
            config=fake_config,
            git_state=clean_git_state,
            allow_dirty=False,
            target="npu",
            workload=minimal_workload,
            condition_label="A",
            blinded_label="cond_0123456789ab",
            repo_root=fake_repo,
            topology_override=VERIFIED_TOPOLOGY,
            run_environment=env,
            capture_run_environment_host=False,
        )


@pytest.mark.parametrize("missing_field", list(REQUIRED_RUN_ENVIRONMENT_FIELDS))
def test_emit_refuses_seal_when_field_absent(
    missing_field: str,
    verified_config: ResolvedConfig,
    fake_repo: Path,
    clean_git_state: GitState,
    minimal_workload: dict[str, Any],
    patch_git: Any,
) -> None:
    patch_git(clean_git_state)
    env = _complete_env()
    del env[missing_field]
    with pytest.raises(ManifestValidationError, match="INF-5 refuse seal"):
        emit(
            config=verified_config,
            target="cpu-p",
            workload=minimal_workload,
            condition_label="inf5_missing",
            repo_root=fake_repo,
            run_environment=env,
            capture_run_environment_host=False,
        )


def test_emit_writes_run_environment_on_success(
    verified_config: ResolvedConfig,
    fake_repo: Path,
    clean_git_state: GitState,
    minimal_workload: dict[str, Any],
    patch_git: Any,
) -> None:
    patch_git(clean_git_state)
    handle = emit(
        config=verified_config,
        target="cpu-p",
        workload=minimal_workload,
        condition_label="inf5_ok",
        repo_root=fake_repo,
        run_environment=_complete_env(),
        capture_run_environment_host=False,
    )
    assert handle.manifest["spec_version"] == "1.1"
    env = handle.manifest["run_environment"]
    for key in REQUIRED_RUN_ENVIRONMENT_FIELDS:
        assert key in env
        assert env[key] is not None
    validate_manifest(handle.manifest)


def test_lift_session_fields_from_plan_aliases() -> None:
    from seam.run_environment import lift_session_fields

    lifted = lift_session_fields(
        {
            "available_mb_start": {"available_mb": 7123.5, "available_method": "pdh"},
            "arms": ["gpu_only_f16", "gpu_only_u8"],
            "session_design": "interleaved",
            "prompt_render_sha256": "c" * 64,
        }
    )
    assert lifted["available_mb_start"] == 7123.5
    assert lifted["arm_order"] == ["gpu_only_f16", "gpu_only_u8"]
    assert lifted["session_design"] == "interleaved"
    assert lifted["prompt_render_sha256"] == "c" * 64


def test_emit_lifts_session_fields_from_summary(
    verified_config: ResolvedConfig,
    fake_repo: Path,
    clean_git_state: GitState,
    minimal_workload: dict[str, Any],
    patch_git: Any,
) -> None:
    """Shared seal path stages summary aliases into run_environment (no silent invent)."""
    patch_git(clean_git_state)
    host = {
        k: v
        for k, v in _complete_env().items()
        if k
        not in {
            "prompt_render_sha256",
            "available_mb_start",
            "session_design",
            "arm_order",
        }
    }
    handle = emit(
        config=verified_config,
        target="cpu-p",
        workload=minimal_workload,
        condition_label="inf5_summary_lift",
        repo_root=fake_repo,
        summary={
            "run_environment": host,
            "available_mb_start": 6800.0,
            "session_design": "sequential",
            "arm_order": ["gpu_only"],
            "prompt_render_sha256": "d" * 64,
        },
        capture_run_environment_host=False,
    )
    env = handle.manifest["run_environment"]
    assert env["available_mb_start"] == 6800.0
    assert env["session_design"] == "sequential"
    assert env["arm_order"] == ["gpu_only"]
    assert env["prompt_render_sha256"] == "d" * 64
    validate_manifest(handle.manifest)


def test_run_environment_session_finalize_requires_prompts() -> None:
    from seam.run_environment import RunEnvironmentSession

    session = RunEnvironmentSession.begin(
        session_design="sequential",
        arm_order=["unit"],
        available_mb_start=7000.0,
    )
    with pytest.raises(ManifestValidationError, match="no prompt renders"):
        session.finalize()
    session.add_prompt_render("hello")
    fields = session.finalize()
    assert fields["session_design"] == "sequential"
    assert fields["arm_order"] == ["unit"]
    assert fields["available_mb_start"] == 7000.0
    assert len(fields["prompt_render_sha256"]) == 64
