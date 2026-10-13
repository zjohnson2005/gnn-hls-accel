"""DEMO-1 V5-CAL: warm points at D 8,500, the V5 path, the boot plan.

Hardware-free: the child runs on fake ov_genai objects, the session on
monkeypatched harness pieces, the launcher is read as text.
"""

from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import seam.tools._delta_n_child as child  # noqa: E402
import tools.boot4_session as b4  # noqa: E402
import tools.v5_cal_plan as plan  # noqa: E402

BOOT = ROOT / "tools" / "launch_boot1.ps1"
WRAPPER = ROOT / "tools" / "launch_v5_cal.ps1"


# ---------------------------------------------------------------- plan


def _v5_block() -> str:
    text = BOOT.read_text(encoding="utf-8")
    block = text[text.index('} elseif ($Profile -eq "v5-cal") {') :]
    return block[: block.index('} elseif ($Profile -eq "resident-limit") {')]


def test_plan_estimates_match_the_launcher_and_fit_one_boot() -> None:
    block = _v5_block()
    found = dict(re.findall(r'Name = "([^"]+)"; Kind = "warm"; EstimateS = (\d+)', block))
    doc = plan.plan()
    assert {c["name"]: c["estimate_s"] for c in doc["cells"]} == {
        k: int(v) for k, v in found.items()
    }
    assert doc["sum_estimate_s"] == 2933 <= plan.BOOT_CAP_S
    assert '$v5Points = "2200,3320,4080,6290,7380"' in block
    assert block.count("DeltaTokens = 8500") == 3
    assert 'NCached = "4080"; DeltaTokens = 8500; Turn2Path = "assistant_then_user"' in block


def test_every_v5_jump_step_is_covered() -> None:
    cov = plan.coverage()
    assert cov["u8"]["uncovered"] == [] and cov["u4"]["uncovered"] == []
    assert cov["u8"]["n_points"] == 6 and cov["u4"]["n_points"] == 5


# ---------------------------------------------------------------- child


class _Hist:
    def __init__(self) -> None:
        self.msgs: list[dict[str, str]] = []

    def set_extra_context(self, _ctx: dict) -> None:
        pass

    def append(self, msg: dict) -> None:
        self.msgs.append(dict(msg))

    def get_messages(self) -> list[dict]:
        return [dict(m) for m in self.msgs]

    def set_messages(self, msgs: list[dict]) -> None:
        self.msgs = [dict(m) for m in msgs]


class _Arr:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids

    def flatten(self) -> _Arr:
        return self

    def tolist(self) -> list[int]:
        return list(self.ids)


class _Tok:
    """Renders like the Qwen3 template: the generation prompt ends with the
    empty think block, which is not rendered for an earlier assistant turn."""

    def apply_chat_template(self, history: _Hist, add_gen: bool) -> str:
        parts = []
        for m in history.msgs:
            parts.append(f"<{m['role']}>{m['content']}</{m['role']}>")
        if add_gen:
            parts.append("<assistant><think></think>")
        return "".join(parts)

    def encode(self, text: str) -> Any:
        pieces = re.findall(r"<[^>]+>|[^<]", text)
        return types.SimpleNamespace(
            input_ids=types.SimpleNamespace(data=_Arr([hash(p) % 997 for p in pieces]))
        )


class _Pipe:
    def __init__(self) -> None:
        self.histories: list[list[dict]] = []

    def get_tokenizer(self) -> _Tok:
        return _Tok()

    def generate(self, history: _Hist, cfg: Any, streamer: Any) -> Any:
        self.histories.append(history.get_messages())
        streamer.write(1)
        return types.SimpleNamespace(texts=["R"], perf_metrics=None)


class _Writer:
    def __init__(self) -> None:
        self.fields: dict = {}

    def update(self, **kw: Any) -> None:
        self.fields.update(kw)


def _ov() -> Any:
    class Base:
        def __init__(self) -> None:
            pass

    return types.SimpleNamespace(
        ChatHistory=_Hist,
        GenerationConfig=lambda: types.SimpleNamespace(),
        StreamerBase=Base,
        StreamingStatus=types.SimpleNamespace(RUNNING=0),
    )


@pytest.fixture
def fake_text(monkeypatch):
    import seam.tools.boot4_text as bt

    monkeypatch.setattr(bt, "user_content_for_rendered_tokens", lambda _t, n, **_kw: "U" * n)
    monkeypatch.setattr(bt, "raw_exact_text", lambda _t, n, **kw: kw["salt"] + "d" * n)


