"""DEMO-2 runtime-default readback (read-only; prints JSON; writes nothing).

Loads the 4B int4 IR on GPU with NO properties passed (the DEMO-2 control's
"runtime default"), then prints:
- openvino / openvino_genai versions and the GPU device name;
- KV_CACHE_PRECISION (and KEY_/VALUE_CACHE_PRECISION when supported) read
  from the GPU device before and after the load (seam.ov_kv_precision);
- the default openvino_genai.SchedulerConfig().enable_prefix_caching;
- a behavioral hint: the same ~2,000-token prompt generated twice
  (max_new_tokens 1); a much smaller second TTFT suggests the prefix was
  reused. This is an indication for the prereg, not a measurement.

  .venv-seam\\Scripts\\python.exe tools\\demo2_readback.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
PROPS = ("KV_CACHE_PRECISION", "KEY_CACHE_PRECISION", "VALUE_CACHE_PRECISION")
FILLER = "The quick brown fox jumps over the lazy dog. "
TARGET_TOKENS = 2000


def device_props(core: Any, device: str = "GPU") -> dict[str, Any]:
    try:
        supported = {str(p) for p in core.get_property(device, "SUPPORTED_PROPERTIES")}
    except Exception as exc:  # recorded, not raised
        supported = set()
        out: dict[str, Any] = {"supported_error": f"{type(exc).__name__}: {exc}"}
    else:
        out = {}
    for name in PROPS:
        if supported and name not in supported:
            out[name] = "not supported"
            continue
        try:
            out[name] = str(core.get_property(device, name))
        except Exception as exc:
            out[name] = f"error: {type(exc).__name__}: {exc}"
    return out


def _ttft_s(pipe: Any, prompt: str, ov_genai: Any) -> dict[str, Any]:
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = 1
    t0 = time.perf_counter()
    result = pipe.generate(prompt, cfg)
    wall = time.perf_counter() - t0
    ttft = None
    metrics = getattr(result, "perf_metrics", None)
    if metrics is not None:
        try:
            ttft = float(metrics.get_ttft().mean) / 1000.0
        except Exception:
            ttft = None
    return {"ttft_s": ttft, "wall_s": wall}


def readback(ov: Any, ov_genai: Any, ir_dir: Path) -> dict[str, Any]:
    core = ov.Core()
    doc: dict[str, Any] = {
        "kind": "demo2_readback",
        "openvino": str(getattr(ov, "__version__", None) or ov.get_version()),
        "openvino_genai": str(getattr(ov_genai, "__version__", "unknown")),
        "ir_dir": str(ir_dir),
        "properties_passed": {},
    }
    try:
        doc["gpu"] = str(core.get_property("GPU", "FULL_DEVICE_NAME"))
    except Exception as exc:
        doc["gpu"] = f"error: {type(exc).__name__}: {exc}"
    doc["device_before_load"] = device_props(core)
    pipe = ov_genai.LLMPipeline(str(ir_dir), "GPU")
    doc["device_after_load"] = device_props(core)
    try:
        doc["scheduler_config_default_enable_prefix_caching"] = bool(
            ov_genai.SchedulerConfig().enable_prefix_caching
        )
    except Exception as exc:
        doc["scheduler_config_default_enable_prefix_caching"] = f"error: {type(exc).__name__}"
    tok = pipe.get_tokenizer()
    reps = 1
    while True:
        prompt = FILLER * reps
        n = int(tok.encode(prompt).input_ids.shape[-1])
        if n >= TARGET_TOKENS:
            break
        reps = max(reps + 1, int(reps * TARGET_TOKENS / max(n, 1)))
    first = _ttft_s(pipe, prompt, ov_genai)
    second = _ttft_s(pipe, prompt, ov_genai)
    ratio = None
    if first["ttft_s"] and second["ttft_s"]:
        ratio = round(second["ttft_s"] / first["ttft_s"], 3)
    doc["prefix_reuse_hint"] = {
        "prompt_tokens": n,
        "first": first,
        "second": second,
        "second_over_first_ttft": ratio,
        "note": "indication only; < 0.5 suggests the prefix was reused between generate calls",
    }
    return doc


def main() -> int:
    import openvino as ov
    import openvino_genai as ov_genai

    from seam.model_provenance import load_local_spec

    spec = load_local_spec(SPEC)
    ir_dir = Path(spec["ir_dir"])
    if not ir_dir.is_absolute():
        ir_dir = ROOT / ir_dir
    print(json.dumps(readback(ov, ov_genai, ir_dir), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
