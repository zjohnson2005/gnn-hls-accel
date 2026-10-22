"""Task BE: passive router, resident pipeline / tool-set warm-up, cloud-only retention, replay."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_iso_quality_replay as rp  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    AnthropicCloudBackend,
    BackendTurn,
    OpenVinoLocalBackend,
    attach_be_modes,
    attach_retention,
    build_argparser,
    order_by_toolset,
    passive_trigger_record,
    toolset_key,
)


def _bt(**kw: Any) -> BackendTurn:
    base: dict[str, Any] = {
        "n_ctx": 100,
        "ttft_s": 0.5,
        "decode_tok_s": 20.0,
        "emitted_parseable_tool_call": True,
        "cloud_tokens_in": 0,
        "cloud_tokens_out": 0,
        "cloud_usd": 0.0,
        "turn_wall_s": 1.0,
        "t_tool_exec": 0.0,
        "t_template_build": 0.0,
        "t_tokenize": 0.0,
        "t_generate": 1.0,
        "n_steps": 2,
    }
    base.update(kw)
    return BackendTurn(**base)


def test_passive_trigger_record_matches_router_order() -> None:
    assert passive_trigger_record(_bt(), generation_error_at_end=False)["mechanical"] is None
    r = passive_trigger_record(_bt(ttft_s=12.0), generation_error_at_end=False)
    assert r["mechanical"] == "ttft>10.0"
    r = passive_trigger_record(_bt(ctx_overflow={"n_ctx": 9}), generation_error_at_end=False)
    assert r["mechanical"] == "ctx_overflow"
    r = passive_trigger_record(_bt(n_steps=5), generation_error_at_end=False)
    assert r["mechanical"] is None and r["quality"] == "step_budget"
    r = passive_trigger_record(_bt(emitted_parseable_tool_call=False), generation_error_at_end=True)
    assert r["mechanical"] == "generation_error" and r["quality"] == "no_parseable_tool_call"


def test_toolset_key_and_order() -> None:
    def e(i: int, cls: list[str]) -> dict[str, Any]:
        return {"id": f"e{i}", "raw_entry": {"involved_classes": cls}}

    es = [e(0, ["A"]), e(1, ["B"]), e(2, ["A"]), e(3, ["C", "B"]), e(4, ["B", "C"])]
    assert toolset_key(es[3]) == toolset_key(es[4])
    assert [x["id"] for x in order_by_toolset(es)] == ["e0", "e2", "e1", "e3", "e4"]


def test_cli_defaults_off_and_refusals(tmp_path: Path) -> None:
    ap = build_argparser()
    a = ap.parse_args(["--out", str(tmp_path)])
    assert not (
        a.resident_pipeline or a.warm_toolset_prefix or a.passive_router or a.order_by_toolset
    )
    assert attach_be_modes(a, ("local_only",), object(), tmp_path) is None
    b = ap.parse_args(["--out", str(tmp_path), "--warm-toolset-prefix"])
    with pytest.raises(SystemExit, match="needs --resident-pipeline"):
        attach_be_modes(b, ("local_only",), object(), tmp_path)
    c = ap.parse_args(["--out", str(tmp_path), "--passive-router"])
    with pytest.raises(SystemExit, match="local_only alone"):
        attach_be_modes(c, ("slo_escalate",), object(), tmp_path)
    with pytest.raises(SystemExit, match="need OpenVINO"):
        attach_be_modes(c, ("local_only",), object(), tmp_path)


def test_attach_be_modes_sets_backend(tmp_path: Path) -> None:
    ap = build_argparser()
    a = ap.parse_args(
        ["--out", str(tmp_path), "--resident-pipeline", "--warm-toolset-prefix", "--passive-router"]
    )
    local = OpenVinoLocalBackend.__new__(OpenVinoLocalBackend)
    rec = attach_be_modes(a, ("local_only",), local, tmp_path)
    assert rec is not None and rec["task"] == "BE"
    assert local.resident_pipeline and local.warm_toolset_prefix and local.passive_router
    assert local.warmup_log_path == tmp_path / "toolset_warmups.jsonl"


def test_warm_toolset_once_per_toolset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tools.bfcl_feasibility_probe as probe

    calls: list[str] = []

    class Pipe:
        def generate(self, prompts: list[str], cfg: Any) -> Any:
            calls.append(prompts[0])

    class Cfg:
        pass

    local = OpenVinoLocalBackend.__new__(OpenVinoLocalBackend)
    local.pipe = Pipe()
    local.tokenizer = lambda text: {"input_ids": list(range(len(text)))}
    local.ov_genai = types.SimpleNamespace(GenerationConfig=Cfg)
    local.warm_toolset_prefix = True
    local.warmup_log_path = tmp_path / "w.jsonl"
    monkeypatch.setattr(probe, "tools_for_entry", lambda _e: [{"name": "t"}])
    monkeypatch.setattr(probe, "render_bfcl_tools_style", lambda _tok, _m, _t: "PROMPT")
    e1 = {"id": "a", "raw_entry": {"involved_classes": ["X"]}}
    e2 = {"id": "b", "raw_entry": {"involved_classes": ["X"]}}
    e3 = {"id": "c", "raw_entry": {"involved_classes": ["Y"]}}
    for e in (e1, e2, e3):
        local._warm_toolset(e)
    assert len(calls) == 2
    assert len((tmp_path / "w.jsonl").read_text().splitlines()) == 2


def test_retention_cloud_only() -> None:
    ap = build_argparser()

    class Tok:
        def __call__(self, text: str, add_special_tokens: bool = True) -> dict[str, list[int]]:
            return {"input_ids": [ord(c) for c in text]}

        def decode(self, ids: list[int], skip_special_tokens: bool = False) -> str:
            return "".join(chr(i) for i in ids)

    local = types.SimpleNamespace(obs_mask=None, tokenizer=Tok())
    cloud = AnthropicCloudBackend(client=None, cloud_model="m")
    a = ap.parse_args(
        ["--policy", "hybrid_full", "--retention-k", "1024", "--retention-cloud-only"]
    )
    plan, rb = attach_retention(a, local, cloud)
    assert local.obs_mask is None and cloud.obs_mask is rb and plan["local"] == "FULL"


def _outcomes(
    base: list[int],
    usd: list[float],
    trig: list[int],
    local: list[int],
    cp: list[int],
    cu: list[float],
) -> dict[str, list[Any]]:
    return {
        "base_pass": [bool(x) for x in base],
        "base_usd": usd,
        "trig": [bool(x) for x in trig],
        "local": [bool(x) for x in local],
        "cloud_pass": [bool(x) for x in cp],
        "cloud_usd": cu,
    }


def test_frontier_and_iso_endpoints() -> None:
    cp = [1, 1, 1, 1, 0, 1]
    cu = [0.3] * 6
    # A: two triggered entries (escalated, pass), four local failures.
    a = _outcomes([1, 1, 0, 0, 0, 0], [0.3, 0.3, 0, 0, 0, 0], [1, 1, 0, 0, 0, 0], [0] * 6, cp, cu)
    # X: same escalations, plus one extra local pass -> same cost, higher quality.
    x = _outcomes(
        [1, 1, 1, 0, 0, 0], [0.3, 0.3, 0, 0, 0, 0], [1, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0], cp, cu
    )
    res = rp.analyse({"A": a, "X": x}, "A", boot=200, seed=1)
    assert res["Q_star"] == pytest.approx(2 / 6) and res["C_star"] == pytest.approx(0.1)
    xr = res["arms"]["X"]
    assert xr["dQ_iso"] == pytest.approx(1 / 6)
    # X reaches 2/6 by thinning one escalation: cost 0.05 -> saves 0.05 per task.
    assert xr["dC_iso"] == pytest.approx(0.05)
    assert xr["mcnemar_at_matched_cost"]["b"] >= 1
    assert set(res["holm"]) == {"X:dC_iso", "X:mcnemar"}


def test_mcnemar_and_holm() -> None:
    assert rp.mcnemar_exact([True] * 6, [False] * 6)["p"] == pytest.approx(2 / 64)
    assert rp.mcnemar_exact([True, False], [True, False])["p"] == 1.0
    h = rp.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert (
        h["a"] == pytest.approx(0.03)
        and h["c"] == pytest.approx(0.06)
        and h["b"] == pytest.approx(0.06)
    )


def test_entry_outcomes_merges_local_then_cloud() -> None:
    seen: list[Any] = []

    def score(entry: dict[str, Any], merged: list[list[list[str]]]) -> bool:
        seen.append(merged)
        return True

    arm = {"e": {"decoded": [[["l0"]], [["l1"]]], "trigger_turn": 1, "local_pass": False}}
    cloud = {
        "e": {"decoded": [[["c0"]], [["c1"]], [["c2"]]], "usd": [0.1, 0.2, 0.3], "pass": False}
    }
    o = rp.entry_outcomes(arm, cloud, ["e"], score, {"e": {}})
    assert seen == [[[["l0"]], [["c1"]], [["c2"]]]]
    assert o["base_usd"] == [pytest.approx(0.5)] and o["base_pass"] == [True]


def test_queue_helper_resume_offset() -> None:
    from tools.demo2_queue_helper import resume_offset

    es = [
        {"id": "a", "raw_entry": {"involved_classes": ["X"]}},
        {"id": "b", "raw_entry": {"involved_classes": ["Y"]}},
        {"id": "c", "raw_entry": {"involved_classes": ["X"]}},
    ]
    assert resume_offset(es, "c", order=False) == 2
    assert resume_offset(es, "c", order=True) == 1
    with pytest.raises(SystemExit):
        resume_offset(es, "z", order=True)
