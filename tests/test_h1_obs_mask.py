"""OBS_MASK live arm (tools/h1_obs_mask.py) in run_h1_hybrid and the sizing tool."""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.h1_obs_mask import ObservationMask, cloud_hook, install_on_session  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    AnthropicCloudBackend,
    ScriptedLiveLocalBackend,
    StubCloudBackend,
    StubLocalBackend,
    attach_obs_mask,
    build_argparser,
    run_interleaved_session,
    write_obs_mask_ledger,
)

LAUNCH_H1 = ROOT / "tools" / "launch_h1.ps1"
PIN_DIR = ROOT / "derived" / "h1_hybrid" / "demo1"


def test_apply_masks_and_records_every_observation() -> None:
    mask = ObservationMask(3, token_count=lambda t: len(t))
    mask.context = {"policy": "slo_escalate"}
    out = mask.apply(
        ["ls(a=1)", "cat(b=2)"],
        ["one two three four", "x  y"],
        source="local",
        entry_id="e1",
        turn=2,
    )
    assert out == ["one two three", "x y"]
    first, second = mask.records
    assert first == {
        "policy": "slo_escalate",
        "source": "local",
        "entry_id": "e1",
        "turn": 2,
        "call": "ls",
        "original_ws_tokens": 4,
        "kept_ws_tokens": 3,
        "truncated": True,
        "original_tokens": 18,
        "kept_tokens": 13,
    }
    assert second["truncated"] is False and second["kept_tokens"] == 3
    ledger = mask.ledger()
    assert ledger["k"] == 3 and ledger["n_observations"] == 2 and ledger["n_truncated"] == 1


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError):
        ObservationMask(0)


def test_install_on_session_and_cloud_hook() -> None:
    session = types.SimpleNamespace(_next_turn_idx=1)

    def execute(decoded: list[str], *_args: Any, **_kwargs: Any) -> tuple[list[str], str]:
        return ["a b c d e"] * len(decoded), "inst"

    session._execute_multi_turn_func_call = execute
    mask = ObservationMask(2)
    install_on_session(session, mask, entry_id="e9")
    texts, inst = session._execute_multi_turn_func_call(["f()"], {}, [], "m", "e9")
    assert texts == ["a b"] and inst == "inst"
    assert mask.records[-1]["source"] == "local" and mask.records[-1]["turn"] == 1
    hook = cloud_hook(mask, entry_id="e9")
    assert hook(["g()"], ["p q r"], 3) == ["p q"]
    assert mask.records[-1]["source"] == "cloud" and mask.records[-1]["turn"] == 3


def test_attach_sets_both_backends_and_default_is_off() -> None:
    local = types.SimpleNamespace(obs_mask=None, tokenizer=None)
    cloud = AnthropicCloudBackend(client=None, cloud_model="m")
    assert attach_obs_mask(None, local, cloud) == (None, None)
    assert local.obs_mask is None and cloud.obs_mask is None
    record, mask = attach_obs_mask(1024, local, cloud)
    assert record["arm"] == "OBS_MASK" and record["k"] == 1024
    assert local.obs_mask is mask and cloud.obs_mask is mask
    with pytest.raises(SystemExit, match="local-script"):
        attach_obs_mask(8, ScriptedLiveLocalBackend(script={}), cloud)


def test_cli_default_off() -> None:
    args = build_argparser().parse_args(["--policy", "slo_escalate"])
    assert args.obs_mask_k is None
    args = build_argparser().parse_args(["--policy", "slo_escalate", "--obs-mask-k", "1024"])
    assert args.obs_mask_k == 1024


