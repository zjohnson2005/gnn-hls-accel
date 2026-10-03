"""PARITY-REMEASURE is a document. The ceiling runner must not read it."""

from __future__ import annotations

import builtins
import contextlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREREG_NAMES = (
    "PARITY_REMEASURE_PREREG.json",
    "PARITY_REMEASURE_AMEND_1.json",
)
RUNNER = ROOT / "tools" / "run_c1_ceiling.py"


def test_prereg_exists_and_runner_source_does_not_name_it() -> None:
    for name in PREREG_NAMES:
        assert (ROOT / "derived" / "c2_ttft" / name).is_file()
    text = RUNNER.read_text(encoding="utf-8")
    for name in PREREG_NAMES:
        assert name not in text


def _forbidden_derived_doc(file: object) -> bool:
    """True for derived/** files whose names carry PREDICTIONS, PREREG, or AMEND."""
    text = str(file).replace("\\", "/")
    lowered = text.lower()
    if "/derived/" not in lowered and not lowered.startswith("derived/"):
        return False
    name = text.rsplit("/", 1)[-1].upper()
    return any(token in name for token in ("PREDICTIONS", "PREREG", "AMEND"))


def test_ceiling_runner_does_not_open_prereg(monkeypatch) -> None:
    opened: list[str] = []
    real_open = builtins.open

    def guard(file: object, *args: Any, **kwargs: Any) -> Any:
        if _forbidden_derived_doc(file):
            opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guard)
    from tools.run_c1_ceiling import main
    from tools.ttft_slo_predictions import resolve_ttft_slo_plan_predictions

    with contextlib.suppress(SystemExit):
        main(["--help"])
    resolve_ttft_slo_plan_predictions(
        model_spec=ROOT / "configs/models/Qwen3-8B-int4-ov.yaml",
        arm_ids=["gpu_only_u8"],
        slo_s=10.0,
        repeats=3,
        default_c2_predictions=lambda *, slo_s, repeats: {"slo_s": slo_s, "repeats": repeats},
        repo_root=ROOT,
        predictions_path=ROOT / "derived/cap3/CAP3_PREDICTIONS.json",
    )
    assert opened == []
