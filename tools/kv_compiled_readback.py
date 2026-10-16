"""KV cache precision readback from compiled cache ports (read-only; prints JSON).

Why: the KV_CACHE_PRECISION property reads "dynamic" on openvino 2026.2.1
whether or not the GPU plugin compresses the cache. The 2026-10-15 literature
check (docs/literature/2026-10-15/notes/verify_intel_measurements.md, Q2)
found that the GPU plugin resolves "dynamic" to u4 for PagedAttention models
with 4-bit weights, and LLMPipeline uses PagedAttention by default. GenAI's
own utils.hpp says the precision must be read from the compiled model's
cache input ports. That is what this script prints.

How: LLMPipeline does not expose its compiled model, so the script repeats
the PagedAttention path on a plain Core: read the IR, apply
openvino._offline_transformations.paged_attention_transformation, compile on
the device with the same properties the runner passes, and print the element
type of every key_cache.* / value_cache.* input of the compiled model.
"default" passes no properties at all, as run_h1_hybrid --kv default
(delta_n arm gpu_only) does. u8 / u4 / f16 pass KV_CACHE_PRECISION, as the
explicit arms do. Caveat: GenAI may pass extra compile properties of its
own; if a port type here disagrees with a memory or behavior check, trust
neither until reconciled.

It also prints the IR's own quantization metadata (seam.ir_quantization:
rt_info, openvino_config.json and a constants census), to confirm the
weight scheme (registry INT4-SCHEME), and the SchedulerConfig() struct defaults on this host
(enable_prefix_caching, max_num_batched_tokens, ...). Those are the values a
runner gets when it constructs a bare SchedulerConfig (NON_RESIDENT); a
pipeline built with no SchedulerConfig uses GenAI's latency-oriented config
instead, which is not readable from Python.

Writes nothing in the repo. Uses the GPU for a few minutes; run only when no
measurement is active on the host.

  .venv-seam\\Scripts\\python.exe tools\\kv_compiled_readback.py
  .venv-seam\\Scripts\\python.exe tools\\kv_compiled_readback.py --kv default
"""

from __future__ import annotations

import argparse
import json
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--kv", choices=(*KV_CHOICES, "all"), default="all")
    ap.add_argument("--device", default="GPU")
    ap.add_argument("--model-spec", type=Path, default=DEFAULT_SPEC)
    args = ap.parse_args(argv)

    import openvino as ov
    import openvino_genai as ov_genai

    from seam.model_provenance import load_local_spec

    spec = load_local_spec(args.model_spec)
    ir_dir = Path(spec["ir_dir"])
    if not ir_dir.is_absolute():
        ir_dir = ROOT / ir_dir
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
    kvs = KV_CHOICES if args.kv == "all" else (args.kv,)
    doc["arms"] = [readback_one(ov, ir_xml, args.device, kv) for kv in kvs]
    print(json.dumps(doc, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
