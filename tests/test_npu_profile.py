"""NPU-1 / NPU-2 cell rules. The runner must not open the prereg."""

from __future__ import annotations

import builtins
import contextlib
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
    ir_quantization,
    main,
    npu2_load_record,
    over_max_record,
    scheduling_plan,
    setting_estimate_s,
    slo_bisect,
)

RUNNER = ROOT / "tools" / "run_npu_profile.py"
LAUNCHER = ROOT / "tools" / "launch_boot1.ps1"


def test_sources_do_not_name_the_prereg() -> None:
    for path in (RUNNER, LAUNCHER, ROOT / "tools" / "launch_t2s_npu1.ps1"):
        assert "NPU1_PREREG" not in path.read_text(encoding="utf-8")
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
            token in name for token in ("PREREG", "PREDICTIONS", "AMEND")
        ):
            raise AssertionError(f"runner opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    with contextlib.suppress(SystemExit):
        main(["--help"])
    assert main(["--cell", "npu1-setting", "--smoke", "--out", str(tmp_path)]) == 0


def test_binding_is_toolchain_latency_or_load_fail() -> None:
    cap = bind_setting(
        load_ok=True,
        cap=1024,
        rungs=[{"n_tokens": 1024, "slo_pass": True, "decode_tok_s": [10.0, 12.0, 11.0]}],
    )
    assert cap["binding"] == "TOOLCHAIN_CAP"
    assert cap["ttft_limit_n"] == 1024
    assert cap["decode_tok_s_at_limit"] == 11.0
    late = bind_setting(
        load_ok=True,
        cap=1024,
        rungs=[
            {"n_tokens": 64, "slo_pass": True, "decode_tok_s": [16.0]},
            {"n_tokens": 1024, "slo_pass": False, "decode_tok_s": [1.0]},
        ],
    )
    assert late["binding"] == "LATENCY"
    assert late["ttft_limit_n"] == 64
    below = bind_setting(load_ok=True, cap=1024, rungs=[{"n_tokens": 64, "slo_pass": False}])
    assert below["binding"] == "LATENCY"
    assert below["ttft_limit_n"] is None
    failed = bind_setting(load_ok=False, cap=1024, rungs=[])
    assert failed["binding"] == "LOAD_FAIL"


def _run_npu_cells(*, rehearsal: bool) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SEAM_BOOT_CELL_STUB"] = "1"
    if rehearsal:
        env["SEAM_BOOT_SMOKE_STUB"] = "1"
    flags = "-NoRebootDeviation -Npu2 -MaxPromptLen 1024"
    if rehearsal:
        flags = "-Rehearsal " + flags
    command = (
        "Set-StrictMode -Version Latest; "
        f"& '{LAUNCHER}' -Profile npu-1 {flags}; "
        "exit $LASTEXITCODE"
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
