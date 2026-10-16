"""run_decode_match --pilot (Task AV): only the registered P9/P2 n lists; default unchanged."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import run_decode_match as rdm  # noqa: E402

SPEC = ["--model-spec", "configs/models/Qwen3-4B-int4-ov.yaml"]
INT8 = ["--model-spec", "configs/models/Qwen3-4B-int8-ov.yaml"]


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    def fake(**kwargs: Any) -> int:
        seen.append(kwargs)
        return 0

    monkeypatch.setattr(rdm, "run_decode", fake)
    return seen


def test_default_unchanged(calls: list[dict[str, Any]]) -> None:
    assert rdm.main(["--arm", "gpu_only", *SPEC, *INT8, "--session-id", "s1"]) == 0
    kw = calls[0]
    assert set(kw) == {"arm", "model_specs", "session_id", "out_dir"}
    assert kw["out_dir"] == ROOT / "derived" / "c2_ttft" / "s1"
    assert rdm.main(["--arm", "gpu_only", *SPEC, *INT8, "--n", "2000,4000,8000"]) == 0


@pytest.mark.parametrize("n", ["3500", "3500,12000,20000", "2000,4000"])
def test_default_refuses_other_n(calls: list[dict[str, Any]], n: str) -> None:
    with pytest.raises(SystemExit, match="decode n must be 2000,4000,8000"):
        rdm.main(["--arm", "gpu_only", *SPEC, *INT8, "--n", n])
    assert calls == []


def test_p9_registered_list(calls: list[dict[str, Any]]) -> None:
    n = ",".join(["3500"] * 12)
    assert (
        rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", "p9", "--n", n, "--session-id", "x"]) == 0
    )
    kw = calls[0]
    assert kw["n_list"] == (3500,) * 12
    assert kw["pilot"] == "p9"
    assert kw["out_dir"] == ROOT / "derived" / "demo2_pilots" / "p9_x"
    assert rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", "p9"]) == 0
    assert calls[1]["n_list"] == (3500,) * 12


def test_p2_registered_list(calls: list[dict[str, Any]]) -> None:
    for arm in ("gpu_only", "gpu_only_u4", "gpu_only_f16"):
        args = ["--arm", arm, *SPEC, "--pilot", "p2", "--n", "3500,12000,20000"]
        assert rdm.main(args) == 0
    assert [c["n_list"] for c in calls] == [(3500, 12000, 20000)] * 3


@pytest.mark.parametrize(
    "pilot,n",
    [
        ("p9", ",".join(["3500"] * 11)),
        ("p9", "3500,12000,20000"),
        ("p2", "3500,12000"),
        ("p2", "3500,12000,20000,30000"),
        ("p2", "2000,4000,8000"),
    ],
)
def test_pilot_refuses_other_n(calls: list[dict[str, Any]], pilot: str, n: str) -> None:
    with pytest.raises(SystemExit, match=f"pilot {pilot} n must be"):
        rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", pilot, "--n", n])
    assert calls == []


def test_pilot_refuses_out_and_two_specs(calls: list[dict[str, Any]], tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no --out"):
        rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", "p2", "--out", str(tmp_path)])
    with pytest.raises(SystemExit, match="exactly one --model-spec"):
        rdm.main(["--arm", "gpu_only", *SPEC, *INT8, "--pilot", "p2"])
    with pytest.raises(SystemExit):
        rdm.main(["--arm", "gpu_only", *SPEC, "--pilot", "p3"])
    assert calls == []


def test_run_decode_signature_defaults() -> None:
    import inspect

    from tools import boot4_session as b4

    params = inspect.signature(b4.run_decode).parameters
    assert params["n_list"].default == b4.DECODE_N == (2000, 4000, 8000)
    assert params["pilot"].default is None