def _run(path: str | None, record: bool) -> tuple[_Writer, _Pipe]:
    spec: dict[str, Any] = {
        "filler_unit": "x",
        "n_cached": 10,
        "delta_tokens": 5,
        "turn2_repeats": 2,
    }
    if path is not None:
        spec["turn2_path"] = path
    if record:
        spec["record_prefix"] = True
    writer, pipe = _Writer(), _Pipe()
    assert child._resident_two_turn(spec, writer, pipe, _ov()) == 0
    return writer, pipe


def test_default_path_is_the_warm_kv_shape(fake_text) -> None:
    writer, pipe = _run(None, False)
    gen = writer.fields["generation"]
    assert gen["turn2_path"] == "user_followup"
    assert [m["role"] for m in pipe.histories[1]] == ["user", "user"]
    assert "common_prefix_tokens" not in gen["turn2"][0]


def test_v5_path_puts_the_reply_in_history_and_records_the_prefix(fake_text) -> None:
    writer, pipe = _run("assistant_then_user", True)
    gen = writer.fields["generation"]
    assert gen["turn2_path"] == "assistant_then_user"
    assert [m["role"] for m in pipe.histories[1]] == ["user", "assistant", "user"]
    assert pipe.histories[1][1]["content"] == "R"
    rec = gen["turn2"][0]
    # The empty think block (<think>, </think>) of the turn-1 generation prompt
    # is not part of turn 2: the common prefix stops 2 pieces before turn 1 ends.
    assert rec["turn1_rendered_tokens"] - rec["common_prefix_tokens"] == 2
    assert (
        rec["measured_delta_tokens"] == rec["turn2_rendered_tokens"] - rec["common_prefix_tokens"]
    )


def test_followup_path_with_prefix_record(fake_text) -> None:
    writer, _pipe = _run("user_followup", True)
    rec = writer.fields["generation"]["turn2"][1]
    # user_followup breaks at the generation prompt itself (3 pieces here).
    assert rec["turn1_rendered_tokens"] - rec["common_prefix_tokens"] == 3


def test_unknown_path_is_refused(fake_text) -> None:
    with pytest.raises(RuntimeError, match="turn2_path"):
        _run("system_then_user", False)


def test_common_prefix_len() -> None:
    assert child.common_prefix_len([1, 2, 3], [1, 2, 4, 5]) == 2
    assert child.common_prefix_len([1, 2], [1, 2, 3]) == 2


# ---------------------------------------------------------------- session


def _session(monkeypatch, tmp_path: Path, **kwargs: Any) -> dict:
    captured: dict = {}
    monkeypatch.setattr(b4, "require_gates", lambda: {})
    monkeypatch.setattr(
        b4,
        "load_harness",
        lambda _spec: {
            "cfg": {},
            "p_cpus": [],
            "model_spec": Path("m.yaml"),
            "model_name": "Qwen3-4B-int4-ov",
        },
    )
    monkeypatch.setattr(b4, "_child_spec", lambda *_a: {})
    monkeypatch.setattr(b4, "_canary_model", lambda *_a: Path("m.yaml"))
    monkeypatch.setattr(b4, "_publish_cell_status", lambda *_a, **_k: None)
    monkeypatch.setattr(b4, "_point_failure", lambda *_a: {})

    class Guard:
        canaries: list = []

        def plan_fragment(self) -> dict:
            return {}

        def opening(self) -> None:
            pass

        def after_probe(self, log: list) -> None:
            pass

    def open_canary(**kw: Any) -> Guard:
        captured["planned"] = kw["planned"]
        return Guard()

    monkeypatch.setattr(b4, "_open_canary", open_canary)
    specs: list = []

    def measured_repeat(**kw: Any) -> dict:
        specs.append(dict(kw["child_spec"]))
        turn2 = [
            {
                "prefill_s": 1.0,
                "prompt_tokens_reported": 9,
                "common_prefix_tokens": 7,
                "measured_delta_tokens": 2,
            }
            for _ in range(b4.TURN2_REPEATS)
        ]
        return {
            "result": {"outcome": "pass", "child": {"generation": {"turn1": {}, "turn2": turn2}}}
        }

    import seam.tools.delta_n as dn

    monkeypatch.setattr(dn, "measured_repeat", measured_repeat)

    def finish(**kw: Any) -> int:
        captured["summary"] = kw["summary"]
        captured["plan"] = kw["plan"]
        return 0

    monkeypatch.setattr(b4, "_finish", finish)
    monkeypatch.setattr(b4, "_warm_advantages", lambda *_a: "ADV")
    assert (
        b4.run_warm(
            arm="gpu_only_u8", model_spec=Path("m.yaml"), session_id="s", out_dir=tmp_path, **kwargs
        )
        == 0
    )
    captured["specs"] = specs
    return captured


