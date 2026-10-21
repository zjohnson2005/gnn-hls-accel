"""Task BB (pilot P11-B): stall vs turn-budget watchdog, post-generate step lines,
local turn limit / ctx-overflow local fail, repro chain mode. All default off."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.step_log import StepLog  # noqa: E402
from seam.turn_watchdog import (  # noqa: E402
    HANG_EVENTS_NAME,
    OUTCOME_BUDGET,
    OUTCOME_HANG,
    OUTCOME_STALL,
    TurnWatchdog,
)
from tools import repro_hang123 as rp  # noqa: E402
from tools import run_h1_hybrid as rh  # noqa: E402

P11B = ROOT / "derived" / "repro_hang123" / "p11b"


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _wd(tmp_path: Path, clock: _Clock, **kw: Any) -> tuple[TurnWatchdog, list[int]]:
    exits: list[int] = []
    wd = TurnWatchdog(out_dir=tmp_path, exit_fn=exits.append, clock=clock, **kw)
    return wd, exits


def _events(tmp_path: Path) -> list[dict[str, Any]]:
    return list(json.loads((tmp_path / HANG_EVENTS_NAME).read_text())["events"])


def test_progress_keeps_a_long_turn_alive_until_the_budget(tmp_path: Path) -> None:
    clock = _Clock()
    wd, exits = _wd(tmp_path, clock, limit_s=3600, stall_s=300)
    wd.arm(entry_id="e123", policy="local_only", turn=0)
    for _ in range(17):  # one step every 200 s (3,400 s): never quiet for 300 s
        clock.t += 200
        wd.progress("step")
        assert wd.check() is None
    clock.t += 201
    wd.progress("token")
    rec = wd.check()
    assert rec is not None and rec["outcome"] == OUTCOME_BUDGET and exits == [86]
    assert rec["n_steps"] == 17 and rec["n_tokens"] == 1 and rec["phase"] == "decode"


def test_quiet_turn_is_a_stall_with_its_phase(tmp_path: Path) -> None:
    clock = _Clock()
    wd, exits = _wd(tmp_path, clock, limit_s=3600, stall_s=300)
    wd.arm(entry_id="e123", policy="local_only", turn=0)
    clock.t += 10
    wd.progress("step")  # a new step, no token yet: prefill
    clock.t += 301
    rec = wd.check()
    assert rec is not None and rec["outcome"] == OUTCOME_STALL and exits == [86]
    assert rec["phase"] == "prefill" and rec["since_progress_s"] == 301.0
    assert _events(tmp_path)[0]["outcome"] == OUTCOME_STALL


def test_stall_after_tokens_is_decode_phase(tmp_path: Path) -> None:
    clock = _Clock()
    wd, _ = _wd(tmp_path, clock, limit_s=None, stall_s=60)
    wd.arm(entry_id="e", policy="p", turn=0)
    wd.progress("step")
    wd.progress("token")
    clock.t += 61
    rec = wd.check()
    assert rec is not None and rec["phase"] == "decode" and rec["limit_s"] is None


def test_without_stall_the_outcome_stays_hang(tmp_path: Path) -> None:
    clock = _Clock()
    wd, _ = _wd(tmp_path, clock, limit_s=600)
    assert "stall_s" not in wd.config()
    wd.arm(entry_id="e", policy="p", turn=0)
    wd.progress("token")  # ignored for the decision without stall_s
    clock.t += 601
    rec = wd.check()
    assert rec is not None and rec["outcome"] == OUTCOME_HANG and "phase" not in rec


def test_watchdog_refusals(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="limit_s, stall_s or both"):
        TurnWatchdog(limit_s=None, out_dir=tmp_path)
    with pytest.raises(ValueError, match="stall watchdog limit must be positive"):
        TurnWatchdog(limit_s=600, stall_s=0, out_dir=tmp_path)


def test_post_generate_line_carries_raw_text_only_when_given(tmp_path: Path) -> None:
    err = io.StringIO()
    log = StepLog(path=tmp_path / "s.jsonl", entry_id="e", policy="p", stderr=err)
    common: dict[str, Any] = {
        "turn": 0,
        "step": 1,
        "prompt_tokens": 87392,
        "generated_tokens": 512,
        "wall_s": 400.1,
        "ttft_s": 341.0,
        "ok": True,
        "error": None,
    }
    log.post_generate(**common)
    log.post_generate(**common, raw_text="<tool_call>x</tool_call>")
    rows = [json.loads(x) for x in (tmp_path / "s.jsonl").read_text().splitlines()]
    assert [r["event"] for r in rows] == ["post_generate", "post_generate"]
    assert "raw_text" not in rows[0] and rows[1]["raw_text"] == "<tool_call>x</tool_call>"
    assert "raw_text_chars" in err.getvalue() and "<tool_call>" not in err.getvalue()


def test_runner_cli_stall_and_limits(tmp_path: Path) -> None:
    ap = rh.build_argparser()
    args = ap.parse_args(["--out", str(tmp_path)])
    assert args.stall_watchdog_s is None and args.local_turn_limit is None
    assert not args.ctx_overflow_local_fail
    args = ap.parse_args(
        ["--out", str(tmp_path), "--turn-watchdog-s", "3600", "--stall-watchdog-s", "900"]
    )
    wd = rh.build_turn_watchdog(args)
    assert wd.config()["stall_s"] == 900.0 and wd.config()["limit_outcome"] == OUTCOME_BUDGET
    with pytest.raises(SystemExit, match="interleaved only"):
        rh.main(["--out", str(tmp_path / "x"), "--allow-dirty", "--local-turn-limit", "1"])


def _ov_local() -> Any:
    return object.__new__(rh.OpenVinoLocalBackend)


def test_attach_local_limits_refusals_and_record(tmp_path: Path) -> None:
    ap = rh.build_argparser()
    off = ap.parse_args(["--out", str(tmp_path)])
    assert rh.attach_local_limits(off, ("local_only",), _ov_local()) is None
    a = ap.parse_args(["--out", str(tmp_path), "--local-turn-limit", "1"])
    with pytest.raises(SystemExit, match="local_only alone"):
        rh.attach_local_limits(a, ("slo_escalate",), _ov_local())
    with pytest.raises(SystemExit, match="need OpenVINO"):
        rh.attach_local_limits(a, ("local_only",), object())
    b = ap.parse_args(["--out", str(tmp_path), "--ctx-overflow-local-fail"])
    with pytest.raises(SystemExit, match="go together"):
        rh.attach_local_limits(b, ("local_only",), _ov_local())
    c = ap.parse_args(
        [
            "--out",
            str(tmp_path),
            "--ctx-overflow-local-fail",
            "--context-window",
            "40960",
            "--local-turn-limit",
            "1",
        ]
    )
    local = _ov_local()
    rec = rh.attach_local_limits(c, ("local_only",), local)
    assert rec is not None and rec["context_window"]["tokens"] == 40960
    assert local.context_window == 40960 and local.ctx_overflow_local_fail
    assert local.local_turn_limit == 1


class _Sess:
    def __init__(self, ovf: dict[str, Any] | None) -> None:
        self.force_quit = False
        self.ctx_overflow = ovf
        self.all_model_response = [["t"]]
        self.all_decoded = [[]]

    def run_user_turn(self, turn_idx: int) -> dict[str, Any]:
        return {
            "n_decoded_steps": 1,
            "prompt_tokens": 2189,
            "ttft_s": 1.0,
            "decode_tok_s": 20.0,
            "turn_wall_s": 2.0,
            "t_tool_exec": 0.0,
            "t_template_build": 0.0,
            "t_tokenize": 0.0,
            "t_generate": 2.0,
            "t_other": 0.0,
            "steps": [],
            "ctx_overflow": self.ctx_overflow,
        }


def _backend(sess: _Sess, **kw: Any) -> Any:
    b = _ov_local()
    b._active_cell = "e123\0local_only"
    b._span_state = {}
    b._sessions = {b._active_cell: sess}
    b.runtime = None
    b.local_turn_limit = kw.get("limit")
    b.ctx_overflow_local_fail = bool(kw.get("fail"))
    b._require_active_session = lambda _entry: sess
    return b


ENTRY = {"id": "e123", "question": [[], [], []]}


def test_span_ends_on_ctx_overflow_or_turn_limit() -> None:
    b = _backend(_Sess({"turn": 0, "n_ctx": 87392, "step": 1}), fail=True)
    # Later BackendTurn fields are not stubbed; the span is set before they are read.
    with contextlib.suppress(Exception):
        b.run_turn(ENTRY, 0, model="m")
    span = b.local_span(ENTRY)
    assert span.turns_executed == 1 and span.stop_reason == "ctx_overflow"
    b = _backend(_Sess(None), limit=1)
    with contextlib.suppress(Exception):
        b.run_turn(ENTRY, 0, model="m")
    span = b.local_span(ENTRY)
    assert span.turns_executed == 1 and span.stop_reason == "turn_limit"
    b = _backend(_Sess(None))
    with contextlib.suppress(Exception):
        b.run_turn(ENTRY, 0, model="m")
    assert b.local_span(ENTRY).stop_reason == "completed"


def _stub_genai(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    class Pipe:
        def __init__(self, *_a: object) -> None:
            pass

        def generate(self, prompt: str, _cfg: object, streamer: Any = None) -> str:
            calls.append(prompt)
            if streamer is not None:
                streamer.write(1)
            return f"out{len(calls)}"

    class Cfg:
        pass

    class StreamerBase:
        def __init__(self) -> None:
            pass

    ov = types.ModuleType("openvino")
    ov.__version__ = "stub"  # type: ignore[attr-defined]
    ga = types.ModuleType("openvino_genai")
    ga.LLMPipeline = Pipe  # type: ignore[attr-defined]
    ga.GenerationConfig = Cfg  # type: ignore[attr-defined]
    ga.StreamerBase = StreamerBase  # type: ignore[attr-defined]
    ga.StreamingStatus = types.SimpleNamespace(RUNNING=0)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openvino", ov)
    monkeypatch.setitem(sys.modules, "openvino_genai", ga)


def test_p11b_inputs_are_pinned_and_chain_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    idx = json.loads((P11B / "INDEX.json").read_text(encoding="utf-8"))
    import hashlib

    for name, row in idx["cells"].items():
        raw = (P11B / row["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["file_sha256"], name
        doc = json.loads(raw)
        assert rp.sha(doc["chain"]["suffix"]) == idx["chain"]["suffix_sha256"]
    assert idx["chain"]["suffix_tokens_hf"] == 55
    calls: list[str] = []
    _stub_genai(monkeypatch, calls)
    f = P11B / "X2_N32768.json"
    sh = hashlib.sha256(f.read_bytes()).hexdigest()
    rc = rp.run(
        f,
        tmp_path,
        None,
        sh,
        watchdog_s=1800,
        out_dir=tmp_path / "runs",
        label="x2",
        stall_s=900,
        chain_steps=4,
    )
    assert rc == 0 and len(calls) == 5
    suffix = json.loads(f.read_text())["chain"]["suffix"]
    assert calls[1] == calls[0] + "out1" + suffix and calls[4].endswith("out4" + suffix)
    (run_dir,) = list((tmp_path / "runs").iterdir())
    rec = json.loads((run_dir / "run.json").read_text())
    assert rec["status"] == "complete" and [s["output_text"] for s in rec["steps"]][-1] == "out5"


def test_chain_refuses_inputs_without_a_suffix(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="'chain' suffix"):
        rp._chain_prompts({"steps": [{"step": 0, "prompt": "x"}]}, None)
