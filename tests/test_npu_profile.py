"""NPU-1 / NPU-2 cell rules. The runner must not open the prereg."""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_npu_profile import (  # noqa: E402
    bind_setting,
    canary_marker,
    drive_npu_rung,
    ir_quantization,
    main,
    new_npu_series,
    npu2_load_record,
    over_max_record,
    scheduling_plan,
    setting_estimate_s,
    slo_bisect,
    stamp_canary,
    summarize_rung,
)

RUNNER = ROOT / "tools" / "run_npu_profile.py"
LAUNCHER = ROOT / "tools" / "launch_boot1.ps1"
DIAG = ROOT / "tools" / "npu_maxlen_diag.py"


def test_sources_do_not_name_the_prereg() -> None:
    for path in (RUNNER, LAUNCHER, ROOT / "tools" / "launch_t2s_npu1.ps1", DIAG):
        assert "NPU1_PREREG" not in path.read_text(encoding="utf-8")
    assert "NPU_MAXLEN_DIAG_RULE" not in DIAG.read_text(encoding="utf-8")
    assert (ROOT / "derived" / "npu" / "NPU1_PREREG.json").is_file()


def test_npu2_does_not_generate() -> None:
    loaded = npu2_load_record(None)
    failed = npu2_load_record("std::bad_alloc")
    assert loaded["generated"] is False
    assert loaded["timed"] is False
    assert loaded["status"] == "infeasible"
    assert failed["generated"] is False
    assert failed["error_class"] == "memory_wall"


def test_over_max_is_infeasible_and_not_a_timing() -> None:
    row = over_max_record(128)
    assert row["generated"] is False
    assert row["timed"] is False
    assert row["prompt_length"] == 129
    assert row["reason"] == "prompt_longer_than_max_prompt_len"


def test_bisection_does_not_pass_the_high_rung(tmp_path: Path) -> None:
    del tmp_path
    seen: list[int] = []

    def probe(n_tokens: int) -> dict[str, object]:
        seen.append(n_tokens)
        return {"n_tokens": n_tokens, "slo_pass": n_tokens <= 256}

    rows = slo_bisect(64, 512, 64, probe)
    assert seen[0] == 64
    assert max(seen) == 512
    assert all(int(row["n_tokens"]) <= 512 for row in rows)
    assert 513 not in seen


