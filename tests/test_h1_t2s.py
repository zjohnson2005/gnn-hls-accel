"""T2S support for the H1 runner and launcher (DEMO-1 groundwork).

The runner records the local model and tier from the model spec (an 8B run
must not be labeled 4B) and the platform the gates resolve to. The launcher
has a -T2S path: SEAM_PLATFORM_ID=evo-t2, the watchdog launch-check, a venv
import check and the uptime deviation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_h1_hybrid import (  # noqa: E402
    ARM_CONFIG,
    KV_MATCH_SEAL_4B,
    StubCloudBackend,
    StubLocalBackend,
    arm_config_for,
    local_model_identity,
    run_interleaved_session,
    run_session,
)

SPEC_4B = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
SPEC_8B = ROOT / "configs" / "models" / "Qwen3-8B-int4-ov.yaml"
LAUNCH_H1 = ROOT / "tools" / "launch_h1.ps1"
GATES_PS1 = ROOT / "tools" / "_run_measurement_gates.ps1"

ENTRY = {"id": "e0", "question": [[]], "n_user_turns": 1}
SCRIPT = {
    "e0": [
        {
            "n_ctx": 100,
            "ttft_s": 0.5,
            "decode_tok_s": 30.0,
            "emitted_parseable_tool_call": True,
            "turn_wall_s": 0.05,
            "t_generate": 0.03,
            "t_tokenize": 0.005,
            "t_template_build": 0.005,
            "t_tool_exec": 0.005,
        }
    ]
}


def _local(spec: Path | None) -> StubLocalBackend:
    local = StubLocalBackend(script=SCRIPT)
    if spec is not None:
        local.model_spec = spec  # type: ignore[attr-defined]
    return local


def test_identity_reads_the_spec_name() -> None:
    assert local_model_identity(_local(SPEC_4B)) == {"model": "Qwen3-4B-int4-ov", "tier": "4B"}
    assert local_model_identity(_local(SPEC_8B)) == {"model": "Qwen3-8B-int4-ov", "tier": "8B"}


def test_identity_relative_spec_resolves_from_root() -> None:
    rel = Path("configs") / "models" / "Qwen3-8B-int4-ov.yaml"
    assert local_model_identity(_local(rel))["tier"] == "8B"


def test_identity_defaults_without_a_spec_file() -> None:
    assert local_model_identity(_local(None)) == {"model": "Qwen3-4B-int4-ov", "tier": "4B"}
    assert local_model_identity(_local(Path("<stubbed_generate>")))["tier"] == "4B"


def test_identity_refuses_a_name_without_tier(tmp_path: Path) -> None:
    spec = tmp_path / "odd.yaml"
    spec.write_text("name: some-model\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no tier"):
        local_model_identity(_local(spec))


def test_arm_config_for_overrides_local_arms_only() -> None:
    before = json.dumps(ARM_CONFIG, sort_keys=True)
    arm = arm_config_for("slo_escalate", _local(SPEC_8B))
    assert arm["model"] == "Qwen3-8B-int4-ov"
    assert arm["tier"] == "8B"
    assert arm["kv"] == "u8" and arm["residency"] == "RESIDENT"
    assert arm_config_for("cloud_only", _local(SPEC_8B)) == ARM_CONFIG["cloud_only"]
    assert json.dumps(ARM_CONFIG, sort_keys=True) == before


def test_interleaved_plan_records_8b_and_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEAM_PLATFORM_ID", "evo-t2")
    out = tmp_path / "il"
    run_interleaved_session(
        entries=[ENTRY],
        out_dir=out,
        local=_local(SPEC_8B),
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        policies=("local_only",),
        policy_caps_usd={"local_only": 1.0},
        session_max_usd=1.0,
        run_id="il-8b",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["tier"] == "8B"
    assert plan["model"] == "Qwen3-8B-int4-ov"
    assert plan["kv_match_seal"] is None
    assert plan["platform_id"] == "evo-t2"
    ledger = json.loads(
        (out / "policies" / "local_only" / "turn_ledger.json").read_text(encoding="utf-8")
    )
    assert {t["model"] for t in ledger["entries"][0]["turns"]} == {"Qwen3-8B-int4-ov"}


def test_interleaved_plan_keeps_4b_labels(tmp_path: Path) -> None:
    out = tmp_path / "il4"
    run_interleaved_session(
        entries=[ENTRY],
        out_dir=out,
        local=_local(SPEC_4B),
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        policies=("local_only",),
        policy_caps_usd={"local_only": 1.0},
        session_max_usd=1.0,
        run_id="il-4b",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["tier"] == "4B"
    assert plan["kv_match_seal"] == KV_MATCH_SEAL_4B


def test_single_policy_plan_records_8b_arm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEAM_PLATFORM_ID", "evo-t2")
    out = tmp_path / "single"
    run_session(
        policy="local_only",
        entries=[ENTRY],
        out_dir=out,
        local=_local(SPEC_8B),
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        max_usd=1.0,
        run_id="single-8b",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["arm_config"]["tier"] == "8B"
    assert plan["arm_config"]["model"] == "Qwen3-8B-int4-ov"
    assert plan["platform_id"] == "evo-t2"


def test_launch_h1_t2s_path() -> None:
    text = LAUNCH_H1.read_text(encoding="ascii")
    assert "[switch]$T2S" in text
    assert '$env:SEAM_PLATFORM_ID = "evo-t2"' in text
    assert "t2s_queue_watchdog.py" in text and "launch-check" in text
    assert "import anthropic, transformers, bfcl_eval" in text
    assert "-SkipUptime:$T2S" in text
    # The detached worker gets the platform on its command line.
    assert "'&& set SEAM_PLATFORM_ID=evo-t2'" in text
    assert text.count("$resolvedCmd = $envPrefix +") == 2
    # A T2S host without -T2S is refused.
    assert '$T2sMarker = "C:\\apu\\ovn"' in text
    assert "pass -T2S" in text


def test_gate_helper_skip_uptime_is_opt_in() -> None:
    text = GATES_PS1.read_text(encoding="ascii")
    assert "[switch]$SkipUptime" in text
    assert '$pyArgs += "--skip-uptime"' in text


def test_launch_h1_runs_the_tier1_gate_on_both_hosts() -> None:
    """f713edc: the tier-1 process gate is in the full gate set launch_h1 runs."""
    launch = LAUNCH_H1.read_text(encoding="ascii")
    assert '. (Join-Path $PSScriptRoot "_run_measurement_gates.ps1")' in launch
    assert "Invoke-SeamMeasurementGates -RepoRoot $root -PythonExe $pythonForGates" in launch
    helper = GATES_PS1.read_text(encoding="ascii")
    assert '"-m", "seam.measurement_gates",' in helper
    assert "--tier1-only" not in helper and "skip-host-probes" not in helper
    gates = (ROOT / "seam" / "measurement_gates.py").read_text(encoding="utf-8")
    main = gates[gates.index("def _main(") :]
    call = main[main.index("report = evaluate_measurement_gates(") :]
    call = call[: call.index(")") + 1]
    assert "skip_host_probes" not in call
    assert "if process_names is not None or not skip_host_probes:" in gates
    assert "gates.append(classify_tier1_processes(names))" in gates
