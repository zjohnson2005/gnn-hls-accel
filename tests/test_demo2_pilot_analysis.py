"""tools/demo2_pilot_analysis.py: pilot decision rules on synthetic run dirs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import demo2_pilot_analysis as pa  # noqa: E402


def _run(tmp: Path, name: str, entries: list[dict[str, Any]], tele: list[dict[str, Any]]) -> Path:
    d = tmp / name
    d.mkdir()
    (d / "turn_ledger.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    (d / pa.TELEMETRY).write_text("".join(json.dumps(r) + "\n" for r in tele), encoding="utf-8")
    return d


def _tele(text: str, dec: float, writes: int = 10, toks: int = 10) -> list[dict[str, Any]]:
    return [
        {
            "entry_id": "e1",
            "policy": "hybrid_full",
            "turn": 0,
            "steps": [
                {
                    "step": 0,
                    "generated_tokens": 100,
                    "decode_tok_s": dec,
                    "raw_text": text,
                    "streamer_writes": writes,
                    "streamer_tokens": toks,
                }
            ],
        }
    ]


def _entry(eid: str, ok: bool, usd: float, gen: float = 4.0) -> dict[str, Any]:
    return {
        "entry_id": eid,
        "hybrid_pass": ok,
        "cloud_usd_entry": usd,
        "turns": [{"turn": 0, "placement": "local", "t_generate": gen, "n_ctx": 5000}],
    }


def test_p1_share_and_lever(tmp_path: Path) -> None:
    text = "<tool_call>" + "x" * 8 + "</tool_call>" + "y" * 81
    d = _run(tmp_path, "r", [], _tele(text, 25.0))
    v = pa.p1([d])
    assert v["share"]["tool_call"] < 0.5 and v["lever_exists"] is True


def test_p4_identity_and_speedup(tmp_path: Path) -> None:
    off = _run(tmp_path, "off", [], _tele("same", 20.0))
    on = _run(tmp_path, "on", [], _tele("same", 24.0, writes=5, toks=10))
    v = pa.p4(off, on)
    assert v["outputs_identical"] and v["decode_speedup_median"] == 1.2 and v["adopt"]
    assert v["tokens_per_streamer_write_on"] == 2.0
    diff = _run(tmp_path, "diff", [], _tele("other", 30.0))
    assert pa.p4(off, diff)["adopt"] is False


def test_p5_p7_p8(tmp_path: Path) -> None:
    k512 = _run(tmp_path, "k512", [_entry("a", True, 0.1), _entry("b", False, 0.1)], [])
    k1024 = _run(tmp_path, "k1024", [_entry("a", True, 0.2), _entry("b", False, 0.2)], [])
    k2048 = _run(tmp_path, "k2048", [_entry("a", True, 0.3), _entry("b", True, 0.3)], [])
    assert pa.p5(k512, k1024, k2048)["chosen_k"] == 512
    a1 = _run(tmp_path, "a1", [_entry(f"e{i}", i < 2, 0.10) for i in range(4)], [])
    a2 = _run(tmp_path, "a2", [_entry(f"e{i}", i in (1, 2), 0.12, 5.0) for i in range(4)], [])
    v7 = pa.p7(a1, a2)
    assert v7["discordant"] == 2 and v7["replicates"] == 2
    assert v7["material_win_floors"]["usd"] == 0.3636  # 2 x 0.02 / 0.11 beats the 25% floor
    v8 = pa.p8(a1, a2)
    assert v8["n_paired"] == 4 and "keep_u4" in v8


def _p9_dir(tmp: Path, medians: list[float]) -> Path:
    d = tmp / "p9"
    (d / "points").mkdir(parents=True)
    for i, m in enumerate(medians):
        doc = {
            "point_index": i,
            "median_decode_tok_s": m,
            "repeats": [{"decode_tok_s": m}, {"decode_tok_s": m}, {"decode_tok_s": m}],
        }
        (d / "points" / f"x_i{i:02d}_n3500.json").write_text(json.dumps(doc), encoding="utf-8")
    return d


def test_p9_drift_rule(tmp_path: Path) -> None:
    flat = pa.p9(_p9_dir(tmp_path / "a", [25.0] * 4 + [30.0] * 4 + [25.5] * 4))
    assert flat["third"] == 4
    assert flat["drift_point_medians"] == 0.02 and flat["warmup_rule"] is False
    slow = pa.p9(_p9_dir(tmp_path / "b", [25.0] * 4 + [24.0] * 4 + [23.5] * 4))
    assert slow["drift_point_medians"] == -0.06 and slow["warmup_rule"] is True


def test_interleaved_root_reads_the_one_policy_ledger(tmp_path: Path) -> None:
    root = tmp_path / "interleaved_x"
    pol = root / "policies" / "local_only"
    pol.mkdir(parents=True)
    ents = [{"entry_id": "e1", "local_pass": True, "turns": [{"placement": "local", "n_ctx": 9}]}]
    (pol / "turn_ledger.json").write_text(json.dumps({"entries": ents}), encoding="utf-8")
    assert pa._entries(root) == ents
    (root / "policies" / "slo_escalate").mkdir()
    (root / "policies" / "slo_escalate" / "turn_ledger.json").write_text(
        json.dumps({"entries": []}), encoding="utf-8"
    )
    try:
        pa._entries(root)
    except SystemExit as exc:
        assert "several policies" in str(exc)
    else:
        raise AssertionError("expected a refusal")
