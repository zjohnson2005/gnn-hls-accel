"""CAP-01 BFCL multi_turn_checker wrapper (adopted without modifying upstream)."""

from __future__ import annotations

import uuid
from typing import Any


def _ensure_bfcl_on_path() -> None:
    """Locate unpacked bfcl_eval whether loaded from package or corpus asset."""
    import sys
    from pathlib import Path

    here = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in here.parents:
        candidates.append(
            parent / "apu_characterization/out/cap01/live_sources/bfcl-wheel/unpacked"
        )
        candidates.append(parent / "out/cap01/live_sources/bfcl-wheel/unpacked")
    for unpacked in candidates:
        if unpacked.is_dir() and (unpacked / "bfcl_eval").is_dir():
            path = str(unpacked)
            if path not in sys.path:
                sys.path.insert(0, path)
            return
    raise ModuleNotFoundError(
        "bfcl_eval not found; expected out/cap01/live_sources/bfcl-wheel/unpacked"
    )


def gold_decoded_from_ground_truth(
    ground_truth: list[list[str]],
) -> list[list[list[str]]]:
    """Wrap per-turn GT execute strings as a single decoded step per turn.

    ``multi_turn_checker`` expects ``list[turn][step][execute_str]``. Ground
    truth is ``list[turn][execute_str]``; gold selftest uses one step/turn.
    """
    out: list[list[list[str]]] = []
    for turn in ground_truth:
        if turn:
            out.append([list(turn)])
        else:
            out.append([])
    return out


def check(
    *,
    test_entry: dict[str, Any],
    ground_truth: list[list[str]],
    model_result_decoded: list[list[list[str]]] | None = None,
    test_category: str = "multi_turn_base",
    model_name: str | None = None,
) -> dict[str, Any]:
    """Run official ``multi_turn_checker`` under CAP-01 import shims.

    If ``model_result_decoded`` is omitted, ground truth is used (gold selftest).
    Returns the upstream result dict (includes ``valid``).
    """
    # Same shim path as ast_checker: stub java/js parsers + MODEL_CONFIG_MAPPING
    # before any bfcl_eval import that might pull those graphs.
    from apu_characterization.cap01.bfcl_shims import install_bfcl_runtime_shims

    _ensure_bfcl_on_path()
    install_bfcl_runtime_shims()
    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (
        multi_turn_checker,
    )

    decoded = (
        model_result_decoded
        if model_result_decoded is not None
        else gold_decoded_from_ground_truth(ground_truth)
    )
    # Unique model_name avoids execute_multi_turn_func_call globals() reuse
    # across successive checks of the same test_entry_id in one process.
    name = model_name or f"cap01_mt_{uuid.uuid4().hex[:12]}"
    return multi_turn_checker(
        decoded,
        ground_truth,
        test_entry,
        test_category,
        name,
    )
