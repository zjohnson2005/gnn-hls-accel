"""What OpenVINO GenAI 2026.2.1 actually ran: backend, compiled KV type, overrides.

Source facts (read at the release tags, 2026-10-16; docs/literature/2026-10-16/
DEMO2_CONTROL/openvino_defaults.md):

- LLMPipeline(model, "GPU") with nothing passed tries PagedAttention (PA) with
  the latency-oriented scheduler config (prefix caching on, unlimited batch
  tokens). If PA setup throws it falls back to SDPA and logs one WARN line,
  FALLBACK_MARKER below.
- With OPENVINO_LOG_LEVEL above WARNING, GenAI prints the compiled model's
  properties under "Model: LLM with Paged Attention" (PA_MARKER). Its
  KV_CACHE_PRECISION line is the compiled type. The plugin property read
  before compile says "dynamic" either way.
- On 2026.2.1 a PA model with no KV property compiles i8 (auto u4 is off).
- The IR's rt_info runtime_options/KV_CACHE_PRECISION overrides the PA default.

Nothing here imports openvino; the parsers take plain text.
"""

from __future__ import annotations

import contextlib
import os
import re
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

LOG_LEVEL_ENV = "OPENVINO_LOG_LEVEL"
# ov::log::Level DEBUG = 3. GenAI prints compiled properties above WARNING (1).
READBACK_LOG_LEVEL = "3"
PA_MARKER = "Model: LLM with Paged Attention"
FALLBACK_MARKER = "Falling back to SDPA backend"
TRUE_DEFAULT_KV = "i8"

_KV_ALIASES = {
    "i8": "i8",
    "int8": "i8",
    "int8_t": "i8",
    "u8": "u8",
    "uint8": "u8",
    "uint8_t": "u8",
    "u4": "u4",
    "uint4": "u4",
    "i4": "i4",
    "f16": "f16",
    "float16": "f16",
    "f32": "f32",
    "float32": "f32",
    "dynamic": "dynamic",
}
_PROP_LINE = re.compile(r"^\s+([A-Z0-9_]+)\s*:\s*(.*?)\s*$")
_RUNTIME_OPTIONS = re.compile(r"<runtime_options>(.*?)</runtime_options>", re.S)
_KV_RT = re.compile(r"<KV_CACHE_PRECISION\s+value=\"([^\"]*)\"")


def normalize_kv(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().strip("'\"<>").lower()
    v = v.replace("type:", "").strip().strip("'\"")
    return _KV_ALIASES.get(v, v or None)


def parse_genai_load_log(text: str) -> dict[str, Any]:
    """Backend and compiled properties from GenAI's load output.

    backend: "PA" if the PA property dump is present and no fallback line;
    "SDPA" if the fallback line is present; "unknown" otherwise (for example
    the log level was not applied, or the output was not captured).
    """
    lines = (text or "").splitlines()
    fallback = any(FALLBACK_MARKER in ln for ln in lines)
    pa_props: dict[str, str] = {}
    in_pa = False
    seen_pa = False
    for ln in lines:
        if ln.startswith("Model: "):
            in_pa = ln.strip() == PA_MARKER
            seen_pa = seen_pa or in_pa
            continue
        if in_pa:
            m = _PROP_LINE.match(ln)
            if m:
                pa_props.setdefault(m.group(1), m.group(2))
            elif ln.strip() and not ln.startswith(" "):
                in_pa = False
    if fallback:
        backend = "SDPA"
    elif seen_pa:
        backend = "PA"
    else:
        backend = "unknown"
    return {
        "backend": backend,
        "sdpa_fallback_warning": fallback,
        "pa_property_dump_seen": seen_pa,
        "kv_cache_precision": normalize_kv(pa_props.get("KV_CACHE_PRECISION")),
        "key_cache_quant_mode": pa_props.get("KEY_CACHE_QUANT_MODE"),
        "value_cache_quant_mode": pa_props.get("VALUE_CACHE_QUANT_MODE"),
        "n_pa_properties": len(pa_props),
        "captured_chars": len(text or ""),
    }


def rt_info_kv_override(ir_xml: Path) -> dict[str, Any]:
    """runtime_options/KV_CACHE_PRECISION in the IR, which overrides the PA default."""
    try:
        text = Path(ir_xml).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"checked": False, "error": f"{type(exc).__name__}: {exc}"}
    block = _RUNTIME_OPTIONS.search(text)
    value = None
    if block:
        m = _KV_RT.search(block.group(1))
        value = m.group(1) if m else None
    return {
        "checked": True,
        "runtime_options_present": block is not None,
        "kv_cache_precision": value,
        "override": value is not None,
    }


def true_default_verdict(parsed: dict[str, Any], rt_info: dict[str, Any] | None) -> dict[str, Any]:
    """DEMO-2 arm A / pilot P0: valid only if PA ran, no fallback, compiled i8, no override."""
    reasons: list[str] = []
    if parsed.get("sdpa_fallback_warning"):
        reasons.append("SDPA fallback warning present")
    if parsed.get("backend") != "PA":
        reasons.append(f"backend {parsed.get('backend')!r}, not PA")
    kv = parsed.get("kv_cache_precision")
    if kv != TRUE_DEFAULT_KV:
        reasons.append(f"compiled KV {kv!r}, not {TRUE_DEFAULT_KV!r}")
    if rt_info is None or not rt_info.get("checked"):
        reasons.append("IR rt_info not checked")
    elif rt_info.get("override"):
        reasons.append(f"IR rt_info sets KV_CACHE_PRECISION={rt_info.get('kv_cache_precision')!r}")
    return {"valid": not reasons, "reasons": reasons}


def _flush_c_stdio() -> None:
    with contextlib.suppress(Exception):
        import ctypes
        import ctypes.util

        name = "msvcrt" if sys.platform == "win32" else ctypes.util.find_library("c")
        if name:
            ctypes.CDLL(name).fflush(None)


@contextlib.contextmanager
def capture_native_output(log_level: str | None = READBACK_LOG_LEVEL) -> Iterator[dict[str, Any]]:
    """Capture fd 1 and 2 (native C++ output included) while the block runs.

    Sets OPENVINO_LOG_LEVEL for the block only and restores it after, so later
    generate calls are not logged at debug level. The captured text is echoed
    back to the real stderr afterwards and returned in box["text"]. If the
    platform routes native output elsewhere the text is empty, and
    parse_genai_load_log reports backend "unknown" (callers fail closed).
    """
    box: dict[str, Any] = {"text": "", "log_level": log_level}
    prev_level = os.environ.get(LOG_LEVEL_ENV)
    if log_level is not None:
        os.environ[LOG_LEVEL_ENV] = log_level
    sys.stdout.flush()
    sys.stderr.flush()
    with tempfile.TemporaryFile(mode="w+b") as tmp:
        saved = (os.dup(1), os.dup(2))
        os.dup2(tmp.fileno(), 1)
        os.dup2(tmp.fileno(), 2)
        try:
            yield box
        finally:
            _flush_c_stdio()
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])
            tmp.seek(0)
            box["text"] = tmp.read().decode("utf-8", errors="replace")
            if log_level is not None:
                if prev_level is None:
                    os.environ.pop(LOG_LEVEL_ENV, None)
                else:
                    os.environ[LOG_LEVEL_ENV] = prev_level
    if box["text"]:
        sys.stderr.write(box["text"])
        sys.stderr.flush()