def test_plan_records_retention_and_ledger_file(tmp_path: Path) -> None:
    entry = {"id": "e0", "question": [[]], "n_user_turns": 1}
    row = {
        "n_ctx": 100,
        "ttft_s": 0.5,
        "decode_tok_s": 30.0,
        "emitted_parseable_tool_call": True,
        "turn_wall_s": 0.05,
        "t_generate": 0.03,
        "t_tokenize": 0.005,
        "t_template_build": 0.005,
        "t_tool_exec": 0.005,
    }
    for name, retention in (("full", None), ("mask", ObservationMask(64).plan_record())):
        out = tmp_path / name
        run_interleaved_session(
            entries=[entry],
            out_dir=out,
            local=StubLocalBackend(script={"e0": [row]}),
            cloud=StubCloudBackend(tokens_in=1, tokens_out=1),
            policies=("local_only",),
            policy_caps_usd={"local_only": 1.0},
            session_max_usd=1.0,
            run_id=name,
            skip_entry_assert=True,
            seal=False,
            retention=retention,
        )
        plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
        assert plan["retention"] == (retention or {"arm": "FULL"})
    mask = ObservationMask(2)
    mask.apply(["f()"], ["a b c"], source="local", entry_id="e0", turn=0)
    write_obs_mask_ledger(tmp_path, mask)
    doc = json.loads((tmp_path / "obs_mask_ledger.json").read_text(encoding="utf-8"))
    assert doc["observations"][0]["original_ws_tokens"] == 3
    write_obs_mask_ledger(tmp_path / "none", None)
    assert not (tmp_path / "none").exists()


def test_launcher_passes_obs_mask_k() -> None:
    text = LAUNCH_H1.read_text(encoding="ascii")
    assert "[Nullable[int]]$ObsMaskK = $null" in text
    assert "' --obs-mask-k ' + $ObsMaskK" in text


# ---------------------------------------------------------------- live vs sizing on gold


def _tokenizer_dir() -> Path:
    raw = os.environ.get("SEAM_QWEN_TOKENIZER")
    if not raw or not (Path(raw) / "tokenizer.json").is_file():
        pytest.skip("set SEAM_QWEN_TOKENIZER to a Qwen3-4B tokenizer dir")
    return Path(raw)


@pytest.mark.parametrize("residency", ["NON_RESIDENT", "RESIDENT"])
@pytest.mark.parametrize("k", [None, 1024])
def test_live_arm_matches_sizing_on_gold(residency: str, k: int | None) -> None:
    pytest.importorskip("bfcl_eval")
    transformers = pytest.importorskip("transformers")
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(_tokenizer_dir()))

    import tools.bfcl_feasibility_probe as probe
    import tools.h1_context_sizing as sizing
    from tools.h1_obs_mask import hf_token_count
    from tools.run_h1_hybrid import OpenVinoLocalBackend, _stubbed_generate_fakes

    data = sizing.bfcl_data_dir(None)
    probe.BFCL_DATA = data
    probe.BFCL_ANSWERS = data / "possible_answer"
    entries = json.loads((PIN_DIR / "DEMO1_LONGCTX_OBSK1024_15.json").read_text(encoding="utf-8"))
    entries = entries[:3]

    pipe, ov_genai, cfg = _stubbed_generate_fakes(tokenizer)
    queue: list[str] = []

    def generate(prompt: Any, cfg: Any = None, streamer: Any = None) -> Any:
        del prompt, cfg
        if streamer is not None:
            streamer.write(1)
            streamer.end()
        text = queue.pop(0) if queue else sizing.CLOSING_TEXT
        return types.SimpleNamespace(texts=[text], perf_metrics=None)

    pipe.generate = generate
    mask = None if k is None else ObservationMask(k, token_count=hf_token_count(tokenizer))
    local = OpenVinoLocalBackend.for_stubbed_generate(
        pipe=pipe,
        tokenizer=tokenizer,
        cfg=cfg,
        residency=residency,
        ov_genai=ov_genai,
        obs_mask=mask,
    )
    sys.modules.setdefault("openvino_genai", types.ModuleType("openvino_genai"))
    for entry in entries:
        expected = [t["n_ctx"] for t in sizing.size_entry(entry, tokenizer, obs_mask_k=k)["turns"]]
        local.begin_entry(entry, policy="slo_escalate")
        got = []
        for turn_idx, gold in enumerate(entry["reference"]):
            calls = [str(c) for c in gold]
            queue[:] = (
                [probe.encode_execute_calls_as_qwen_tool_text(calls), sizing.CLOSING_TEXT]
                if calls
                else [sizing.CLOSING_TEXT]
            )
            got.append(local.run_turn(entry, turn_idx, model="m").n_ctx)
        local.finish_entry(entry)
        assert got == expected, (entry["id"], got, expected)
    if mask is not None:
        assert any(r["truncated"] for r in mask.records)
        assert all("original_tokens" in r and "kept_tokens" in r for r in mask.records)
