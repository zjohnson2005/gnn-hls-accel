"""Payload size distributions from existing trace files."""

from __future__ import annotations

import json
from pathlib import Path

TRACE_DIR = Path("orchestration_engine/characterization/traces")
GATE_DIR = Path("orchestration_engine/characterization/out/gate")

DEFAULTS = {
    "llm_response_bytes": (512, 4096),
    "tool_result_bytes": (1024, 102_400),
}


def _estimate_json_blob_sizes(path: Path) -> list[int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    sizes: list[int] = []
    if isinstance(data, dict):
        raw = json.dumps(data)
        sizes.append(len(raw))
        for span in data.get("spans", []):
            meta = span.get("meta", {})
            for v in meta.values():
                if isinstance(v, str) and len(v) > 32:
                    sizes.append(len(v))
    return sizes


def load_payload_defaults() -> dict[str, tuple[int, int]]:
    sizes: list[int] = []
    for d in (TRACE_DIR, GATE_DIR):
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            sizes.extend(_estimate_json_blob_sizes(p))

    if len(sizes) < 5:
        return DEFAULTS

    sizes.sort()
    lo = sizes[max(0, len(sizes) // 10)]
    hi = sizes[min(len(sizes) - 1, len(sizes) * 9 // 10)]
    mid = sizes[len(sizes) // 2]
    return {
        "llm_response_bytes": (max(512, lo), max(4096, mid)),
        "tool_result_bytes": (max(1024, lo), max(hi, 50_000)),
    }
