"""NPU-INT8 content prompt length (task Y).

The 1e79daa3 content check failed with "overshot while padding to 960:
reached 961": on Qwen3 the filler's final "." and the "\\n\\n" separator are
one token, so padding before the suffix split it. The fake tokenizer below
has the same merge. The pinned-tokenizer test runs when
SEAM_QWEN3_TOKENIZER_DIR points at the OpenVINO/Qwen3-4B-int4-ov b467368d
tokenizer files and transformers is installed.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import seam.tools.boot4_text as bt  # noqa: E402
import tools.run_npu_profile as rnp  # noqa: E402
from seam.errors import SeamError  # noqa: E402

UNIT = " the quick brown fox jumps over the lazy dog."
CHECK = ROOT / "analysis" / "npu" / "NPU_CONTENT_PROMPT_CHECK_20261013.json"
_TOKEN = re.compile(r"\.\n\n|\n\n|\.| ?[^\s.]+")


def _render(_tok: Any, text: str) -> str:
    return f"<u>{text}</u>"


def _count(_tok: Any, text: str) -> int:
    return len(_TOKEN.findall(text))


def _fake(monkeypatch) -> None:
    monkeypatch.setattr(rnp, "render_user", _render)
    monkeypatch.setattr(rnp, "id_count", _count)


def test_fake_tokenizer_has_the_qwen3_merge() -> None:
    assert _count(None, "dog.\n\nWhat") == 3
    assert _count(None, "dog. a\n\nWhat") == 5


def test_old_padding_overshoots_on_the_merge() -> None:
    suffix = rnp.CONTENT_SEPARATOR + rnp.CONTENT_QUESTION
    with pytest.raises(SeamError, match="overshot"):
        bt._exact_body(
            lambda text: _count(None, _render(None, text + suffix)),
            960,
            prefix="npu ",
            unit=UNIT,
        )


@pytest.mark.parametrize("target", [64, 192, 960, 1984, 4032, 8128, 16320])
def test_content_prompt_is_exact_with_the_merge(monkeypatch, target: int) -> None:
    _fake(monkeypatch)
    prompt = rnp.content_prompt(None, target, unit=UNIT, salt="npu")
    assert _count(None, prompt) == target
    assert prompt.endswith(rnp.CONTENT_SEPARATOR + rnp.CONTENT_QUESTION + "</u>")
    assert prompt.startswith("<u>npu")


def test_unreachable_length_returns_the_nearest_below(monkeypatch) -> None:
    # Padding costs 2 tokens per step here, so odd gaps cannot be closed.
    monkeypatch.setattr(rnp, "render_user", _render)
    monkeypatch.setattr(rnp, "id_count", lambda _t, s: _count(None, s.replace(" a", " a b")))
    prompt = rnp.content_prompt(None, 961, unit=" w w", salt="npu")
    realized = _count(None, prompt.replace(" a", " a b"))
    assert realized == 960


def _gen(text: str) -> dict[str, Any]:
    return {"text": text, "pipeline_input_tokens": None}


def test_content_check_records_the_shortfall() -> None:
    record = rnp.run_content_check(
        limit=960,
        build=lambda _n: "P",
        npu_generate=lambda _p: {},
        gpu_generate=lambda _p: {},
        npu_stops=[],
        gpu_stops=[],
        decode=str,
        count=lambda _p: 959,
    )
    assert record["target_tokens"] == 960
    assert record["n_tokens"] == 959
    assert record["shortfall_tokens"] == 1
    exact = rnp.run_content_check(
        limit=960,
        build=lambda _n: "P",
        npu_generate=lambda _p: {},
        gpu_generate=lambda _p: {},
        npu_stops=[],
        gpu_stops=[],
        decode=str,
    )
    assert exact["shortfall_tokens"] == 0 and exact["n_tokens"] == 960


def test_limit_citable_requires_no_shortfall() -> None:
    src = (ROOT / "tools" / "run_npu_profile.py").read_text(encoding="utf-8")
    block = src[src.index('summary["limit_citable"] = bool(') :]
    block = block[: block.index("\n        )\n")]
    assert 'content.get("shortfall_tokens") == 0' in block
    assert 'content.get("outcome") == "CONTENT_OK"' in block


def test_recorded_pinned_tokenizer_check() -> None:
    doc = json.loads(CHECK.read_text(encoding="utf-8"))
    assert "b467368d" in doc["tokenizer"]
    assert doc["n_targets"] == doc["n_exact"] == doc["n_suffix_ok"] == 128
    assert doc["rung_prompts_exact_unchanged"] is True
    targets = {r["target"] for r in doc["rows"]}
    assert targets == set(range(64, 8129, 64)) | {16320}


@pytest.mark.skipif(
    not os.environ.get("SEAM_QWEN3_TOKENIZER_DIR"), reason="pinned tokenizer not available"
)
@pytest.mark.parametrize("target", [64, 960, 1984, 4032, 8128, 16320])
def test_content_prompt_is_exact_with_the_pinned_tokenizer(monkeypatch, target: int) -> None:
    transformers = pytest.importorskip("transformers")
    tok = transformers.AutoTokenizer.from_pretrained(os.environ["SEAM_QWEN3_TOKENIZER_DIR"])

    def render(_t: Any, content: str) -> str:
        return tok.apply_chat_template(
            [{"role": "user", "content": content}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    def count(_t: Any, text: str) -> int:
        return len(tok(text)["input_ids"])

    monkeypatch.setattr(rnp, "render_user", render)
    monkeypatch.setattr(rnp, "id_count", count)
    prompt = rnp.content_prompt(None, target, unit=rnp._filler(), salt="npu")
    assert count(None, prompt) == target
    assert rnp.CONTENT_SEPARATOR + rnp.CONTENT_QUESTION + "<|im_end|>" in prompt
