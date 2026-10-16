"""seam/genai_runtime.py: GenAI load-log parsing, rt_info check, verdict, capture."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seam import genai_runtime as gr  # noqa: E402

PA_LOG = """\
some loader line
Model: LLM with Paged Attention
  NETWORK_NAME: Model0
  KV_CACHE_PRECISION: i8
  KEY_CACHE_QUANT_MODE: BY_CHANNEL
  VALUE_CACHE_QUANT_MODE: BY_TOKEN
  INFERENCE_PRECISION_HINT: f16
EXECUTION_DEVICES:
 GPU: Intel(R) Graphics
"""

FALLBACK_LOG = (
    "[WARNING] Paged Attention backend initialization failed. Falling back to SDPA "
    'backend. Set ATTENTION_BACKEND="SDPA" to skip Paged Attention initialization.\n'
)


def test_pa_dump_parsed() -> None:
    p = gr.parse_genai_load_log(PA_LOG)
    assert p["backend"] == "PA"
    assert p["kv_cache_precision"] == "i8"
    assert p["key_cache_quant_mode"] == "BY_CHANNEL"
    assert p["value_cache_quant_mode"] == "BY_TOKEN"
    assert not p["sdpa_fallback_warning"]


def test_fallback_wins_over_dump() -> None:
    p = gr.parse_genai_load_log(FALLBACK_LOG + PA_LOG)
    assert p["backend"] == "SDPA"
    assert p["sdpa_fallback_warning"]


def test_empty_capture_is_unknown_and_invalid(tmp_path: Path) -> None:
    p = gr.parse_genai_load_log("")
    assert p["backend"] == "unknown"
    xml = tmp_path / "m.xml"
    xml.write_text("<net><rt_info></rt_info></net>", encoding="utf-8")
    v = gr.true_default_verdict(p, gr.rt_info_kv_override(xml))
    assert not v["valid"]


def test_normalize_kv_aliases() -> None:
    assert gr.normalize_kv("int8_t") == "i8"
    assert gr.normalize_kv("<Type: 'uint8_t'>") == "u8"
    assert gr.normalize_kv("U4") == "u4"
    assert gr.normalize_kv(None) is None


def test_rt_info_override_detected(tmp_path: Path) -> None:
    xml = tmp_path / "openvino_model.xml"
    xml.write_text(
        "<net><rt_info><runtime_options>\n"
        '<KV_CACHE_GROUP_SIZE value="64" />\n<KV_CACHE_PRECISION value="u8" />\n'
        "</runtime_options></rt_info></net>",
        encoding="utf-8",
    )
    rt = gr.rt_info_kv_override(xml)
    assert rt["override"] and rt["kv_cache_precision"] == "u8"
    v = gr.true_default_verdict(gr.parse_genai_load_log(PA_LOG), rt)
    assert not v["valid"]
    assert any("rt_info" in r for r in v["reasons"])


def test_true_default_valid(tmp_path: Path) -> None:
    xml = tmp_path / "openvino_model.xml"
    xml.write_text("<net><rt_info><runtime_options>\n</runtime_options></rt_info></net>")
    v = gr.true_default_verdict(gr.parse_genai_load_log(PA_LOG), gr.rt_info_kv_override(xml))
    assert v == {"valid": True, "reasons": []}


def test_u8_compiled_is_invalid_for_arm_a(tmp_path: Path) -> None:
    xml = tmp_path / "openvino_model.xml"
    xml.write_text("<net/>")
    v = gr.true_default_verdict(
        gr.parse_genai_load_log(PA_LOG.replace("i8", "u4")), gr.rt_info_kv_override(xml)
    )
    assert not v["valid"]


def test_capture_native_output_and_env_restored() -> None:
    before = os.environ.get(gr.LOG_LEVEL_ENV)
    with gr.capture_native_output() as box:
        assert os.environ[gr.LOG_LEVEL_ENV] == gr.READBACK_LOG_LEVEL
        os.write(1, b"Model: LLM with Paged Attention\n  KV_CACHE_PRECISION: i8\n")
    assert "KV_CACHE_PRECISION: i8" in box["text"]
    assert os.environ.get(gr.LOG_LEVEL_ENV) == before


def test_module_is_ascii() -> None:
    (ROOT / "seam" / "genai_runtime.py").read_bytes().decode("ascii")
