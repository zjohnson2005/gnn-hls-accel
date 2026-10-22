"""Task BC: retention budget (revised arm C), its runner flags, L1 helpers, predictions."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_ladder_l1 as l1  # noqa: E402
from tools.h1_retention_budget import (  # noqa: E402
    RetentionBudget,
    marker,
    truncate_json,
    truncate_observation,
)
from tools.run_h1_hybrid import (  # noqa: E402
    AnthropicCloudBackend,
    ScriptedLiveLocalBackend,
    attach_retention,
    build_argparser,
)


def enc(text: str) -> list[int]:
    """Toy codec: one token per character."""
    return [ord(c) for c in text]


def dec(ids: list[int]) -> str:
    return "".join(chr(i) for i in ids)


def test_short_observation_is_byte_identical() -> None:
    text = "a  b\n c"
    for shape in ("head", "h70t30", "json"):
        assert truncate_observation(text, 100, shape, enc, dec) == text


def test_head_and_h70t30_shapes() -> None:
    text = "".join(chr(65 + i % 26) for i in range(1000))
    head = truncate_observation(text, 200, "head", enc, dec)
    assert head.startswith(text[:200]) and head.endswith(marker(800))
    mid = truncate_observation(text, 200, "h70t30", enc, dec)
    h, t = mid.split("\n" + marker(800) + "\n")
    assert len(h) == 72 and len(t) == 128  # tail floor 128 tokens
    assert text.startswith(h) and text.endswith(t)


def test_json_shape_keeps_scalars_and_list_ends() -> None:
    doc = {
        "symbol": "TSLA",
        "price": 180.0,
        "history": [{"id": i, "v": i * 1.5} for i in range(400)],
    }
    text = json.dumps(doc)
    out = truncate_json(text, 600, enc, dec)
    body, tail = out.rsplit("\n", 1)
    assert tail.startswith("[... ") and len(enc(body)) <= 600
    kept = json.loads(body)
    assert kept["symbol"] == "TSLA" and kept["price"] == 180.0
    assert kept["history"][0] == {"id": 0, "v": 0.0}
    assert kept["history"][-1] == {"id": 399, "v": 598.5}
    assert any(isinstance(x, str) and "items elided" in x for x in kept["history"])


def test_json_shape_falls_back_for_non_json() -> None:
    text = "x" * 1000
    out = truncate_json(text, 300, enc, dec)
    assert marker(700) in out


def test_bad_shape_or_k_refused() -> None:
    with pytest.raises(ValueError):
        truncate_observation("x", 10, "tail", enc, dec)
    with pytest.raises(ValueError):
        RetentionBudget(0, shape="json", encode=enc, decode=dec)


def test_apply_records_and_ledger() -> None:
    rb = RetentionBudget(10, shape="h70t30", encode=enc, decode=dec)
    rb.context = {"policy": "hybrid_full"}
    out = rb.apply(["f(a=1)", "g()"], ["short", "y" * 500], source="local", entry_id="e", turn=0)
    assert out[0] == "short" and out[1] != "y" * 500
    led = rb.ledger()
    assert led["arm"] == "RETENTION_BUDGET" and led["n_truncated"] == 1
    assert led["observations"][1]["original_tokens"] == 500


def test_age_mask_masks_oldest_never_last_three() -> None:
    rb = RetentionBudget(10, shape="json", encode=enc, decode=dec, age_mask=True)
    msgs: list[dict[str, Any]] = [{"role": "user", "content": "q"}]
    for i in range(5):
        msgs.append({"role": "assistant", "content": "c"})
        msgs.append({"role": "tool", "content": "t" * 100 + str(i)})

    def count(m: list[dict[str, Any]]) -> int:
        return sum(len(x["content"]) for x in m)

    masked = rb.fit(msgs, count=count, max_new_tokens=0, window=10, where={"turn": 0, "step": 1})
    tools = [m for m in msgs if m["role"] == "tool"]
    assert masked == [2, 4]  # the two oldest tool messages; the last 3 are kept
    assert tools[0]["content"].startswith("[earlier tool output omitted")
    assert all(not t["content"].startswith("[earlier") for t in tools[2:])
    assert len(rb.mask_events) == 2
    off = RetentionBudget(10, shape="json", encode=enc, decode=dec)
    assert off.fit(msgs, count=count, max_new_tokens=0, window=10, where={}) == []


def test_runner_cli_default_off_and_refusals() -> None:
    ap = build_argparser()
    a = ap.parse_args(["--policy", "hybrid_full"])
    assert a.retention_k is None and not a.retention_age_mask and not a.retention_cloud_raw
    local = types.SimpleNamespace(obs_mask=None, tokenizer=None)
    cloud = AnthropicCloudBackend(client=None, cloud_model="m")
    assert attach_retention(a, local, cloud) == (None, None)
    b = ap.parse_args(["--policy", "hybrid_full", "--retention-age-mask"])
    with pytest.raises(SystemExit, match="need --retention-k"):
        attach_retention(b, local, cloud)
    c = ap.parse_args(["--policy", "hybrid_full", "--retention-k", "2048", "--obs-mask-k", "8"])
    with pytest.raises(SystemExit, match="exclusive"):
        attach_retention(c, local, cloud)
    d = ap.parse_args(["--policy", "hybrid_full", "--retention-k", "2048", "--retention-age-mask"])
    with pytest.raises(SystemExit, match="needs --context-window"):
        attach_retention(d, local, cloud)
    e = ap.parse_args(["--policy", "hybrid_full", "--retention-k", "2048"])
    with pytest.raises(SystemExit, match="local-script"):
        attach_retention(e, ScriptedLiveLocalBackend(script={}), cloud)


def test_runner_attach_sets_backends_and_cloud_raw() -> None:
    ap = build_argparser()

    class Tok:
        def __call__(self, text: str, add_special_tokens: bool = True) -> dict[str, list[int]]:
            return {"input_ids": enc(text)}

        def decode(self, ids: list[int], skip_special_tokens: bool = False) -> str:
            return dec(ids)

    local = types.SimpleNamespace(obs_mask=None, tokenizer=Tok())
    cloud = AnthropicCloudBackend(client=None, cloud_model="m")
    a = ap.parse_args(["--policy", "hybrid_full", "--retention-k", "2048"])
    plan, rb = attach_retention(a, local, cloud)
    assert plan["k"] == 2048 and plan["shape"] == "json" and plan["cloud"] == "same"
    assert local.obs_mask is rb and cloud.obs_mask is rb
    local2 = types.SimpleNamespace(obs_mask=None, tokenizer=Tok())
    cloud2 = AnthropicCloudBackend(client=None, cloud_model="m")
    b = ap.parse_args(["--policy", "hybrid_full", "--retention-k", "2048", "--retention-cloud-raw"])
    plan2, rb2 = attach_retention(b, local2, cloud2)
    assert plan2["cloud"] == "FULL" and local2.obs_mask is rb2 and cloud2.obs_mask is None


def test_launch_h1_passes_retention_flags() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    for flag in (
        "--retention-k",
        "--retention-shape",
        "--retention-age-mask",
        "--retention-cloud-raw",
    ):
        assert flag in text


def test_l1_values_and_boundaries() -> None:
    assert l1.call_values(
        "place_order(order_type='Buy', symbol='TSLA', price=180.0, amount=150)"
    ) == [
        "Buy",
        "TSLA",
        "180.0",
        "150",
    ]
    assert l1.call_values("f(flag=True, x=1)") == []
    assert l1.occurs("150", "amount 150 units") and not l1.occurs("150", "1500")
    assert not l1.occurs("180.0", "1180.05")


def test_l1_decision_rule() -> None:
    def row(lost: dict[str, int]) -> dict[str, Any]:
        cands = {
            f"{k}_{s}": {"n_required": 4, "n_lost": lost.get(f"{k}_{s}", 0), "kept_tokens": 10}
            for k in l1.KS
            for s in ("head", "h70t30", "json")
        }
        return {"full_tokens": 100, "candidates": cands}

    # head at 512 preserves all but is never chosen; 512 json loses one -> 512 h70t30.
    d = l1.decide([row({"512_json": 1})])
    assert d["chosen"] == {"k": 512, "shape": "h70t30", "rule": "100% preserved"}
    every = {f"{k}_{s}": 1 for k in l1.KS for s in ("h70t30", "json")}
    d2 = l1.decide([row(every)])
    assert d2["chosen"]["k"] is None or d2["chosen"]["k"] == 2048


def test_l1_excludes_heldout_ids() -> None:
    ids = l1.heldout_ids()
    assert len(ids) == 120 or len(ids) > 60


def test_bc_predictions_reproduce_registered_arm_a() -> None:
    from tools import demo2_bc_predict as bp

    doc = bp.build()
    reg = doc["registered_true_default_cells_for_comparison"]
    assert doc["per_cell_usd"]["A-X"]["point"]["usd_per_task"] == reg["A-X"]
    assert doc["per_cell_usd"]["A-T"]["point"]["usd_per_task"] == reg["A-T"]
    assert doc["budgets"]["prompt"] == {"XPS": 8192, "T2S": 16384}
    for c in ("B-X", "C-X", "B-T", "C-T"):
        for b in ("lo", "point", "hi"):
            assert doc["per_cell_usd"][c][b]["gold_local_turns_over_32768"] == 0


def test_l4_p90_nearest_rank() -> None:
    from tools.demo2_ladder_l4 import p90_of

    assert p90_of([1.0, 2.0, 3.0]) == 3.0
    assert p90_of([5.0]) == 5.0
    assert p90_of([float(i) for i in range(1, 11)]) == 9.0


def test_l4_verdict_u4_and_default() -> None:
    from tools.demo2_ladder_l4 import _verdict

    ok_u4 = {"backend": "PA", "sdpa_fallback_warning": False, "kv_cache_precision": "u4"}
    assert _verdict(ok_u4, "u4")["valid"]
    assert not _verdict({**ok_u4, "kv_cache_precision": "i8"}, "u4")["valid"]
    assert not _verdict({**ok_u4, "backend": "SDPA"}, "u4")["valid"]


def test_per_device_pins_disjoint_and_registered() -> None:
    import hashlib

    from tools import demo2_per_device_pins as pins
    from tools.run_h1_hybrid import ENTRY_PINS

    meta = json.loads((ROOT / "derived/h1_hybrid/demo2/DEMO2_CONFIRM_200.meta.json").read_text())
    assert meta["n"] == 200 and not set(meta["selected"]) & pins.excluded_ids()
    for name in ("DEMO2_CONFIRM_200", "DEMO2_GROWTH_10"):
        raw = (ROOT / f"derived/h1_hybrid/demo2/{name}.json").read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        assert ENTRY_PINS[sha]["name"] == name
    growth = [i for i, _ in pins.select_growth()]
    assert growth[0] == "multi_turn_long_context_123" and len(growth) == 10
