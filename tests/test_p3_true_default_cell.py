"""Task AX: the added P3 cell (true-default resident limit) loads with no scheduler override."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.boot4_session as b4  # noqa: E402
import tools.run_resident_limit as rrl  # noqa: E402


def _main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_run(**kw: Any) -> int:
        seen.update(kw)
        seen["scheduler"] = b4.SCHEDULER_OVERRIDE
        seen["high"] = b4._resident_high()
        return 0

    monkeypatch.setattr(rrl, "run_resident_limit", fake_run)
    try:
        assert rrl.main(argv) == 0
    finally:
        b4.set_pilot_overrides()
    return seen


def test_true_default_cell_has_no_scheduler_override(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _main(
        monkeypatch,
        [
            "--arm",
            "gpu_only",
            "--model-spec",
            "configs/models/Qwen3-4B-int4-ov.yaml",
            "--high",
            "50000",
        ],
    )
    assert seen["arm"] == "gpu_only"
    assert seen["scheduler"] is None  # plain LLMPipeline(model, "GPU"): the true default
    assert seen["high"] == 50_000


def test_registered_cell_keeps_its_override(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _main(
        monkeypatch,
        [
            "--arm",
            "gpu_only_u4",
            "--model-spec",
            "configs/models/Qwen3-4B-int4-ov.yaml",
            "--high",
            "45000",
            "--sched-max-batched-tokens",
            "4096",
        ],
    )
    assert seen["scheduler"] == {"enable_prefix_caching": True, "max_num_batched_tokens": 4096}
    assert seen["high"] == 45_000


def test_gpu_only_arm_passes_no_kv_property() -> None:
    import yaml

    cfg = yaml.safe_load((ROOT / "configs" / "delta_n.yaml").read_text(encoding="utf-8"))
    arm = next(a for a in cfg["arms"] if a["id"] == "gpu_only")
    assert not arm.get("properties")
