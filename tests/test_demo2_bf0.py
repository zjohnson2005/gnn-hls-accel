"""Task BF0: cache-aware price + CostGuard, replay fixes (PF 2-13), rebuild-on-error, held-out gate."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_iso_quality_replay as rp  # noqa: E402
from tools.h1_cloud_accounting import (  # noqa: E402
    CloudPriceRefused,
    load_price_table,
    price_request,
)
from tools.run_h1_hybrid import (  # noqa: E402
    AnthropicCloudBackend,
    CostCapExceeded,
    CostGuard,
    OpenVinoLocalBackend,
    attach_be_modes,
    build_argparser,
)

DAY = date(2026, 10, 22)


def _req(inp: int, out: int, cw: int | None, cr: int | None, ok: bool = True) -> dict[str, Any]:
    return {
        "model": "claude-sonnet-5",
        "ok": ok,
        "turn": 0,
        "request_index_within_turn": 0,
        "input_tokens": inp,
        "output_tokens": out,
        "cache_creation_input_tokens": cw,
        "cache_read_input_tokens": cr,
        "prompt_tokens": inp,
        "completion_tokens": out,
        "usd": (inp * 3 + out * 15) / 1e6,  # the old, cache-blind figure
    }


# ------------------------------------------------------------------ X2
def test_price_formula_and_refusals() -> None:
    t = load_price_table()
    usd = price_request(_req(1000, 100, 2000, 10000), table=t, when=DAY)
    assert usd == pytest.approx((1000 * 3 + 2000 * 3.75 + 10000 * 0.30 + 100 * 15) / 1e6)
    with pytest.raises(CloudPriceRefused, match="never priced as zero"):
        price_request(_req(1000, 100, None, 0), table=t, when=DAY)
    assert price_request(_req(0, 0, None, None, ok=False), table=t, when=DAY) == 0.0


def test_cloud_backend_charges_cache_aware_and_costguard_caps() -> None:
    cloud = AnthropicCloudBackend(client=None, cloud_model="claude-sonnet-5")
    calls = [dict(_req(1000, 100, 2000, 10000), user_turn=0)]
    cloud._entry_cache["e"] = {"calls": calls, "model_result_decoded": [[["f()"]]]}
    bt = cloud.run_turn({"id": "e"}, 0, model="claude-sonnet-5")
    want = (1000 * 3 + 2000 * 3.75 + 10000 * 0.30 + 100 * 15) / 1e6
    assert bt.cloud_usd == pytest.approx(want)
    assert bt.cloud_usd > calls[0]["usd"] * 3  # the old figure undercounted the cache tokens
    guard = CostGuard(max_usd=0.01)
    with pytest.raises(CostCapExceeded):
        guard.charge(bt.cloud_usd)
    cloud._entry_cache["m"] = {
        "calls": [dict(_req(1000, 100, None, 5), user_turn=0)],
        "model_result_decoded": [[["f()"]]],
    }
    with pytest.raises(CloudPriceRefused):
        cloud.run_turn({"id": "m"}, 0, model="claude-sonnet-5")


# ------------------------------------------------------------------ replay loading
def _write(d: Path, rel: str, doc: Any) -> None:
    p = d / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _local_turn(t: int, *, trig: str | None = None) -> dict[str, Any]:
    return {
        "turn": t,
        "placement": "local",
        "decoded_steps": [[f"l{t}()"]],
        "passive_triggers": {"mechanical": trig, "quality": None},
    }


def _cloud_dir(d: Path, entries: list[dict[str, Any]]) -> Path:
    _write(d, "turn_ledger.json", {"entries": entries})
    _write(d, "plan.json", {"started_utc": "2026-10-23T01:00:00+00:00"})
    return d


def _cloud_entry(eid: str, n_turns: int, *, cr: int = 0) -> dict[str, Any]:
    turns = [
        {
            "turn": t,
            "decoded_steps": [[f"c{t}()"]],
            "cloud_usd": 0.0,
            "cloud_requests": [_req(100, 10, 0, cr)],
        }
        for t in range(n_turns)
    ]
    return {"entry_id": eid, "hybrid_pass": True, "turns": turns}


def test_load_cloud_reprices_and_cold_delta(tmp_path: Path) -> None:
    d = _cloud_dir(tmp_path / "c", [_cloud_entry("e", 2, cr=1000)])
    c = rp.load_cloud([d], table=load_price_table(), when=rp.price_date([d], None))
    hot = (100 * 3 + 1000 * 0.30 + 10 * 15) / 1e6
    assert c["e"]["usd"] == [pytest.approx(hot)] * 2
    assert c["e"]["cold_delta"][1] == pytest.approx(1000 * (3.75 - 0.30) / 1e6)
    bad = _cloud_entry("x", 1)
    bad["turns"][0]["cloud_requests"][0]["cache_read_input_tokens"] = None
    d2 = _cloud_dir(tmp_path / "c2", [bad])
    with pytest.raises(SystemExit, match="never priced as zero"):
        rp.load_cloud([d2], table=load_price_table(), when=DAY)
    d3 = _cloud_dir(tmp_path / "c3", [_cloud_entry("e", 1), _cloud_entry("e", 1)])
    with pytest.raises(SystemExit, match="duplicate cloud entry"):
        rp.load_cloud([d3], table=load_price_table(), when=DAY)


def test_load_arm_refusals_and_hang_turn(tmp_path: Path) -> None:
    led = "policies/local_only/turn_ledger.json"
    eq = "policies/local_only/entry_quality.json"
    a = tmp_path / "a"
    _write(a, led, {"entries": [{"entry_id": "e", "local_pass": None, "turns": [_local_turn(0)]}]})
    with pytest.raises(SystemExit, match="local_pass None"):
        rp.load_arm([a], derive=False)
    b = tmp_path / "b"
    _write(b, led, {"entries": [{"entry_id": "e", "local_pass": False, "turns": [_local_turn(0)]}]})
    with pytest.raises(SystemExit, match="duplicate entry"):
        rp.load_arm([b, b], derive=False)
    # A hang at turn 2 with no local prefix: escalated at turn 0, counted.
    c = tmp_path / "c"
    _write(c, led, {"entries": []})
    _write(
        c, eq, {"entries": [{"entry_id": "h", "status": "skipped_hang", "hang_ref": {"turn": 2}}]}
    )
    arm = rp.load_arm([c], derive=False)
    assert arm["h"]["trigger_turn"] == 0 and arm["h"]["hang_prefix_missing"]
    assert arm["h"]["hang_turn"] == 2
    d = tmp_path / "d"
    _write(d, led, {"entries": []})
    _write(d, eq, {"entries": [{"entry_id": "h", "status": "skipped_hang", "hang_ref": {}}]})
    with pytest.raises(SystemExit, match=r"no hang_ref\.turn"):
        rp.load_arm([d], derive=False)
    # A recorded fire with no skipped_hang row in any continuation is refused.
    f = tmp_path / "f"
    _write(f, led, {"entries": []})
    _write(f, "hang_events.json", {"events": [{"entry_id": "z", "outcome": "stall"}]})
    with pytest.raises(SystemExit, match="no skipped_hang row"):
        rp.load_arm([f], derive=False)


# ------------------------------------------------------------------ modes, frontier, family
def _o(base: list[int], usd: list[float], trig: list[int], local: list[int]) -> dict[str, Any]:
    n = len(base)
    return {
        "ids": [f"e{k}" for k in range(n)],
        "base_pass": [bool(x) for x in base],
        "base_usd": usd,
        "trig": [bool(x) for x in trig],
        "late": [False] * n,
        "local": [bool(x) for x in local],
        "cloud_pass": [True] * n,
        "cloud_usd": [0.3] * n,
    }


def test_entry_outcomes_modes() -> None:
    arm = {"e": {"decoded": [[["l0"]], [["l1"]]], "trigger_turn": 1, "local_pass": False}}
    cloud = {
        "e": {
            "decoded": [[["c0"]], [["c1"]], [["c2"]]],
            "usd": [0.1, 0.2, 0.3],
            "cold_delta": [0.0, 0.05, 0.0],
            "pass": False,
        }
    }

    def score(_e: dict[str, Any], _m: list[list[list[str]]]) -> bool:
        return True

    sp = rp.entry_outcomes(arm, cloud, ["e"], score, {"e": {}}, mode="splice")
    rr = rp.entry_outcomes(arm, cloud, ["e"], score, {"e": {}}, mode="rerun")
    cd = rp.entry_outcomes(arm, cloud, ["e"], score, {"e": {}}, mode="cold")
    assert sp["base_usd"] == [pytest.approx(0.5)] and sp["base_pass"] == [True]
    assert rr["base_usd"] == [pytest.approx(0.6)] and rr["base_pass"] == [False]
    assert cd["base_usd"] == [pytest.approx(0.55)] and sp["late"] == [True]


def test_analytic_frontier_has_no_seed_and_keeps_neg_inf() -> None:
    a = _o([1, 1, 0, 0], [0.3, 0.3, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0])
    segs = rp.segments(a, range(4))
    assert segs[0] == pytest.approx((0.15, 0.5))
    assert rp.c_at(segs, 0.25) == pytest.approx(0.075)  # halfway down the thinning segment
    assert rp.q_at(segs, 0.0) == pytest.approx(0.0)
    # X never passes and never escalates beyond what fails: cannot reach Q* = 0.5.
    x = _o([0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0])
    x["cloud_pass"] = [False] * 4
    res = rp.analyse(
        {"splice": {"A": a, "P": x}}, [("P", "A")], primary=("P", "A"), boot=50, seed=1
    )
    c = res["contrasts"]["P vs A"]
    assert c["role"] == "primary" and c["splice"]["dC_iso"] == "-inf"
    assert c["splice"]["dC_iso_boot_neg_inf"] > 0
    assert c["rejects_at_alpha_0.05"] is False and "does not reach" in c["note"]


def test_matched_point_is_outcome_blind_and_deterministic() -> None:
    a = _o([1, 1, 1, 0], [0.3, 0.3, 0.3, 0], [1, 1, 1, 0], [0, 1, 0, 0])
    p1, info1 = rp.matched_point_passes(a, 0.15)
    p2, info2 = rp.matched_point_passes(a, 0.15)
    assert p1 == p2 and info1 == info2 and info1["segment"] == "down"


def test_fixed_sequence_gates_xps() -> None:
    def doc(rej: bool) -> dict[str, Any]:
        c = {"role": "primary", "rejects_at_alpha_0.05": rej, "splice": {"dC_iso": 0.01}}
        return {"all": {"contrasts": {"P vs A": c}}}

    f = rp.fixed_sequence(doc(False), doc(True))
    assert f["T2S"]["tested"] and not f["T2S"]["claim"]
    assert not f["XPS"]["tested"] and not f["XPS"]["claim"]
    g = rp.fixed_sequence(doc(True), doc(True))
    assert g["XPS"]["tested"] and g["XPS"]["claim"]


def test_cli_refuses_derive_on_heldout_and_short_cloud(tmp_path: Path) -> None:
    pin = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60.json"
    base = ["--cloud", str(tmp_path), "--arm", f"A={tmp_path}", "--bfcl-unpacked", str(tmp_path)]
    with pytest.raises(SystemExit, match="not allowed on DEMO2_HELDOUT_60"):
        rp.main(["--pin", str(pin), "--derive-triggers", *base, "--out", str(tmp_path / "o")])
    cal = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_CALIB_30.json"
    first = json.loads(cal.read_text(encoding="utf-8"))[0]
    _cloud_dir(tmp_path / "c", [_cloud_entry(str(first["id"]), 1)])
    args = ["--pin", str(cal), "--cloud", str(tmp_path / "c"), "--arm", f"A={tmp_path}"]
    with pytest.raises(SystemExit, match="fewer turns than user turns"):
        rp.main([*args, "--bfcl-unpacked", str(tmp_path), "--out", str(tmp_path / "o")])


# ------------------------------------------------------------------ H2 rebuild, flags
def test_rebuild_on_error_needs_resident_and_rebuilds(tmp_path: Path) -> None:
    ap = build_argparser()
    local = OpenVinoLocalBackend.__new__(OpenVinoLocalBackend)
    with pytest.raises(SystemExit, match="needs --resident-pipeline"):
        attach_be_modes(
            ap.parse_args(["--out", str(tmp_path), "--rebuild-on-error"]),
            ("local_only",),
            local,
            tmp_path,
        )
    a = ap.parse_args(["--out", str(tmp_path), "--resident-pipeline", "--rebuild-on-error"])
    rec = attach_be_modes(a, ("local_only",), local, tmp_path)
    assert rec is not None and local.rebuild_on_error and "rebuild_on_error" in rec
    local.load_meta = {"stubbed_generate": True}
    local.warmup_log_path = tmp_path / "w.jsonl"
    local.__dict__["_warmed_toolsets"] = {"X"}
    local._needs_rebuild = "generation_error entry=e turn=1"
    local._rebuild_resident({"id": "next"})
    assert local.__dict__["_warmed_toolsets"] == set() and local._prefix_reloads == 1
    row = json.loads((tmp_path / "w.jsonl").read_text().splitlines()[0])
    assert row["event"] == "PIPELINE_REBUILT" and row["before_entry_id"] == "next"
    assert "_needs_rebuild" not in local.__dict__


def test_launcher_passes_bf0_switches() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    assert "' --rebuild-on-error'" in text and "' --heldout-after-freeze'" in text
