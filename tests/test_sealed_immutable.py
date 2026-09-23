"""Sealed-tree hook: a tracked .sealed protects the directory and its descendants."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "tools" / "hooks" / "check_sealed_immutable.py"

_spec = importlib.util.spec_from_file_location("check_sealed_immutable", HOOK_PATH)
assert _spec is not None and _spec.loader is not None
hook = importlib.util.module_from_spec(_spec)
sys.modules["check_sealed_immutable"] = hook
_spec.loader.exec_module(hook)


def test_raw_and_sealed_star_still_protected() -> None:
    assert hook._is_sealed_path("raw/abc/summary.json")
    assert hook._is_sealed_path("derived/cap4/sealed_abc/summary.json")


def test_tracked_sealed_marker_protects_descendants(monkeypatch) -> None:
    marker = "derived/h1_hybrid/interleaved_d482c621/.sealed"

    def in_head(rel: str) -> bool:
        return rel == marker

    monkeypatch.setattr(hook, "_in_head", in_head)
    assert hook._is_sealed_path("derived/h1_hybrid/interleaved_d482c621/summary.json")
    assert hook._is_sealed_path(
        "derived/h1_hybrid/interleaved_d482c621/policies/slo/turn_ledger.json"
    )
    assert not hook._is_sealed_path("derived/h1_hybrid/interleaved_other/summary.json")


def test_scan_refuses_staged_edit_under_tracked_seal(monkeypatch) -> None:
    edited = "derived/h1_hybrid/interleaved_d482c621/summary.json"
    marker = "derived/h1_hybrid/interleaved_d482c621/.sealed"

    def in_head(rel: str) -> bool:
        return rel in {marker, edited}

    monkeypatch.setattr(hook, "_in_head", in_head)
    monkeypatch.setattr(hook, "_staged_paths", lambda: [edited])
    assert hook.scan([edited]) == 1


def test_scan_allows_a_new_tree_whose_seal_is_not_in_head(monkeypatch) -> None:
    added = "derived/h1_hybrid/interleaved_new/summary.json"

    monkeypatch.setattr(hook, "_in_head", lambda _rel: False)
    monkeypatch.setattr(hook, "_staged_paths", lambda: [added])
    assert hook.scan([added]) == 0
