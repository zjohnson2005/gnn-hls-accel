"""KV cache precision and backend readback for the true runtime default (read-only; JSON).

Why: the KV_CACHE_PRECISION property reads "dynamic" on openvino 2026.2.1
whether or not the GPU plugin compresses the cache; "dynamic" is the plugin's
pre-compile placeholder. Corrected 2026-10-16 (Task AS, source read at the
2026.2.1 tags, docs/literature/2026-10-16/DEMO2_CONTROL/openvino_defaults.md):
the 2026.2.1 GPU plugin hard-codes auto_enable_4bit_kv = false, so a
PagedAttention (PA) model with no KV property compiles i8 (key per-channel,
value per-token), not u4 as the 2026-10-15 note said; a u8 request is
normalized to the same i8; a stateful/SDPA model on Xe2/Xe3 compiles f16.

Two methods, both printed (--mode all):

1. genai (the method that matches what the runners do; DEMO-2 pilot P0):
   a child process builds LLMPipeline(ir_dir, device) with nothing passed,
   with OPENVINO_LOG_LEVEL=3, so GenAI prints the compiled properties under
   "Model: LLM with Paged Attention". The parent reads KV_CACHE_PRECISION
   from that dump and looks for the "Falling back to SDPA backend" WARN line
   (seam.genai_runtime). It also checks the IR's rt_info
   runtime_options/KV_CACHE_PRECISION, which overrides the PA default.
   Verdict "valid" = PA ran, no fallback, compiled i8, no rt_info override.
2. core (cross-check, Task AQ): repeat the PA transform on a plain Core,
   compile with the properties the runner passes (default/u8/u4/f16) and
   print the key_cache.* / value_cache.* port types. Not GenAI's own compile.

It also prints the IR quantization census (registry INT4-SCHEME) and the
SchedulerConfig() struct defaults. Those are what a bare SchedulerConfig
gets (256 tokens, prefix caching off); LLMPipeline with no SchedulerConfig
uses the latency config instead (prefix caching on, unlimited batch tokens).

Writes nothing in the repo. Uses the GPU for a few minutes; run only when no
measurement is active on the host.

  .venv-seam\\Scripts\\python.exe tools\\kv_compiled_readback.py
  .venv-seam\\Scripts\\python.exe tools\\kv_compiled_readback.py --mode genai
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
KV_CHOICES = ("default", "u8", "u4", "f16")
MODES = ("all", "core", "genai")
CHILD_DONE = "KV_READBACK_CHILD_DONE"
CACHE_PREFIXES = ("key_cache.", "value_cache.")
SCHEDULER_FIELDS = (
    "enable_prefix_caching",
    "max_num_batched_tokens",
    "max_num_seqs",
    "cache_size",
    "num_kv_blocks",
    "dynamic_split_fuse",
    "use_cache_eviction",
)


def cache_ports(ports: Iterable[Any]) -> list[dict[str, str]]:
    """Return name and element type for every key_cache.* / value_cache.* port."""
    out: list[dict[str, str]] = []
    for port in ports:
        names = sorted(str(n) for n in port.get_names())
        hit = [n for n in names if n.startswith(CACHE_PREFIXES)]
        if not hit:
            continue
        out.append({"name": hit[0], "element_type": str(port.get_element_type())})
    return out


def summarize_ports(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Distinct element types for key and value caches, with port counts."""
    summary: dict[str, Any] = {}
    for kind in ("key_cache", "value_cache"):
        types = sorted({r["element_type"] for r in rows if r["name"].startswith(kind + ".")})
        count = sum(1 for r in rows if r["name"].startswith(kind + "."))
        summary[kind] = {"element_types": types, "ports": count}
    summary["n_cache_ports"] = len(rows)
    return summary


