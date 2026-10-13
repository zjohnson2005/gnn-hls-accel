"""Quantization metadata read from an OpenVINO IR directory, not assumed.

Three sources, each recorded as found:
- rt_info: the NNCF weight_compression block in openvino_model.xml, when the
  exporter wrote one (mode, group_size, ratio, ...).
- openvino_config.json: the optimum-intel quantization_config, when present.
- constants: a census of the compressed weight constants in
  openvino_model.xml (element types, group sizes from weight shapes, zero
  points). Always computed when the xml exists.

The summary fields mode, group_size, ratio and sym take the first source
that states them, in the order rt_info, openvino_config, constants, and name
that source. ratio has no constants fallback: NNCF ratio counts only the
layers eligible for the primary precision, which the census cannot tell.
The census reports int4_param_share instead.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from seam.hashing import sha256_file

__all__ = ["constants_census", "ir_quantization", "read_rt_info"]

LOW_BIT_TYPES = {"u4": 4, "i4": 4, "nf4": 4, "f4e2m1": 4, "u8": 8, "i8": 8}
SYM_TYPES = {"i4", "i8", "nf4", "f4e2m1"}


def _shape(text: str | None) -> list[int]:
    if not text:
        return []
    return [int(part) for part in text.split(",") if part.strip()]


def _nested(elem: ET.Element) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for child in elem:
        if "value" in child.attrib:
            out[child.tag] = child.attrib["value"]
        else:
            out[child.tag] = _nested(child)
    return out


def read_rt_info(xml_path: Path) -> dict[str, Any] | None:
    """The model-level rt_info as a nested dict of value strings, or None."""
    for _event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "rt_info":
            return _nested(elem)
    return None


def constants_census(xml_path: Path) -> dict[str, Any]:
    """Count low-bit Const layers by role.

    A weight is a low-bit constant of rank >= 2 whose last dimension is > 1:
    rank 3 [out, groups, group] gives group size = last dim; rank 2 [out, in]
    is per channel (group size -1). A zero point is a low-bit constant whose
    last dimension is 1 (per group or per channel), or a scalar.
    """
    weights: Counter[str] = Counter()
    params: Counter[str] = Counter()
    groups: Counter[str] = Counter()
    zero_points: Counter[str] = Counter()
    scalar_zero_points = 0
    for _event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != "layer" or elem.attrib.get("type") != "Const":
            continue
        data = elem.find("data")
        if data is None:
            continue
        etype = str(data.attrib.get("element_type", "")).lower()
        if etype not in LOW_BIT_TYPES:
            elem.clear()
            continue
        shape = _shape(data.attrib.get("shape"))
        if len(shape) >= 2 and shape[-1] > 1:
            weights[etype] += 1
            count = 1
            for dim in shape:
                count *= dim
            params[etype] += count
            group = shape[-1] if len(shape) == 3 else -1
            groups[f"{LOW_BIT_TYPES[etype]}bit:{group}"] += 1
        elif len(shape) >= 2:
            zero_points[etype] += 1
        else:
            scalar_zero_points += 1
        elem.clear()
    total = sum(params.values())
    int4 = sum(v for k, v in params.items() if LOW_BIT_TYPES[k] == 4)
    return {
        "weight_constants": dict(sorted(weights.items())),
        "weight_params": dict(sorted(params.items())),
        "group_sizes": dict(sorted(groups.items())),
        "zero_point_constants": dict(sorted(zero_points.items())),
        "scalar_low_bit_constants": scalar_zero_points,
        "int4_param_share": (int4 / total) if total else None,
    }


def _from_census(census: dict[str, Any]) -> dict[str, Any]:
    weights = census.get("weight_constants") or {}
    if not weights:
        return {}
    bits = 4 if any(LOW_BIT_TYPES[t] == 4 for t in weights) else 8
    primary = [t for t in weights if LOW_BIT_TYPES[t] == bits]
    has_zero_points = any(
        LOW_BIT_TYPES.get(t) == bits for t in census.get("zero_point_constants") or {}
    )
    sym = all(t in SYM_TYPES for t in primary) and not has_zero_points
    prefix = f"{bits}bit:"
    sizes = Counter(
        {k[len(prefix) :]: v for k, v in census["group_sizes"].items() if k.startswith(prefix)}
    )
    group = int(sizes.most_common(1)[0][0]) if sizes else None
    return {
        "mode": f"INT{bits}_{'SYM' if sym else 'ASYM'}",
        "group_size": group,
        "sym": sym,
    }


def _from_rt_info(rt_info: dict[str, Any] | None) -> dict[str, Any]:
    block = ((rt_info or {}).get("nncf") or {}).get("weight_compression")
    if not isinstance(block, dict):
        return {}
    out: dict[str, Any] = {}
    mode = block.get("mode")
    if isinstance(mode, str) and mode:
        out["mode"] = mode.upper()
        out["sym"] = mode.lower().endswith("_sym")
    if isinstance(block.get("group_size"), str):
        out["group_size"] = int(float(block["group_size"]))
    if isinstance(block.get("ratio"), str):
        out["ratio"] = float(block["ratio"])
    return out


def _from_openvino_config(config: dict[str, Any] | None) -> dict[str, Any]:
    q = (config or {}).get("quantization_config")
    if not isinstance(q, dict):
        return {}
    out: dict[str, Any] = {}
    bits = q.get("bits")
    sym = q.get("sym")
    if isinstance(sym, bool):
        out["sym"] = sym
    if isinstance(bits, int) and isinstance(sym, bool):
        out["mode"] = f"INT{bits}_{'SYM' if sym else 'ASYM'}"
    if isinstance(q.get("group_size"), int):
        out["group_size"] = q["group_size"]
    if isinstance(q.get("ratio"), int | float):
        out["ratio"] = float(q["ratio"])
    return out


def ir_quantization(ir_dir: Path, xml_sha256_pin: str | None = None) -> dict[str, Any]:
    """Read every source; never raises for a missing or unreadable IR."""
    ir_dir = Path(ir_dir)
    xml_path = ir_dir / "openvino_model.xml"
    record: dict[str, Any] = {
        "ir_dir": str(ir_dir),
        "xml_present": xml_path.is_file(),
        "xml_sha256": None,
        "xml_sha256_pin": xml_sha256_pin,
        "xml_matches_pin": None,
        "rt_info": None,
        "openvino_config": None,
        "constants": None,
        "summary": {},
        "conflicts": [],
        "error": None,
    }
    try:
        config_path = ir_dir / "openvino_config.json"
        if config_path.is_file():
            record["openvino_config"] = json.loads(config_path.read_text(encoding="utf-8"))
        if not xml_path.is_file():
            record["error"] = "openvino_model.xml absent"
            return record
        record["xml_sha256"] = sha256_file(xml_path)
        if xml_sha256_pin:
            record["xml_matches_pin"] = record["xml_sha256"] == xml_sha256_pin
        record["rt_info"] = read_rt_info(xml_path)
        record["constants"] = constants_census(xml_path)
    except (OSError, ValueError, ET.ParseError) as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record
    sources = (
        ("rt_info", _from_rt_info(record["rt_info"])),
        ("openvino_config", _from_openvino_config(record["openvino_config"])),
        ("constants", _from_census(record["constants"])),
    )
    summary: dict[str, Any] = {"source": {}}
    for field in ("mode", "group_size", "ratio", "sym"):
        stated = [(name, found[field]) for name, found in sources if field in found]
        if stated:
            summary[field] = stated[0][1]
            summary["source"][field] = stated[0][0]
            if len({json.dumps(v) for _n, v in stated}) > 1:
                record["conflicts"].append({"field": field, "stated": dict(stated)})
        else:
            summary[field] = None
            summary["source"][field] = None
    record["summary"] = summary
    return record