def test_session_defaults_are_the_sealed_warm_kv(monkeypatch, tmp_path) -> None:
    got = _session(monkeypatch, tmp_path)
    assert got["summary"]["kind"] == "warm_kv"
    assert got["summary"]["n_cached"] == list(b4.N_CACHED)
    assert got["summary"]["delta_tokens"] == b4.DELTA_TOKENS == 183
    assert got["summary"]["f16_advantage_percent"] == "ADV"
    assert got["planned"] == b4.WARM_PLANNED_PROBES
    assert all("turn2_path" not in s and "record_prefix" not in s for s in got["specs"])


def test_session_v5_cal_overrides(monkeypatch, tmp_path) -> None:
    got = _session(
        monkeypatch,
        tmp_path,
        n_cached=plan.N_CACHED,
        delta_tokens=8500,
        turn2_path="user_followup",
        record_prefix=True,
    )
    summary = got["summary"]
    assert summary["kind"] == got["plan"]["kind"] == "warm_kv_v5cal"
    assert summary["n_cached"] == list(plan.N_CACHED) and summary["delta_tokens"] == 8500
    assert summary["f16_advantage_percent"] is None
    assert got["planned"] == 5
    assert [s["n_cached"] for s in got["specs"]] == list(plan.N_CACHED)
    assert all(s["delta_tokens"] == 8500 and s["record_prefix"] is True for s in got["specs"])
    point = json.loads((tmp_path / "points" / "n2200.json").read_text(encoding="utf-8"))
    assert point["common_prefix_tokens"] == [7, 7, 7] and point["measured_delta_tokens"] == [
        2,
        2,
        2,
    ]


def test_runner_cli(monkeypatch) -> None:
    import tools.run_warm_kv as rk

    seen: dict = {}
    monkeypatch.setattr(rk, "run_warm", lambda **kw: seen.update(kw) or 0)
    assert (
        rk.main(
            [
                "--arm",
                "gpu_only_u4",
                "--model-spec",
                "m.yaml",
                "--session-id",
                "s",
                "--n-cached",
                "2200,3320",
                "--delta-tokens",
                "8500",
                "--turn2-path",
                "assistant_then_user",
                "--record-prefix",
            ]
        )
        == 0
    )
    assert seen["n_cached"] == (2200, 3320) and seen["delta_tokens"] == 8500
    assert seen["turn2_path"] == "assistant_then_user" and seen["record_prefix"] is True
    seen.clear()
    assert rk.main(["--arm", "gpu_only_u8", "--model-spec", "m.yaml", "--session-id", "s"]) == 0
    assert seen["n_cached"] == b4.N_CACHED and seen["delta_tokens"] is None
    assert seen["turn2_path"] == "user_followup" and seen["record_prefix"] is False


# ---------------------------------------------------------------- launcher


def test_launcher_profile_and_wrapper() -> None:
    text = BOOT.read_text(encoding="utf-8")
    assert '"npu-1", "v5-cal")]' in text
    assert '"v5-cal" { "V5CAL_SUMMARY.json" }' in text
    assert 'if ($Profile -ne "boot4" -and $Profile -ne "v5-cal") { return }' in text
    assert '$args += @("--n-cached", [string]$nCached)' in text
    assert (
        'if (Get-BootCellField -Cell $Cell -Name "RecordPrefix") { $args += "--record-prefix" }'
        in text
    )
    assert '$smokeArgs += @("--turn2-path"' in text
    wrapper = WRAPPER.read_text(encoding="utf-8")
    assert '"-Profile", "v5-cal"' in wrapper
    for path in (
        BOOT,
        WRAPPER,
        ROOT / "tools" / "run_warm_kv.py",
        ROOT / "tools" / "boot4_session.py",
    ):
        body = path.read_text(encoding="utf-8")
        assert "DEMO1_V5CAL_PREREG" not in body and "DEMO1_AMEND" not in body