def scheduler_defaults(ov_genai: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        sc = ov_genai.SchedulerConfig()
    except Exception as exc:  # recorded, not raised
        return {"error": f"{type(exc).__name__}: {exc}"}
    for field in SCHEDULER_FIELDS:
        try:
            out[field] = getattr(sc, field)
        except Exception as exc:
            out[field] = f"error: {type(exc).__name__}"
    return out


def _pa_transform(model: Any) -> dict[str, Any]:
    from openvino._offline_transformations import paged_attention_transformation

    try:
        paged_attention_transformation(model)
        return {"applied": True, "call": "paged_attention_transformation(model)"}
    except TypeError:
        paged_attention_transformation(model, False, False)
        return {"applied": True, "call": "paged_attention_transformation(model, False, False)"}


def _kv_props(ov: Any, kv: str) -> dict[str, Any]:
    if kv == "default":
        return {}
    return {"KV_CACHE_PRECISION": getattr(ov.Type, kv)}


def readback_one(ov: Any, ir_xml: Path, device: str, kv: str) -> dict[str, Any]:
    core = ov.Core()
    rec: dict[str, Any] = {"kv_requested": kv, "properties_passed": {}}
    if kv != "default":
        rec["properties_passed"] = {"KV_CACHE_PRECISION": kv}
    try:
        model = core.read_model(str(ir_xml))
        rec["pa_transform"] = _pa_transform(model)
        rec["model_cache_ports_before_compile"] = summarize_ports(cache_ports(model.inputs))
        t0 = time.perf_counter()
        compiled = core.compile_model(model, device, _kv_props(ov, kv))
        rec["compile_s"] = round(time.perf_counter() - t0, 2)
        rows = cache_ports(compiled.inputs)
        rec["compiled_cache_ports"] = summarize_ports(rows)
        rec["compiled_cache_ports_first4"] = rows[:4]
        try:
            rec["compiled_property_KV_CACHE_PRECISION"] = str(
                compiled.get_property("KV_CACHE_PRECISION")
            )
        except Exception as exc:
            rec["compiled_property_KV_CACHE_PRECISION"] = f"error: {type(exc).__name__}: {exc}"
        del compiled
    except Exception as exc:  # recorded, not raised: one arm failing must not hide the others
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def genai_child(ir_dir: Path, device: str) -> int:
    """Child: build LLMPipeline(ir_dir, device) with nothing else passed, then exit."""
    import openvino_genai as ov_genai

    t0 = time.perf_counter()
    pipe = ov_genai.LLMPipeline(str(ir_dir), device)
    load_s = round(time.perf_counter() - t0, 2)
    del pipe
    sys.stdout.flush()
    print(f"{CHILD_DONE} load_s={load_s}", flush=True)
    return 0


def genai_default_readback(ir_dir: Path, device: str, model_spec: Path) -> dict[str, Any]:
    """Parent: run genai_child at OPENVINO_LOG_LEVEL=3 and parse its output."""
    from seam.genai_runtime import (
        LOG_LEVEL_ENV,
        READBACK_LOG_LEVEL,
        parse_genai_load_log,
        rt_info_kv_override,
        true_default_verdict,
    )

    env = dict(os.environ)
    env[LOG_LEVEL_ENV] = READBACK_LOG_LEVEL
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--genai-child",
        "--device",
        device,
        "--model-spec",
        str(model_spec),
    ]
    rec: dict[str, Any] = {
        "method": "LLMPipeline(ir_dir, device), no properties, OPENVINO_LOG_LEVEL=3",
    }
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=1800)
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        rec["child_returncode"] = proc.returncode
        rec["child_done"] = CHILD_DONE in text
    except Exception as exc:  # recorded, not raised
        text = ""
        rec["child_error"] = f"{type(exc).__name__}: {exc}"
    parsed = parse_genai_load_log(text)
    rt = rt_info_kv_override(ir_dir / "openvino_model.xml")
    rec["parsed"] = parsed
    rec["ir_rt_info"] = rt
    rec["verdict_true_default"] = true_default_verdict(parsed, rt)
    rec["log_tail"] = text.splitlines()[-60:]
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--mode", choices=MODES, default="all")
    ap.add_argument("--kv", choices=(*KV_CHOICES, "all"), default="all")
    ap.add_argument("--device", default="GPU")
    ap.add_argument("--model-spec", type=Path, default=DEFAULT_SPEC)
    ap.add_argument("--genai-child", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    from seam.model_provenance import load_local_spec

    spec = load_local_spec(args.model_spec)
    ir_dir = Path(spec["ir_dir"])
    if not ir_dir.is_absolute():
        ir_dir = ROOT / ir_dir
    if args.genai_child:
        return genai_child(ir_dir, args.device)

    import openvino as ov
    import openvino_genai as ov_genai

    ir_xml = ir_dir / "openvino_model.xml"
    doc: dict[str, Any] = {
        "kind": "kv_compiled_readback",
        "openvino": str(getattr(ov, "__version__", None) or ov.get_version()),
        "openvino_genai": str(getattr(ov_genai, "__version__", "unknown")),
        "model_spec": str(args.model_spec),
        "ir_xml": str(ir_xml),
        "device": args.device,
        "scheduler_config_struct_defaults": scheduler_defaults(ov_genai),
    }
    try:
        from seam.ir_quantization import ir_quantization

        doc["ir_quantization"] = ir_quantization(ir_dir)
    except Exception as exc:  # recorded, not raised
        doc["ir_quantization"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        doc["device_name"] = str(ov.Core().get_property(args.device, "FULL_DEVICE_NAME"))
    except Exception as exc:
        doc["device_name"] = f"error: {type(exc).__name__}: {exc}"
    if args.mode in ("all", "genai"):
        doc["genai_default"] = genai_default_readback(ir_dir, args.device, args.model_spec)
    if args.mode in ("all", "core"):
        kvs = KV_CHOICES if args.kv == "all" else (args.kv,)
        doc["arms"] = [readback_one(ov, ir_xml, args.device, kv) for kv in kvs]
    print(json.dumps(doc, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
