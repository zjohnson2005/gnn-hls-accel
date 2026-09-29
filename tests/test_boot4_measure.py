"""Boot-4 design numbers, the stub refusal, and exact-token text."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.tools.boot4_text import (  # noqa: E402
    decode_span_tok_s,
    raw_exact_text,
    rendered_exact_prompt,
)
from tools.boot4_session import (  # noqa: E402
    DELTA_TOKENS,
    N_CACHED,
    advantage_percent,
    runner_body_is_stub,
)

LEDGER = (
    ROOT
    / "derived"
    / "h1_hybrid"
    / "interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da"
    / "policies"
    / "slo_escalate"
    / "turn_ledger.json"
)
AMEND = ROOT / "derived" / "delta_prefill" / "WARM_KV_AMEND_1.json"


def test_advantage_percent_uses_the_other_median_as_the_base() -> None:
    assert advantage_percent(median_f16=8.0, median_other=10.0) == pytest.approx(20.0)


def test_decode_span_rate_is_63_over_the_token_gap() -> None:
    assert decode_span_tok_s(t_first_ns=1_000_000_000, t_last_ns=2_000_000_000) == pytest.approx(
        63.0
    )


def test_delta_matches_the_sealed_turn_ledger() -> None:
    doc = json.loads(LEDGER.read_text(encoding="utf-8"))
    increases: list[int] = []
    for entry in doc["entries"]:
        turns = sorted(entry["turns"], key=lambda item: int(item["turn"]))
        by_turn = {int(item["turn"]): int(item["n_ctx"]) for item in turns}
        for turn in sorted(by_turn):
            if turn < 1 or (turn - 1) not in by_turn:
                continue
            increase = by_turn[turn] - by_turn[turn - 1]
            if increase > 0:
                increases.append(increase)
    amend = json.loads(AMEND.read_text(encoding="utf-8"))
    assert len(increases) == 532
    assert statistics.median(increases) == 182.5
    assert amend["delta_median_n_ctx_increase"] == 182.5
    assert amend["n_turns"] == 532
    assert amend["delta_tokens"] == 183
    assert DELTA_TOKENS == 183
    assert N_CACHED == (12000, 24000, 46000)
    assert amend["prediction_unchanged"].startswith("f16 > u8 >= u4")


def test_real_runners_are_not_stubs_and_a_stub_file_is(tmp_path: Path) -> None:
    for rel in ("tools/run_warm_kv.py", "tools/run_decode_match.py"):
        assert runner_body_is_stub(ROOT / rel) is False
    stub = tmp_path / "stub.py"
    stub.write_text("raise SystemExit('measurement body is not started')\n", encoding="utf-8")
    assert runner_body_is_stub(stub) is True


def test_dry_run_refuses_a_stub_body(tmp_path: Path) -> None:
    stub = tmp_path / "stub_runner.py"
    stub.write_text("measurement body is not started\n", encoding="utf-8")
    env = os.environ.copy()
    env["SEAM_BOOT4_STUB_FIXTURE"] = str(stub)
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(ROOT / "tools" / "launch_boot4.ps1"),
            "-DryRun",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "stub measurement body" in combined


def test_exact_token_text_hits_the_target() -> None:
    model = ROOT / "models" / "Qwen3-4B-int4-ov"
    if not model.is_dir():
        pytest.skip("int4 tokenizer is not on this machine")
    import openvino_genai as ov_genai

    tokenizer = ov_genai.Tokenizer(str(model))
    unit = " the quick brown fox jumps over the lazy dog."
    rendered = rendered_exact_prompt(tokenizer, 32, unit=unit, salt="f")
    raw_a = raw_exact_text(tokenizer, 16, unit=unit, salt="d0")
    raw_b = raw_exact_text(tokenizer, 16, unit=unit, salt="d1")
    assert int(tokenizer.encode(rendered).input_ids.shape[-1]) == 32
    assert int(tokenizer.encode(raw_a).input_ids.shape[-1]) == 16
    assert int(tokenizer.encode(raw_b).input_ids.shape[-1]) == 16
    assert raw_a != raw_b
