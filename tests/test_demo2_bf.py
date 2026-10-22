"""Task BF: replay scorer uses one BFCL checker name per call."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_iso_quality_replay as rp  # noqa: E402


def test_score_fn_never_reuses_checker_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # bfcl_score_fn sets module and interpreter state; restore all of it after the test.
    import tools.bfcl_feasibility_probe as probe

    monkeypatch.setattr(probe, "BFCL_UNPACKED", probe.BFCL_UNPACKED)
    monkeypatch.setattr(sys, "path", list(sys.path))
    if "openvino_genai" not in sys.modules:
        monkeypatch.setitem(sys.modules, "openvino_genai", None)
        monkeypatch.delitem(sys.modules, "openvino_genai")
    score = rp.bfcl_score_fn(tmp_path)

    names: list[str] = []

    def fake(**kw: Any) -> dict[str, Any]:
        names.append(str(kw["model_name"]))
        return {"valid": True}

    monkeypatch.setattr(probe, "score_multi_turn", fake)
    entry = {"id": "multi_turn_base_1", "raw_entry": {}, "reference": []}
    for _ in range(3):
        assert score(entry, [[["pwd()"]]])
    assert len(set(names)) == 3
    assert all(n.startswith("replay_multi_turn_base_1_") for n in names)


def test_nearest_rank_p5_and_aa_floor() -> None:
    from tools import demo2_freeze_values as fv

    xs = [float(x) for x in range(1, 101)]
    assert fv.nearest_rank(xs, 0.05) == 5.0
    assert fv.nearest_rank([3.0], 0.05) == 3.0
    assert fv.nearest_rank([], 0.05) is None

    def run(steps: list[list[str]], ok: bool, t_gen: float) -> dict[str, Any]:
        turn = {"turn": 0, "decoded_steps": steps}
        return {
            "_eq": {"e1": {"local_pass": ok}},
            "_tl": {"e1": {"turns": [turn]}},
            "t_generate_p50": t_gen,
        }

    aa = fv.aa_floor(run([["a()"], ["b()"]], True, 1.0), run([["a()"]], False, 3.0))
    assert aa["n_discordant"] == 1
    assert (aa["step_positions"], aa["step_mismatches"]) == (2, 1)
    assert aa["d_lat"] == 1.0