def test_runner_does_not_open_the_prereg(monkeypatch, tmp_path: Path) -> None:
    real_open = builtins.open

    def guarded(file, *args, **kwargs):
        text = str(file).replace("\\", "/")
        name = text.rsplit("/", 1)[-1].upper()
        if "/derived/" in text.lower() and any(
            token in name for token in ("PREREG", "PREDICTIONS", "AMEND", "RULE")
        ):
            raise AssertionError(f"runner opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    # pathlib.Path.open / read_text go through io.open.
    monkeypatch.setattr(io, "open", guarded)
    with contextlib.suppress(SystemExit):
        main(["--help"])
    assert main(["--cell", "npu1-setting", "--smoke", "--out", str(tmp_path)]) == 0

    from tools import npu_maxlen_diag

    with contextlib.suppress(SystemExit):
        npu_maxlen_diag.main(["--help"])
    assert npu_maxlen_diag.main(["--smoke", "--out", str(tmp_path / "diag")]) == 0
    npu_maxlen_diag.watchdog_state(str(tmp_path / "watchdog.log"))


def test_binding_is_toolchain_latency_or_load_fail() -> None:
    cap = bind_setting(
        load_ok=True,
        cap=1024,
        rungs=[
            {
                "n_tokens": 1024,
                "slo_pass": True,
                "prefill_s": [1.3, 1.3, 1.3],
                "decode_tok_s": [10.0, 12.0, 11.0],
            }
        ],
    )
    assert cap["binding"] == "TOOLCHAIN_CAP"
    assert cap["ttft_limit_n"] == 1024
    assert cap["decode_tok_s_at_limit"] == 11.0
    late = bind_setting(
        load_ok=True,
        cap=1024,
        rungs=[
            {"n_tokens": 64, "slo_pass": True, "prefill_s": [1.3], "decode_tok_s": [16.0]},
            {"n_tokens": 1024, "slo_pass": False, "prefill_s": [12.0], "decode_tok_s": [1.0]},
        ],
    )
    assert late["binding"] == "LATENCY"
    assert late["ttft_limit_n"] == 64
    refused = bind_setting(
        load_ok=True,
        cap=1024,
        rungs=[{"n_tokens": 64, "slo_pass": False, "prefill_s": None}],
    )
    assert refused["binding"] == "TOOLCHAIN_CAP"
    assert refused["ttft_limit_n"] is None
    failed = bind_setting(load_ok=False, cap=1024, rungs=[])
    assert failed["binding"] == "LOAD_FAIL"


def test_refused_cap_is_toolchain_when_a_lower_rung_passes() -> None:
    """680b031a shape: the cap was never timed, and the rung under it passed."""
    bound = bind_setting(
        load_ok=True,
        cap=1024,
        rungs=[
            {
                "n_tokens": 960,
                "slo_pass": True,
                "prefill_s": [1.30, 1.30, 1.31],
                "decode_tok_s": [16.5, 18.5, 16.6],
            },
            {
                "n_tokens": 1024,
                "slo_pass": False,
                "prefill_s": [None, None, None],
                "reason": ["prompt_longer_than_max_prompt_len"] * 3,
            },
        ],
    )
    assert bound["binding"] == "TOOLCHAIN_CAP"
    assert bound["ttft_limit_n"] == 960


def test_unarmed_canary_marker_is_unguarded() -> None:
    assert canary_marker(None) == {"armed": False, "UNGUARDED": True}
    assert canary_marker({"armed": False, "smoke_skip": True})["UNGUARDED"] is True
    opened = canary_marker({"canary_gate": {"armed": False}})
    assert opened == {"armed": False, "UNGUARDED": True}
    assert canary_marker({"canary_gate": {"armed": True}}) == {"armed": True, "UNGUARDED": False}


def test_rung_summary_keeps_prefill_and_realized_tokens() -> None:
    row = summarize_rung(
        960,
        [
            {
                "prefill_s": 1.30,
                "decode_tok_s": 16.5,
                "prompt_length": 960,
                "exact_match_vs_gpu": False,
                "timed": True,
                "reason": None,
            }
        ],
    )
    assert row["prefill_s"] == [1.30]
    assert row["prompt_tokens"] == [960]
    refused = summarize_rung(
        1024,
        [
            {
                "prefill_s": None,
                "prompt_length": 1024 + 8,
                "timed": False,
                "reason": "prompt_longer_than_max_prompt_len",
                "exact_match_vs_gpu": None,
                "decode_tok_s": None,
            }
        ],
    )
    assert refused["prefill_s"] == [None]
    assert refused["prompt_tokens"] == [1032]
    assert refused["slo_pass"] is False


def test_stub_session_arms_after_c_plus_one_canaries(tmp_path: Path, monkeypatch) -> None:
    """The GPU guard arms once C+1 canaries have run. The NPU series does not gate."""
    from tools.ttft_slo_canary import CALIBRATION_C, TtftSloCanaryGuard

    guard = TtftSloCanaryGuard(
        root=ROOT,
        model_spec=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
        work_dir=tmp_path / "canaries",
        plan_path=tmp_path / "plan.json",
        planned_probe_count=CALIBRATION_C + 1,
    )

    def stub_cell() -> dict[str, object]:
        return {
            "is_canary": True,
            "canary_index": len(guard.canaries),
            "classification": "OK",
            "turn1_prefill_s": 1.0,
            "turn2_prefill_s": 0.5,
            "execute_ok": True,
        }

    monkeypatch.setattr(guard, "_run_cell", stub_cell)
    guard.opening()
    series = new_npu_series()
    probes_log: list[dict[str, object]] = []

    def one_repeat(n_tokens: int) -> dict[str, object]:
        return {
            "n_tokens": n_tokens,
            "slo_pass": True,
            "prefill_s": 1.0,
            "decode_tok_s": 16.0,
            "prompt_length": n_tokens,
            "timed": True,
            "exact_match_vs_gpu": False,
            "reason": None,
        }

    def on_interval(after_probe_count: int) -> None:
        series["n_derivation"] = guard.n_derivation
        series["samples"].append(
            {
                "label": "npu_canary_series",
                "gates": False,
                "n_tokens": 400,
                "after_probe_count": after_probe_count,
            }
        )

    drive_npu_rung(
        64,
        repeats=CALIBRATION_C,
        one_repeat=one_repeat,
        guard=guard,
        probes_log=probes_log,
        on_interval=on_interval,
    )
    assert len(guard.canaries) == CALIBRATION_C + 1
    assert guard.gate["armed"] is True
    assert guard.canaries[CALIBRATION_C]["gate_armed"] is True
    plan: dict[str, object] = {}
    summary: dict[str, object] = {"status": "complete"}
    marker = stamp_canary(plan, summary, guard, series)
    assert marker == {"armed": True, "UNGUARDED": False}
    assert summary["armed"] is True
    assert summary["UNGUARDED"] is False
    assert series["label"] == "npu_canary_series"
    assert series["gates"] is False
    assert series["n_derivation"]["n"] == 1
    assert series["samples"]
    assert all(row["gates"] is False for row in series["samples"])


def test_npu1_refusal_hint_names_the_t2s_launcher() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    start = text.index("$script:RehearsalMac")
    arm = text[text.index('"npu-1"', start) : text.index("default", start)]
    assert "launch_t2s_npu1.ps1" in arm
    assert "launch_boot4.ps1" not in arm
    assert ".\\tools\\launch_t2s_npu1.ps1" in arm


def _run_npu_cells(*, rehearsal: bool) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SEAM_BOOT_CELL_STUB"] = "1"
    if rehearsal:
        env["SEAM_BOOT_SMOKE_STUB"] = "1"
    flags = "-NoRebootDeviation -Npu2 -MaxPromptLen 1024"
    if rehearsal:
        flags = "-Rehearsal " + flags
    command = (
        f"Set-StrictMode -Version Latest; & '{LAUNCHER}' -Profile npu-1 {flags}; exit $LASTEXITCODE"
    )
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_npu_real_cell_stub_reads_exit() -> None:
    """The real invoker, not the rehearsal smoke branch, must survive worker stdout."""
    proc = _run_npu_cells(rehearsal=False)
    combined = proc.stdout + proc.stderr
    assert "cannot be found on this object" not in combined, combined
    assert proc.returncode == 0, combined
    assert "cell_invoke kind=npu" in combined
    assert "SMOKE_OK npu2-load" in combined
    assert "SMOKE_OK npu1-setting" in combined
    assert "=== machine-lock / alive-worker check ===" in combined
    summary = (
        ROOT / "derived" / "c2_ttft" / "_launches" / "_stub" / "npu-1" / "T2S_NPU1_SUMMARY.json"
    )
    doc = json.loads(summary.read_text(encoding="utf-8"))
    assert doc["state"] == "complete"
    assert len(doc["cells"]) == 2
    assert doc["cells"][0]["status"] == "smoke"


def test_npu_rehearsal_uses_the_cell_invoker() -> None:
    proc = _run_npu_cells(rehearsal=True)
    combined = proc.stdout + proc.stderr
    assert "cannot be found on this object" not in combined, combined
    assert proc.returncode == 0, combined
    assert "cell_invoke kind=npu" in combined
    assert "SMOKE_OK npu2-load" in combined
    assert "REHEARSAL_COMPLETE" in combined
    assert "rehearsal_cell " not in combined
    summary = (
        ROOT
        / "derived"
        / "c2_ttft"
        / "_launches"
        / "_rehearsal"
        / "npu-1"
        / "T2S_NPU1_SUMMARY.json"
    )
    doc = json.loads(summary.read_text(encoding="utf-8"))
    assert doc["state"] == "complete"
    assert doc["cells"]
    assert doc["cells"][0]["status"] == "rehearsal_invoke"


def test_ir_is_groupwise_int4_sym() -> None:
    import yaml

    doc = yaml.safe_load(
        (ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml").read_text(encoding="utf-8")
    )
    row = ir_quantization(doc)
    assert row["mode"] == "INT4_SYM"
    assert row["group_size"] == 128
    assert row["channel_wise"] is False


def test_fixed_ladder_does_not_fit_one_session() -> None:
    plan = scheduling_plan()
    assert plan["fits_one_session"] is False
    assert plan["split"] == "one detached session per MAX_PROMPT_LEN"
    assert [row["max_prompt_len"] for row in plan["settings"]] == [1024, 2048, 4096, 8192]
    assert all(int(row["estimate_s"]) <= 7200 for row in plan["settings"])
    assert setting_estimate_s(int(plan["tail_start"])) > 7200


def test_launcher_uses_the_prompt_len_axis() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "npu1-setting" in text
    assert "MaxPromptLen" in text
    assert "npu1-feasibility" not in text
    assert "npu1-bisect" not in text
