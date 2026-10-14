"""DEMO2_HELDOUT_60: disjoint from DEMO-1, reproducible, pinned in the runner."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_heldout  # noqa: E402
from tools.run_h1_hybrid import ENTRY_PINS, assert_entry_set_pinned  # noqa: E402

PIN = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60.json"
META = PIN.with_name("DEMO2_HELDOUT_60.meta.json")


def _atlas_ids(name: str) -> list[str]:
    doc = json.loads((ROOT / "analysis" / "demo1" / "atlas" / name).read_text(encoding="utf-8"))
    return [r["entry_id"] for r in doc["entries"]]


def test_pin_file_matches_meta_and_runner() -> None:
    meta = json.loads(META.read_text(encoding="utf-8"))
    digest = hashlib.sha256(PIN.read_bytes()).hexdigest()
    assert digest == meta["entries_sha256"]
    assert ENTRY_PINS[digest]["name"] == "DEMO2_HELDOUT_60"
    pin = assert_entry_set_pinned(PIN)
    assert pin["n"] == 60
    ids = [e["id"] for e in json.loads(PIN.read_text(encoding="utf-8"))]
    assert ids == meta["selected"]
    assert sum(i.startswith("multi_turn_base_") for i in ids) == 30
    assert sum(i.startswith("multi_turn_long_context_") for i in ids) == 30


def test_disjoint_from_every_demo1_pin() -> None:
    ids = set(json.loads(META.read_text(encoding="utf-8"))["selected"])
    for name in demo2_heldout.EXCLUDE_PINS:
        demo1 = json.loads(
            (ROOT / "derived" / "h1_hybrid" / "demo1" / f"{name}.meta.json").read_text(
                encoding="utf-8"
            )
        )["selected"]
        assert not ids & set(demo1), name


def test_selection_reproduces_from_file_order_ids() -> None:
    meta = json.loads(META.read_text(encoding="utf-8"))
    sel = demo2_heldout.select(
        _atlas_ids("multi_turn_base_FULL.json"),
        _atlas_ids("multi_turn_long_context_FULL.json"),
    )
    assert sel["selected_base"] + sel["selected_long"] == meta["selected"]
    assert meta["seed"] == demo2_heldout.SEED == 20261014
    assert meta["long_jump_selected"] == 3 and meta["long_jump_eligible"] == 3
    assert meta["selection_rule_entries_used"] == []
