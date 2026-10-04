"""NPU-1 / NPU-2 cell rules. The runner must not open the prereg."""

from __future__ import annotations

import builtins
import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_npu_profile import (  # noqa: E402
    main,
    npu2_load_record,
    over_max_record,
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
    assert main(["--cell", "npu1-feasibility", "--smoke", "--out", str(tmp_path)]) == 0
