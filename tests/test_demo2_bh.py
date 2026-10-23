"""Task BH: DEMO-2 F2 family (non-dollar objectives) and its predictions."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_bf0_predict as bf0  # noqa: E402
from tools import demo2_bh_predict as bh  # noqa: E402
from tools import demo2_f2_objectives as f2  # noqa: E402

DEMO2 = ROOT / "derived" / "h1_hybrid" / "demo2"


def _write_run(
    d: Path,
    entries: list[dict[str, Any]],
    *,
    window: int | None = None,
    steps: list[dict[str, Any]] | None = None,
    quality: list[dict[str, Any]] | None = None,
    hangs: list[dict[str, Any]] | None = None,
) -> Path:
    pol = d / "policies" / "local_only"
    pol.mkdir(parents=True)
    (pol / "turn_ledger.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    if quality is not None:
        (pol / "entry_quality.json").write_text(json.dumps({"entries": quality}), encoding="utf-8")
    plan: dict[str, Any] = {}
    if window is not None:
        plan["local_limits"] = {"context_window": {"tokens": window}}
    (d / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    lines = [json.dumps(s) for s in steps or []]
    (d / "step_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if hangs is not None:
        (d / "hang_events.json").write_text(json.dumps({"events": hangs}), encoding="utf-8")
    return d


def _entry(eid: str, ok: bool, stop: str, walls: list[float]) -> dict[str, Any]:
    turns = [{"turn": k, "placement": "local", "turn_wall_s": w} for k, w in enumerate(walls)]
    return {"entry_id": eid, "local_pass": ok, "stop_reason": stop, "turns": turns}


def _gen(
    eid: str, turn: int, step: int, prompt: int, out: int, ok: bool = True
) -> list[dict[str, Any]]:
    k = {"entry_id": eid, "turn": turn, "step": step, "policy": "local_only"}
    return [
        {**k, "event": "pre_generate", "prompt_tokens": prompt},
        {
            **k,
            "event": "post_generate",
            "generated_tokens": out,
            "ok": ok,
            "error": None,
            "wall_s": 1.0,
        },
    ]


def test_silent_overrun_loud_and_cap(tmp_path: Path) -> None:
    steps = _gen("e1", 0, 0, 40_800, 512) + _gen("e2", 0, 0, 41_000, 10) + _gen("e3", 0, 0, 1000, 5)
    entries = [
        _entry("e1", False, "completed", [5.0]),  # 41,312 positions, no error -> silent
        _entry("e2", False, "generation_error", [5.0]),  # over, but loud
        _entry("e3", True, "completed", [1.0]),
    ]
    a = f2.load_arm([_write_run(tmp_path / "a", entries, steps=steps)])
    assert a["e1"]["a_silent_overrun"] and a["e1"]["cap"] == 40_960
    assert a["e2"]["overrun"] and a["e2"]["loud"] and not a["e2"]["a_silent_overrun"]
    assert not a["e3"]["overrun"]
    c = f2.load_arm([_write_run(tmp_path / "c", entries, window=8704, steps=steps)])
    assert c["e1"]["cap"] == 8704


def test_hang_entry_wall_lower_bound_and_hang_loop(tmp_path: Path) -> None:
    steps = _gen("h", 0, 0, 2000, 50)
    hung = _write_run(
        tmp_path / "hung",
        [_entry("x", True, "max_steps", [2.0])],
        steps=steps,
        hangs=[{"entry_id": "h", "outcome": "stall", "elapsed_s": 900.0, "turn": 1}],
    )
    cont = _write_run(
        tmp_path / "cont",
        [],
        quality=[{"entry_id": "h", "status": "skipped_hang", "hang_ref": {"turn": 1}}],
    )
    arm = f2.load_arm([hung, cont])
    assert arm["h"]["b_wall"] == pytest.approx(901.0)
    assert arm["h"]["wall_lower_bound"] and arm["h"]["d_hang_loop"] and arm["h"]["loud"]
    assert arm["x"]["d_hang_loop"]  # max_steps counts as a loop


def test_family_holm_m6_and_by_construction_excluded(tmp_path: Path) -> None:
    ids = [f"e{k}" for k in range(20)]

    def arm(scale: float, fail: bool) -> dict[str, dict[str, Any]]:
        return {
            i: {
                "local_pass": not fail,
                "stop_reason": "completed",
                "cap": 40_960,
                "max_positions": 0,
                "n_generates_over_cap": 0,
                "overrun": False,
                "loud": False,
                "a_silent_overrun": False,
                "b_wall": scale * (10.0 + k),
                "wall_lower_bound": False,
                "d_hang_loop": False,
            }
            for k, i in enumerate(ids)
        }

    res = f2.analyse({"A": arm(2.0, True), "P": arm(1.0, True), "C": arm(1.0, False)}, ids)
    assert res["F2"]["m"] == 6
    assert "a_silent_overrun | A vs P" not in res["F2"]["holm_adjusted"]
    p = res["contrasts"]["A vs P"]
    assert p["b_wall"]["favours"] == "X" and p["b_wall"]["rejects_holm_0.05"]
    assert "P improves on A for b_wall" in res["F2"]["claims"]
    c = res["contrasts"]["A vs C"]["c_time_to_failure"]
    assert not c["testable"] and c["p"] == 1.0  # C never fails: p = 1, m stays 6
    assert res["contrasts"]["A vs C"]["d_hang_loop"]["p"] == 1.0  # 0 vs 0


def test_wilcoxon_all_zero_is_p1() -> None:
    assert f2.wilcoxon([0.0, 0.0])["p"] == 1.0


def test_bf0_file_unchanged_and_i4k_rows_host_independent() -> None:
    # OBJ section 1: the identical P / C vs I-4K values follow from inputs with no host term.
    doc = json.loads((DEMO2 / "DEMO2_BF0_PREDICTIONS.json").read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(bf0.build()))
    for k in ("P vs I-4K", "C vs I-4K"):
        assert doc["contrasts"]["XPS"][k] == doc["contrasts"]["T2S"][k]
    assert bf0.f_ref("I-4K", 0.1) == bf0.f_ref("I-4K", 0.9)


def test_committed_f2_predictions_match_generator() -> None:
    doc = json.loads((DEMO2 / "DEMO2_BH_F2_PREDICTIONS.json").read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(bh.build()))
    assert doc["runner_must_not_read_this_file"] is True


def test_runner_never_reads_bh_files() -> None:
    for name in ("run_h1_hybrid.py", "launch_h1.ps1", "context_window.py"):
        text = (ROOT / "tools" / name).read_text(encoding="utf-8")
        for needle in (
            "DEMO2_BH_F2",
            "DEMO2_AMEND_2026-10-23",
            "demo2_f2_objectives",
        ):
            assert needle not in text
