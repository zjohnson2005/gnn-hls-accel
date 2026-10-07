"""NPU-MAXLEN-DIAG rule v2 instrument check, off the NPU (CPU).

Runs only when openvino_genai imports and SEAM_TINY_IR names a small
OpenVINO GenAI IR directory (for example OpenVINO/Qwen3-0.6B-int4-ov).
Otherwise skipped. Checks the call form the diagnostic depends on:
generate(str) returns str with no perf_metrics; generate([str]) returns
DecodedResults whose perf_metrics reports the input-token count.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ov_genai = pytest.importorskip("openvino_genai")
IR = os.environ.get("SEAM_TINY_IR")
pytestmark = pytest.mark.skipif(not IR, reason="SEAM_TINY_IR not set")


def _cfg(apply_chat_template: bool):
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = 8
    cfg.do_sample = False
    cfg.apply_chat_template = apply_chat_template
    return cfg


def test_list_form_reports_input_tokens_and_str_form_does_not() -> None:
    from seam.tools.boot4_text import id_count, render_user
    from tools.npu_maxlen_diag import generate_direct

    pipe = ov_genai.LLMPipeline(str(IR), "CPU")
    tok = ov_genai.Tokenizer(str(IR))
    rendered = render_user(tok, "hello there, count to five")
    realized = id_count(tok, rendered)

    as_str = pipe.generate(rendered, _cfg(True))
    assert isinstance(as_str, str)
    assert getattr(as_str, "perf_metrics", None) is None

    raw = pipe.generate([rendered], _cfg(False))
    assert int(raw.perf_metrics.get_num_input_tokens()) == realized

    wrapped = pipe.generate([rendered], _cfg(True))
    assert int(wrapped.perf_metrics.get_num_input_tokens()) > realized

    row = generate_direct(ov_genai, pipe, rendered)
    assert row["result_type"] == "DecodedResults"
    assert row["pipeline_input_tokens"] == int(wrapped.perf_metrics.get_num_input_tokens())
    assert row["generation_config"]["do_sample"] is False
    assert row["streamer_tokens"] >= 1
    print(
        f"realized={realized} raw={raw.perf_metrics.get_num_input_tokens()} row={row['pipeline_input_tokens']}"
    )
