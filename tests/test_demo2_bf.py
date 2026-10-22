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
    score = rp.bfcl_score_fn(tmp_path)
    import tools.bfcl_feasibility_probe as probe

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
