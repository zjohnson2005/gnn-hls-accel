"""Task AZ: --step-log, one flushed line per local step before generate (default off)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam import genai_runtime as gr  # noqa: E402
from seam.step_log import STDERR_TAG, StepLog  # noqa: E402
from tools import run_h1_hybrid as rh  # noqa: E402


def _opts(**kw: Any) -> dict[str, Any] | None:
    base: dict[str, Any] = {"residency": "RESIDENT", "kv": "default", "placement": "gpu_only"}
    base.update(kw)
    return gr.build_runtime_options(**base)


def test_line_is_on_disk_before_generate_returns(tmp_path: Path) -> None:
    err = io.StringIO()
    log = StepLog(
        path=tmp_path / "step_log.jsonl", entry_id="e123", policy="local_only", stderr=err
    )

    def stalled_generate() -> None:
        # What a hang leaves behind: the line must already be readable here.
        rows = (tmp_path / "step_log.jsonl").read_text(encoding="utf-8").splitlines()
        assert json.loads(rows[-1])["step"] == 0
        raise TimeoutError("stalled")

    log.before_generate(
        turn=0, step=0, prompt_tokens=2189, generate_input_tokens=2189, input_kind="chat_history"
    )
    with pytest.raises(TimeoutError):
        stalled_generate()
    assert err.getvalue().startswith(STDERR_TAG + " ")


def test_new_tokens_estimate(tmp_path: Path) -> None:
    log = StepLog(path=tmp_path / "s.jsonl", entry_id="e", policy="p", stderr=io.StringIO())
    r0 = log.before_generate(
        turn=0, step=0, prompt_tokens=2189, generate_input_tokens=2189, input_kind="x"
    )
    assert r0["new_tokens_est"] == 2189 and r0["seen_tokens_before"] is None
    log.after_generate(prompt_tokens=2189, generated_tokens=196)
    r1 = log.before_generate(
        turn=0, step=1, prompt_tokens=34050, generate_input_tokens=34050, input_kind="x"
    )
    assert r1["new_tokens_est"] == 34050 - 2189 - 196
    log.after_generate(prompt_tokens=34050, generated_tokens=None)
    r2 = log.before_generate(
        turn=1, step=0, prompt_tokens=100, generate_input_tokens=100, input_kind="x"
    )
    assert r2["new_tokens_est"] == 0
    rows = [json.loads(x) for x in (tmp_path / "s.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["step"] for r in rows] == [0, 1, 0]


def test_runtime_option_default_off_and_absent() -> None:
    assert _opts() is None
    on = _opts(step_log=True)
    assert on is not None and on["step_log"] is True
    other = _opts(debug_raw_text=True)
    assert other is not None and "step_log" not in other


def test_argparse_flag_default_off() -> None:
    ap = rh.build_argparser()
    assert ap.parse_args([]).step_log is False
    assert ap.parse_args(["--step-log"]).step_log is True
    assert "step_log" in rh.RUNTIME_FLAG_KEYS


def test_hook_precedes_both_generate_calls() -> None:
    src = (ROOT / "tools" / "bfcl_feasibility_probe.py").read_text(encoding="utf-8")
    body = src[src.index("def run_user_turn") :]
    hook = body.index("self.step_log.before_generate(")
    assert hook < body.index("gen = pipe.generate([prompt_full], cfg)")
    assert hook < body.index("timed = _timed_generate(pipe, ov_genai, gen_input, cfg_use)")
    assert body.index("if self.step_log is not None:") < hook
    assert hook < body.index("self.step_log.after_generate(")


def test_launcher_and_ascii() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    assert "' --step-log'" in text and "[switch]$StepLog" in text
    (ROOT / "seam" / "step_log.py").read_bytes().decode("ascii")


def test_fixture_run_refuses_step_log(tmp_path: Path) -> None:
    fix = {
        "entries": [{"id": "e", "question": [[]], "n_user_turns": 1}],
        "local_script": {"e": [{"n_ctx": 100, "ttft_s": 0.1, "decode_tok_s": 30.0}]},
    }
    path = tmp_path / "fix.json"
    path.write_text(json.dumps(fix), encoding="utf-8")
    argv = ["--policy", "hybrid_full", "--fixture", str(path), "--out", str(tmp_path / "o")]
    argv += ["--max-usd", "1", "--allow-dirty", "--step-log"]
    with pytest.raises(SystemExit, match="OpenVINO local backend"):
        rh.main(argv)
