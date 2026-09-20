"""Minimal Q-8B reload smoke: load int4-4B, switch to int4-8B, switch back.

Does NOT run BFCL quality. Records per-switch load_s into
derived/q8b/_reload_smoke/. Confirms reload cost is a separate event and is
not folded into a generate timing field (no generate is issued).

Usage:
  .\\.venv-seam\\Scripts\\python.exe tools\\smoke_q8b_reload.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_q_8b_quality import (  # noqa: E402
    ARM_MODEL_SPECS,
    ARMS,
    KV_EXPECTED,
    PLACEMENT_ARM,
    _assert_kv_f16,
)

OUT_DEFAULT = ROOT / "derived" / "q8b" / "_reload_smoke"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = p.parse_args(argv)
    out: Path = args.out if args.out.is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    import tools.bfcl_feasibility_probe as probe

    events: list[dict[str, Any]] = []
    pipes: dict[str, Any] = {}

    def drop() -> None:
        pipes.clear()
        import gc

        gc.collect()

    def load(arm_id: str, *, reason: str) -> dict[str, Any]:
        spec = ARM_MODEL_SPECS[arm_id]
        probe.apply_model_spec(spec)
        t0 = time.perf_counter()
        pipe, meta, load_s = probe.load_arm_pipeline(PLACEMENT_ARM, enable_prefix_caching=None)
        wall = time.perf_counter() - t0
        kv = _assert_kv_f16(meta, arm_id=arm_id)
        pipes[arm_id] = pipe
        ev = {
            "event": "model_load",
            "arm_id": arm_id,
            "model_spec": str(spec),
            "reason": reason,
            "load_s": load_s,
            "load_wall_s": wall,
            "kv_normalized": kv["loads"][0]["kv_cache_precision"]["readback"]["normalized"],
            "excluded_from_decode_metrics": True,
            "generate_issued": False,
            "utc": _utc(),
        }
        events.append(ev)
        print(
            f"SMOKE_LOAD_OK arm={arm_id} load_s={load_s:.3f} wall_s={wall:.3f} reason={reason}",
            flush=True,
        )
        return ev

    sequence = [
        ("int4_4B", "initial_4b"),
        ("int4_8B", "switch_4b_to_8b"),
        ("int4_4B", "switch_8b_to_4b"),
    ]
    report: dict[str, Any] = {
        "kind": "q8b_reload_smoke",
        "started_utc": _utc(),
        "arms": list(ARMS),
        "placement_arm": PLACEMENT_ARM,
        "kv_expected": KV_EXPECTED,
        "ir_bytes": {
            "int4_4B": 2290768181,
            "int4_8B": 4882865352,
            "sum_gib": (2290768181 + 4882865352) / (1024**3),
        },
        "simultaneous_residency": {
            "attempted": False,
            "note": (
                "This smoke loads one arm at a time (drop between switches) to "
                "measure reload cost. Dual-resident attempt is the full runner's "
                "job when available_mb >= 10000."
            ),
        },
        "code_derived": {
            "apply_model_spec_is_global": True,
            "load_arm_pipeline_uses_MODEL_DIR": True,
            "different_model_specs_require_reload_or_dual_pipes": True,
            "cell_wall_starts_after_ensure_arm": True,
            "turn_ttft_decode_from_generate_only": True,
        },
        "status": "running",
    }
    _write(out / "report.json", report)

    avail0 = probe._host_available_mb()
    report["available_mb_start"] = avail0
    try:
        for arm_id, reason in sequence:
            if pipes:
                drop()
                events.append(
                    {
                        "event": "drop_all",
                        "before_load": arm_id,
                        "excluded_from_decode_metrics": True,
                        "utc": _utc(),
                    }
                )
            load(arm_id, reason=reason)
        report["status"] = "complete"
        report["finding"] = "reload_required_for_model_spec_switch"
        report["finding_detail"] = (
            "Arm switch drops the prior pipe and reloads the target IR. "
            "Reload cost is recorded as model_load events with "
            "excluded_from_decode_metrics=true; no generate() timing fields exist "
            "in this smoke."
        )
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["finding"] = "smoke_blocked_or_failed"
        report["finding_detail"] = (
            "Could not complete 4B->8B->4B reload sequence on this host. "
            "Code path still implies explicit reload on model-spec switch "
            "(global MODEL_DIR / apply_model_spec); dual-resident would require "
            "holding two LLMPipeline objects (~6.7 GiB IR alone)."
        )
        print(f"SMOKE_FAILED {report['error']}", flush=True)
        _write(out / "reload_events.json", {"events": events})
        _write(out / "report.json", report)
        return 2

    report["finished_utc"] = _utc()
    report["events"] = events
    load_only = [e for e in events if e.get("event") == "model_load"]
    report["reload_costs_s"] = [
        {"arm_id": e["arm_id"], "reason": e["reason"], "load_s": e["load_s"]} for e in load_only
    ]
    _write(out / "reload_events.json", {"events": events})
    _write(out / "report.json", report)
    print("SMOKE_OK", json.dumps(report["reload_costs_s"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
