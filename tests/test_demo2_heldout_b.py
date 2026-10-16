"""DEMO2_HELDOUT_60_B long_context half: selection, disjointness, reservation guard."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import demo2_heldout_b as hb  # noqa: E402
from tools import run_h1_hybrid as rh  # noqa: E402

PIN = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60_B_LONG30.json"
META = PIN.with_name(PIN.stem + ".meta.json")


def _ids(cat: str) -> list[str]:
    return [f"{cat}_{i}" for i in range(200)]


def test_selection_reproduces_meta() -> None:
    sel = hb.select(_ids("multi_turn_base"), _ids("multi_turn_long_context"))
    meta = json.loads(META.read_text(encoding="ascii"))
    assert sel["selected_long"] == meta["selected"]
    assert sel["base_eligible"] == 0
    assert sel["long_eligible"] == 133
    assert sel["long_jump_eligible"] == 0


def test_disjoint_from_every_other_pin() -> None:
    meta = json.loads(META.read_text(encoding="ascii"))
    chosen = set(meta["selected"])
    for name, ids in hb.excluded().items():
        assert not chosen & set(ids), name
    entries = json.loads(PIN.read_text(encoding="ascii"))
    assert [e["id"] for e in entries] == meta["selected"]


def test_registered_and_reserved() -> None:
    digest = hashlib.sha256(PIN.read_bytes()).hexdigest()
    assert digest == rh.DEMO2_HELDOUT_60_B_LONG30_SHA256
    pin = rh.ENTRY_PINS[digest]
    assert pin["reserved_for"]
    with pytest.raises(SystemExit, match="reserved"):
        rh.assert_entry_set_pinned(PIN)
    assert rh.assert_entry_set_pinned(PIN, allow_reserved=True)["n"] == 30


def test_confirmation_flag_default_off() -> None:
    args = rh.build_argparser().parse_args(["--policy", "hybrid_full"])
    assert args.confirmation_run is False
