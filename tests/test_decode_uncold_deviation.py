"""run_decode_match --uncold-uptime-deviation (Task AY): T2S P9/P2 without a reboot."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import boot4_session as b4  # noqa: E402
from tools import run_decode_match as rdm  # noqa: E402

SPEC = ["--model-spec", "configs/models/Qwen3-4B-int4-ov.yaml"]


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    def fake(**kwargs: Any) -> int:
        seen.append(kwargs)
        return 0

    monkeypatch.setattr(rdm, "run_decode", fake)
    return seen


def test_default_passes_no_deviation(calls: list[dict[str, Any]]) -> None:
    assert rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", "p9", "--session-id", "a"]) == 0
    assert calls[0]["uncold_uptime"] is False


def test_deviation_on_evo_t2(calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEAM_PLATFORM_ID", "evo-t2")
    argv = ["--arm", "gpu_only", *SPEC, "--pilot", "p2", "--uncold-uptime-deviation"]
    assert rdm.main(argv) == 0
    assert calls[0]["uncold_uptime"] is True


def test_deviation_refusals(calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEAM_PLATFORM_ID", "evo-t2")
    with pytest.raises(SystemExit, match="needs --pilot"):
        rdm.main(
            [
                "--arm",
                "gpu_only",
                *SPEC,
                "--model-spec",
                "configs/models/Qwen3-4B-int8-ov.yaml",
                "--uncold-uptime-deviation",
            ]
        )
    monkeypatch.setenv("SEAM_PLATFORM_ID", "aipc-c1")
    with pytest.raises(SystemExit, match="evo-t2"):
        rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", "p9", "--uncold-uptime-deviation"])
    monkeypatch.delenv("SEAM_PLATFORM_ID")
    with pytest.raises(SystemExit, match="evo-t2"):
        rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", "p9", "--uncold-uptime-deviation"])
    assert calls == []


def test_require_gates_passes_skip_uptime(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []

    class _Report:
        all_passed = True
        refusal_reasons: list[str] = []

        def to_dict(self) -> dict[str, Any]:
            return {}

    def fake(root: Path, *, skip_uptime: bool = False) -> _Report:
        seen.append(skip_uptime)
        return _Report()

    import seam.measurement_gates as mg

    monkeypatch.setattr(mg, "evaluate_measurement_gates", fake)
    b4.require_gates()
    b4.require_gates(skip_uptime=True)
    assert seen == [False, True]
