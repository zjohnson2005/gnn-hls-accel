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


FULL = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60_B.json"
FULL_META = FULL.with_name(FULL.stem + ".meta.json")


def test_r1_base_selection_reproduces_meta() -> None:
    meta = json.loads(FULL_META.read_text(encoding="ascii"))
    r1 = hb.select_base_r1(_ids("multi_turn_base"))
    assert r1["selected_base"] == meta["selected_base"]
    assert r1["base_r1_eligible"] == meta["base_r1_eligible"] == 140
    assert meta["selected"] == meta["selected_base"] + meta["selected_long"]
    assert meta["search_barred_outcomes"]["ids"] == meta["selected_base"]


def test_full_pin_disjoint_and_in_w3() -> None:
    meta = json.loads(FULL_META.read_text(encoding="ascii"))
    ex = hb.excluded()
    w3 = set(ex.pop("W3_multi_turn_base_200"))
    assert set(meta["selected_base"]) <= w3
    for name, ids in ex.items():
        assert not set(meta["selected"]) & set(ids), name
    assert len(set(meta["selected"])) == 60


def test_full_pin_long_half_is_the_registered_long30() -> None:
    entries = json.loads(FULL.read_text(encoding="ascii"))
    long30 = json.loads(PIN.read_text(encoding="ascii"))
    assert [e["id"] for e in entries] == json.loads(FULL_META.read_text(encoding="ascii"))[
        "selected"
    ]
    assert entries[30:] == long30


def test_full_pin_registered_and_reserved() -> None:
    digest = hashlib.sha256(FULL.read_bytes()).hexdigest()
    assert digest == rh.DEMO2_HELDOUT_60_B_SHA256
    assert digest == json.loads(FULL_META.read_text(encoding="ascii"))["entries_sha256"]
    assert rh.ENTRY_PINS[digest]["reserved_for"]
    with pytest.raises(SystemExit, match="reserved"):
        rh.assert_entry_set_pinned(FULL)
    assert rh.assert_entry_set_pinned(FULL, allow_reserved=True)["n"] == 60
