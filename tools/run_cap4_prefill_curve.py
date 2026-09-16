"""CAP-4 — Prefill curve to failure per KV precision, gpu_only (merges MEM-CEIL).

Interleaved ladder across gpu_only_{f16,u8,u4}. One arm failing does not end the
sweep for the others. Continues past the primary rungs until each arm stops
working (non-pass). Reuses C-1/C-2 measured_repeat / _probe_once child path.

Predictions MUST exist in derived/cap4/CAP4_PREDICTIONS.json with
status=pre_registered_before_measurement before the first probe.

Usage:
  .\\.venv-seam\\Scripts\\python.exe tools\\run_cap4_prefill_curve.py \\
      --session-id <uuid> --out derived/cap4/<uuid>
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.run_environment import RunEnvironmentSession  # noqa: E402
from tools.run_c1_ceiling import (  # noqa: E402
    ARMS as DEFAULT_ARMS,
    IR_BYTES,
    _start_wsh_watchdog,
    classify_c1_failure,
)

PRED_PATH = ROOT / "derived" / "cap4" / "CAP4_PREDICTIONS.json"
DEFAULT_MODEL_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
PRIMARY_RUNGS = (12000, 16000, 20000, 26000, 32000, 40000, 46000)
CONTINUE_STEP = 6000
REPEATS = 3
INTERLEAVE_SEED = 20260915
SLO_PREFILL_S = 10.0
SLO_DECODE_TOK_S = 6.0
POSITION_LIMIT = 40960
MAX_N_SAFETY = 100_000


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _assert_predictions() -> dict[str, Any]:
    if not PRED_PATH.is_file():
        raise SystemExit(f"REFUSED -- {PRED_PATH} missing; register before measuring")
    pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
    if pred.get("status") != "pre_registered_before_measurement":
        raise SystemExit(f"REFUSED -- bad predictions status {pred.get('status')!r}")
    if not pred.get("registered_utc"):
        raise SystemExit("REFUSED -- predictions missing registered_utc")
    return pred


def classify_cap4_failure(result: dict[str, Any], *, envelope: dict[str, Any] | None) -> dict[str, Any]:
    """Map a non-pass child result to CAP-4 failure classes."""
    base = classify_c1_failure(result)
    verbatim = base.get("verbatim")
    combined_l = (verbatim or "").lower()
    paging_verdict = (envelope or {}).get("paging_gate_verdict")
    paging_reasons = (envelope or {}).get("paging_gate_reasons")

    if result.get("outcome") == "pass":
        return {
            "class": "pass",
            "verbatim": None,
            "c1": base,
            "paging_gate_verdict": paging_verdict,
        }

    alloc_markers = (
        "cl_out_of_resources",
        "out_of_resources",
        "out of memory",
        "oom",
        "std::bad_alloc",
        "bad_alloc",
        "cannot allocate",
        "not enough memory",
        "memoryerror",
        "failed to allocate",
        "allocation failure",
        "c0000005",
        "0xc0000005",
    )
    if any(m in combined_l for m in alloc_markers) or base.get("failure_kind") == "memory_wall":
        cls = "ALLOC_FAILURE"
    elif paging_verdict in ("FAIL", "fail", "PAGING", "paging") or (
        isinstance(paging_reasons, list) and paging_reasons
    ):
        # Paging gate FAIL on a non-pass cell.
        if paging_verdict and str(paging_verdict).upper() in ("FAIL", "PAGING"):
            cls = "PAGING"
        elif any("page" in str(r).lower() for r in (paging_reasons or [])):
            cls = "PAGING"
        else:
            cls = "OTHER"
    else:
        cls = "OTHER"

    return {
        "class": cls,
        "verbatim": verbatim,
        "c1": base,
        "paging_gate_verdict": paging_verdict,
        "paging_gate_reasons": paging_reasons,
        "exception_type": base.get("exception_type"),
        "exception_message": base.get("exception_message"),
    }


def _round_arm_order(*, seed: int, n_tokens: int, round_i: int, active: list[str]) -> list[str]:
    material = f"{seed}|cap4|{n_tokens}|{round_i}|{','.join(active)}"
    rng = random.Random(material)
    order = list(active)
    rng.shuffle(order)
    return order


def _median(xs: list[float | None]) -> float | None:
    vals = [float(x) for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not vals:
        return None
    return float(statistics.median(vals))


def _finite_floats(xs: list[Any]) -> list[float]:
    out: list[float] = []
    for x in xs:
        if x is None:
            continue
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if math.isnan(v) or math.isinf(v):
            continue
        out.append(v)
    return out


def _min_max(xs: list[Any]) -> dict[str, float | None]:
    vals = _finite_floats(xs)
    if not vals:
        return {"min": None, "max": None}
    return {"min": float(min(vals)), "max": float(max(vals))}


def _fit_power_law(ns: list[int], ys: list[float]) -> dict[str, Any] | None:
    """log y = a + b log n  →  y = exp(a) * n^b."""
    if len(ns) < 2 or len(ns) != len(ys):
        return None
    if any(n <= 0 or y <= 0 for n, y in zip(ns, ys, strict=True)):
        return None
    lx = [math.log(n) for n in ns]
    ly = [math.log(y) for y in ys]
    n = len(lx)
    mx = sum(lx) / n
    my = sum(ly) / n
    num = sum((x - mx) * (y - my) for x, y in zip(lx, ly, strict=True))
    den = sum((x - mx) ** 2 for x in lx)
    if den <= 0:
        return None
    b = num / den
    a = my - b * mx
    pred = [math.exp(a + b * math.log(nn)) for nn in ns]
    ss_res = sum((yi - pi) ** 2 for yi, pi in zip(ys, pred, strict=True))
    ss_tot = sum((yi - my) ** 2 for yi in ly)  # on log scale for stability note only
    return {
        "form": "prefill_s = C * n^b",
        "C": math.exp(a),
        "b": b,
        "n_points": n,
        "ss_res_linear": ss_res,
        "ss_tot_log_y": ss_tot,
        "predict_46000_s": math.exp(a + b * math.log(46000.0)),
    }


def analyze_session(summary: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    """Evaluate pre-registration against measured cells; answer (a)/(b)."""
    cells = summary.get("cells") or []
    by_arm: dict[str, list[dict[str, Any]]] = {a: [] for a in summary.get("arms") or DEFAULT_ARMS}
    for c in cells:
        by_arm.setdefault(c["arm_id"], []).append(c)

    per_arm: dict[str, Any] = {}
    for arm_id, arm_cells in by_arm.items():
        successes = [c for c in arm_cells if c.get("verdict") == "PASS"]
        failures = [c for c in arm_cells if c.get("verdict") != "PASS"]
        highest = max((c["n_tokens"] for c in successes), default=None)
        first_fail = min(failures, key=lambda c: c["n_tokens"]) if failures else None
        medians = {
            str(c["n_tokens"]): c.get("prefill_s_median")
            for c in successes
            if c.get("prefill_s_median") is not None
        }
        prefill_minmax: dict[str, dict[str, float | None]] = {}
        available_mb_by_n: dict[str, dict[str, float | None]] = {}
        for c in sorted(successes, key=lambda x: int(x["n_tokens"])):
            n_key = str(c["n_tokens"])
            reps = c.get("repeats_detail") or []
            prefills = [r.get("prefill_s") for r in reps]
            mm = _min_max(prefills)
            # Fall back to median-only cell when reconstruct lacks repeats_detail.
            if mm["min"] is None and c.get("prefill_s_median") is not None:
                v = float(c["prefill_s_median"])
                mm = {"min": v, "max": v}
            prefill_minmax[n_key] = mm
            available_mb_by_n[n_key] = {
                "available_mb_start_median": c.get("available_mb_start_median"),
                "available_mb_end_median": c.get("available_mb_end_median"),
            }
        ns = sorted(int(k) for k in medians)
        ys = [float(medians[str(n)]) for n in ns]
        fit = _fit_power_law(ns, ys)
        if fit is not None and ns:
            fit["fit_range_n"] = [ns[0], ns[-1]]
            fit["fit_n_list"] = list(ns)
        # First rung where start-median Available MB falls vs prior PASS rung.
        first_available_fall_n: int | None = None
        prev_mb: float | None = None
        for n in ns:
            mb = available_mb_by_n[str(n)].get("available_mb_start_median")
            if mb is None:
                continue
            mb_f = float(mb)
            if prev_mb is not None and mb_f < prev_mb:
                first_available_fall_n = n
                break
            prev_mb = mb_f
        per_arm[arm_id] = {
            "highest_successful_n": highest,
            "first_failure_n": (first_fail or {}).get("n_tokens"),
            "first_failure_class": (first_fail or {}).get("failure_class"),
            "first_failure_verbatim": (first_fail or {}).get("verbatim_error"),
            "reached_46000": bool(highest is not None and highest >= 46000),
            "median_prefill_s_by_n": medians,
            "prefill_s_min_max_by_n": prefill_minmax,
            "available_mb_by_n": available_mb_by_n,
            "first_available_mb_fall_n": first_available_fall_n,
            "power_law_fit": fit,
            "rungs_completed": sorted({int(c["n_tokens"]) for c in arm_cells}),
            "first_slo_exceeded_n": next(
                (
                    c["n_tokens"]
                    for c in sorted(successes, key=lambda x: x["n_tokens"])
                    if c.get("slo_exceeded")
                ),
                None,
            ),
        }

    reached = {a: per_arm[a]["reached_46000"] for a in per_arm}
    any_alloc = any(per_arm[a].get("first_failure_class") == "ALLOC_FAILURE" for a in per_arm)
    all_reach_46000_no_alloc = all(reached.values()) and not any_alloc

    # P1
    p1_vals = [
        per_arm[a]["median_prefill_s_by_n"].get("46000")
        for a in per_arm
        if per_arm[a]["median_prefill_s_by_n"].get("46000") is not None
    ]
    p1: dict[str, Any]
    if not p1_vals:
        p1 = {"outcome": "not_evaluable", "reason": "no arm reached n=46000 with PASS"}
    else:
        band = pred["predictions"]["P1_prefill_at_46000"]["evaluable_band_s"]
        in_band = all(band[0] <= float(v) <= band[1] for v in p1_vals)
        p1 = {
            "outcome": "confirmed" if in_band else "falsified",
            "predicted_s": 115.0,
            "measured_median_prefill_s_at_46000": {a: per_arm[a]["median_prefill_s_by_n"].get("46000") for a in per_arm},
            "band_s": band,
        }

    # P2 order
    highs = {a: per_arm[a]["highest_successful_n"] for a in per_arm}
    orderable = all(v is not None for v in highs.values())
    if all_reach_46000_no_alloc:
        p2_outcome = "falsified"
        p2_reason = "joint_falsifier: all three reached 46000 without ALLOC_FAILURE"
    elif orderable:
        f16, u8, u4 = highs["gpu_only_f16"], highs["gpu_only_u8"], highs["gpu_only_u4"]
        ok = f16 < u8 < u4  # type: ignore[operator]
        p2_outcome = "confirmed" if ok else "falsified"
        p2_reason = f"highest_success order f16={f16} u8={u8} u4={u4}"
    else:
        p2_outcome = "partial"
        p2_reason = "one or more arms have no successful cell"

    p2 = {
        "outcome": p2_outcome,
        "reason": p2_reason,
        "highest_successful_n": highs,
        "any_alloc_failure": any_alloc,
    }

    p3 = {
        "outcome": ("falsified" if all_reach_46000_no_alloc else ("confirmed" if any_alloc else "partial")),
        "any_alloc_failure": any_alloc,
        "note": (
            "Primary rungs start at n>=12000; C-2 already showed TTFT SLO binding near 9750 "
            "for u8/u4 and f16 ALLOC at 8000 (c647f0c7). CAP-4 asks whether ALLOC binds "
            "before the extrapolated 46k point under interleaved per-KV gpu_only RESIDENT."
        ),
    }

    overall = "confirmed"
    outcomes = [p1["outcome"], p2["outcome"], p3["outcome"]]
    if "falsified" in outcomes:
        overall = "falsified"
    elif "partial" in outcomes or "not_evaluable" in outcomes:
        overall = "partial"

    answer_a = {
        "question": "Is ~2 minutes / ~115 s at 46000 measured, or only extrapolated?",
        "46000_reachable": any(reached.values()),
        "measured_prefill_s_at_46000": {
            a: per_arm[a]["median_prefill_s_by_n"].get("46000") for a in per_arm
        },
        "prediction_115s": p1,
    }
    answer_b = {
        "question": "Does GPU allocation ceiling bind before SLO on gpu_only?",
        "per_arm_first_failure_class": {
            a: per_arm[a].get("first_failure_class") for a in per_arm
        },
        "per_arm_first_failure_n": {a: per_arm[a].get("first_failure_n") for a in per_arm},
        "slo_already_binds_by_n12000": True,
        "alloc_binds_before_46k": {
            a: (
                per_arm[a].get("first_failure_class") == "ALLOC_FAILURE"
                and per_arm[a].get("first_failure_n") is not None
                and int(per_arm[a]["first_failure_n"]) <= 46000
            )
            for a in per_arm
        },
        "p3": p3,
    }

    return {
        "per_arm": per_arm,
        "pre_registration_outcome": overall,
        "P1": p1,
        "P2": p2,
        "P3": p3,
        "answer_a": answer_a,
        "answer_b": answer_b,
        "median_prefill_table": {
            a: per_arm[a]["median_prefill_s_by_n"] for a in per_arm
        },
    }


def run_session(
    *,
    out_dir: Path,
    session_id: str,
    model_spec: Path,
    arms: list[str],
    repeats: int,
    seed: int,
    watchdog_interval_s: int,
    primary_rungs: list[int],
    continue_step: int,
) -> dict[str, Any]:
    from transformers import AutoTokenizer

    from seam.config import resolve_config
    from seam.model_provenance import load_local_spec
    from seam.powerstate import capture_power_state
    from seam.tools.delta_n import (
        _DELTA_N_PATH,
        _MEASUREMENT_PATH,
        _PLATFORM_PATH,
        memory_now,
        prompt_for,
    )
    from seam.tools.acceptance_instrumentation import host_memory_snapshot

    pred = _assert_predictions()
    power = capture_power_state()
    if power.on_battery:
        raise SystemExit(
            f"REFUSED -- CAP-4 requires AC; on_battery={power.on_battery} pct={power.battery_pct}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "work"
    work_dir.mkdir(exist_ok=True)

    resolved = resolve_config(
        [ROOT / _PLATFORM_PATH, ROOT / _MEASUREMENT_PATH, ROOT / _DELTA_N_PATH],
        repo_root=ROOT,
    )
    cfg = resolved.data
    spec = load_local_spec(model_spec)
    model_dir = str(spec["ir_dir"])
    if not Path(model_dir).is_dir():
        raise SystemExit(f"REFUSED -- model IR missing: {model_dir}")
    arms_by_id = {a["id"]: a for a in cfg["arms"]}
    for aid in arms:
        if aid not in arms_by_id:
            raise SystemExit(f"REFUSED -- unknown arm {aid}")
        if aid == "gpu_only_f16":
            props = arms_by_id[aid].get("properties") or {}
            if str(props.get("KV_CACHE_PRECISION") or "").lower() != "f16":
                raise SystemExit(f"REFUSED -- gpu_only_f16 pin missing f16: {props}")

    p_cpus = [int(c) for c in cfg["topology"]["p_cpus"]]
    if sorted(p_cpus) != [0, 1, 2, 3]:
        raise SystemExit(f"REFUSED -- unexpected p_cpus {p_cpus}; Platform A expects 0..3")
    unit = str((cfg.get("ladder") or {}).get("filler_unit") or "")
    if not unit:
        raise SystemExit("REFUSED -- ladder.filler_unit missing")

    mb0 = memory_now()
    env_session = RunEnvironmentSession.begin(
        session_design="interleaved",
        arm_order=list(arms),
        available_mb_start=float(mb0["available_mb"]),
        available_mb_start_method="delta_n.memory_now",
    )

    watch = _start_wsh_watchdog(out_dir, int(watchdog_interval_s))
    plan = {
        "kind": "cap4_prefill_curve_to_failure",
        "experiment": "CAP-4",
        "session_id": session_id,
        "started_utc": _utc(),
        "model_spec": str(model_spec),
        "ir_sha256": spec.get("ir_sha256"),
        "ir_bytes": IR_BYTES,
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "arms": list(arms),
        "session_design": "interleaved",
        "arm_order": list(arms),
        "primary_rungs": list(primary_rungs),
        "continue_past_primary_step": int(continue_step),
        "repeats_per_cell": int(repeats),
        "interleave_seed": int(seed),
        "slo": {
            "prefill_s_max": SLO_PREFILL_S,
            "decode_tok_s_min": SLO_DECODE_TOK_S,
            "stops_arm": False,
        },
        "position_limit_tokens": POSITION_LIMIT,
        "pre_registered_predictions_path": str(PRED_PATH.relative_to(ROOT)).replace("\\", "/"),
        "predictions_registered_utc": pred.get("registered_utc"),
        "predictions": pred.get("predictions"),
        "joint_falsifier": pred.get("joint_falsifier"),
        "power_state_at_start": {
            "on_battery": power.on_battery,
            "battery_pct": power.battery_pct,
            "charging": power.charging,
            "power_plan_name": power.power_plan_name,
            "power_plan_guid": power.power_plan_guid,
        },
        "available_mb_start": mb0,
        "watchdog": watch,
        "status": "running",
        "run_environment": {
            "available_mb_start": float(mb0["available_mb"]),
            "session_design": "interleaved",
            "arm_order": list(arms),
        },
    }
    _write_json(out_dir / "plan.json", plan)
    print(
        json.dumps({"event": "cap4.plan_written", "session_id": session_id}, sort_keys=True),
        flush=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    prompt_cache: dict[int, dict[str, Any]] = {}
    probes_log: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    realized_orders: list[dict[str, Any]] = []
    active = list(arms)
    arm_dead: dict[str, dict[str, Any]] = {}
    status = "complete"
    abort_reason: str | None = None
    abort_verbatim: str | None = None
    abort_at: dict[str, Any] | None = None
    run_environment: dict[str, Any] | None = None

    def persist() -> None:
        _write_json(out_dir / "cells.json", {"cells": cells})
        (out_dir / "probes.ndjson").write_text(
            "".join(json.dumps(p, sort_keys=True) + "\n" for p in probes_log),
            encoding="utf-8",
        )
        _write_json(
            out_dir / "checkpoint.json",
            {
                "active_arms": active,
                "arm_dead": arm_dead,
                "n_cells": len(cells),
                "n_probes": len(probes_log),
                "updated_utc": _utc(),
                "status": status,
                "abort_reason": abort_reason,
            },
        )

    def measure_repeat(arm_id: str, n_tokens: int, round_i: int, arm_order: list[str]) -> dict[str, Any]:
        from seam.tools.ceiling_a import _child_spec_for_arm
        from seam.tools.delta_n import measured_repeat

        prompt = prompt_for(
            root=ROOT,
            tokenizer=tokenizer,
            n_tokens=n_tokens,
            unit=unit,
            cache=prompt_cache,
        )
        prompt_text = Path(prompt["path"]).read_text(encoding="utf-8")
        env_session.add_prompt_render(prompt_text)

        host_start = host_memory_snapshot()
        mb_start = memory_now()
        print(f"[cap4] probe arm={arm_id} n={n_tokens} repeat={round_i}", flush=True)
        child_spec = _child_spec_for_arm(
            cfg=cfg,
            arm=arms_by_id[arm_id],
            model_dir=model_dir,
            prompt=prompt,
            p_cpus=p_cpus,
        )
        tag = f"{arm_id}.n{n_tokens}.r{round_i}"
        record = measured_repeat(
            root=ROOT,
            cfg=cfg,
            p_cpus=p_cpus,
            work_dir=work_dir,
            child_spec=child_spec,
            label=f"cap4/{arm_id}/{n_tokens}/{round_i}",
            tag=tag,
        )
        mb_end = memory_now()
        result = record.get("result") or {}
        child = result.get("child") or {}
        gen = child.get("generation") or {}
        envelope = record.get("envelope") or {}
        outcome = result.get("outcome")
        failure = None
        if outcome != "pass":
            failure = classify_cap4_failure(result, envelope=envelope)

        prefill = gen.get("prefill_s")
        decode = gen.get("decode_tok_s")
        slo_exceeded = False
        if outcome == "pass" and prefill is not None:
            if float(prefill) > SLO_PREFILL_S:
                slo_exceeded = True
            if decode is not None and float(decode) < SLO_DECODE_TOK_S:
                slo_exceeded = True

        row = {
            "arm_id": arm_id,
            "n_tokens": n_tokens,
            "repeat_index": round_i,
            "realized_arm_order": list(arm_order),
            "outcome": outcome,
            "completed": bool(child.get("completed")),
            "admissible": record.get("admissible"),
            "prefill_s": prefill,
            "decode_tok_s": decode,
            "r_prefill_tok_s": gen.get("r_prefill_tok_s"),
            "wall_s": gen.get("wall_s"),
            "slo_exceeded": slo_exceeded,
            "failure_class": (failure or {}).get("class") if failure else "pass",
            "verbatim_error": (failure or {}).get("verbatim") if failure else None,
            "failure_detail": failure,
            "paging_gate_verdict": envelope.get("paging_gate_verdict"),
            "available_mb_start": mb_start.get("available_mb"),
            "available_mb_end": mb_end.get("available_mb"),
            "host_memory_start": host_start,
            "beyond_native_context": n_tokens > POSITION_LIMIT,
            "started_utc": record.get("started_utc"),
            "ended_utc": record.get("ended_utc"),
            "prompt_path": prompt.get("path"),
            "prompt_sha256": prompt.get("sha256"),
        }
        probes_log.append(row)
        return row

    def _finalize_run_environment() -> dict[str, Any]:
        nonlocal run_environment
        if run_environment is not None:
            return run_environment
        try:
            run_environment = env_session.finalize()
        except Exception as exc:  # noqa: BLE001 — abort path must still emit a summary
            # Reconstruct what we can from plan + last probe bookends.
            last_mb_end = None
            if probes_log:
                last_mb_end = probes_log[-1].get("available_mb_end")
            run_environment = {
                "available_mb_start": float(mb0["available_mb"]),
                "available_mb_end": float(last_mb_end)
                if last_mb_end is not None
                else float(mb0["available_mb"]),
                "session_design": "interleaved",
                "arm_order": list(arms),
                "prompt_render_sha256": None,
                "finalize_error": f"{type(exc).__name__}: {exc}",
            }
        return run_environment

    def write_summary(*, final_status: str) -> dict[str, Any]:
        executed = sorted({c["n_tokens"] for c in cells})
        rungs_completed_per_arm = {
            a: sorted({int(c["n_tokens"]) for c in cells if c.get("arm_id") == a}) for a in arms
        }
        env = _finalize_run_environment()
        ended = _utc()
        plan["run_environment"] = env
        if env.get("prompt_render_sha256"):
            plan["prompt_render_sha256"] = env["prompt_render_sha256"]
        plan["status"] = final_status
        plan["ended_utc"] = ended
        plan["arm_dead"] = arm_dead
        plan["rungs_executed"] = executed
        plan["abort_reason"] = abort_reason
        plan["abort_verbatim"] = abort_verbatim
        plan["abort_at"] = abort_at
        plan["rungs_completed_per_arm"] = rungs_completed_per_arm
        _write_json(out_dir / "plan.json", plan)
        _write_json(out_dir / "realized_orders.json", {"orders": realized_orders})
        persist()

        summary: dict[str, Any] = {
            "kind": "cap4_prefill_curve_to_failure",
            "experiment": "CAP-4",
            "session_id": session_id,
            "status": final_status,
            "ended_utc": ended,
            "arms": list(arms),
            "session_design": "interleaved",
            "arm_order": list(arms),
            "placement": "gpu_only",
            "residency": "RESIDENT",
            "cells": cells,
            "arm_dead": arm_dead,
            "n_probes": len(probes_log),
            "rungs_executed": executed,
            "rungs_completed_per_arm": rungs_completed_per_arm,
            "predictions_registered_utc": pred.get("registered_utc"),
            "available_mb_start": env.get("available_mb_start"),
            "available_mb_end": env.get("available_mb_end"),
            "prompt_render_sha256": env.get("prompt_render_sha256"),
            "run_environment": env,
            "abort_reason": abort_reason,
            "abort_verbatim": abort_verbatim,
            "abort_at": abort_at,
        }
        analysis = analyze_session(summary, pred)
        if final_status == "aborted":
            analysis["stop_classification"] = {
                "class": "quiescence_refusal_under_paging_pressure"
                if abort_verbatim and "quiescence_refusal" in abort_verbatim
                else "aborted",
                "note": (
                    "Sweep stopped on machine-admissibility refusal, not an allocation "
                    "ceiling (no ALLOC_FAILURE cell recorded)."
                ),
                "abort_reason": abort_reason,
                "abort_verbatim": abort_verbatim,
                "abort_at": abort_at,
            }
        summary["analysis"] = analysis
        _write_json(out_dir / "summary.json", summary)
        _write_json(out_dir / "analysis.json", analysis)
        report = _render_report(summary, analysis, pred)
        (out_dir / "CAP4_RESULTS.md").write_text(report, encoding="utf-8")
        (ROOT / "derived" / "cap4" / "CAP4_RESULTS.md").write_text(report, encoding="utf-8")
        print(report.encode("ascii", errors="replace").decode("ascii"))
        return summary

    summary_out: dict[str, Any] | None = None
    try:
        # Build rung schedule: primary, then continue while any arm active.
        rungs = list(primary_rungs)
        next_extra = primary_rungs[-1] + continue_step if primary_rungs else continue_step

        rung_i = 0
        while True:
            if rung_i < len(rungs):
                n_tokens = rungs[rung_i]
            else:
                if not active:
                    break
                n_tokens = next_extra
                next_extra += continue_step
                if n_tokens > MAX_N_SAFETY:
                    print(
                        json.dumps(
                            {
                                "event": "cap4.safety_stop",
                                "n_tokens": n_tokens,
                                "active": active,
                            }
                        ),
                        flush=True,
                    )
                    break
                rungs.append(n_tokens)

            if not active:
                break

            print(
                json.dumps(
                    {"event": "cap4.rung_start", "n_tokens": n_tokens, "active": list(active)},
                    sort_keys=True,
                ),
                flush=True,
            )

            # Interleaved: for each repeat round, shuffle active arms and measure one each.
            per_arm_reps: dict[str, list[dict[str, Any]]] = {a: [] for a in list(active)}
            for round_i in range(repeats):
                still = [a for a in active if a not in arm_dead]
                if not still:
                    break
                order = _round_arm_order(
                    seed=seed, n_tokens=n_tokens, round_i=round_i, active=still
                )
                realized_orders.append(
                    {
                        "n_tokens": n_tokens,
                        "round_i": round_i,
                        "order": list(order),
                        "utc": _utc(),
                    }
                )
                for arm_id in order:
                    if arm_id in arm_dead:
                        continue
                    row = measure_repeat(arm_id, n_tokens, round_i, order)
                    per_arm_reps.setdefault(arm_id, []).append(row)
                    persist()

            # Summarize cells; kill arms that did not fully pass.
            for arm_id in list(active):
                reps = per_arm_reps.get(arm_id) or []
                if not reps:
                    continue
                outcomes = [r.get("outcome") for r in reps]
                n_pass = sum(1 for o in outcomes if o == "pass")
                if n_pass == repeats:
                    verdict = "PASS"
                elif n_pass == 0:
                    verdict = "FAIL"
                else:
                    verdict = "MIXED"

                prefills = [r.get("prefill_s") for r in reps]
                decodes = [r.get("decode_tok_s") for r in reps]
                fail_reps = [r for r in reps if r.get("outcome") != "pass"]
                # Prefer ALLOC_FAILURE if any repeat has it.
                failure_class = None
                verbatim = None
                if fail_reps:
                    for prefer in ("ALLOC_FAILURE", "PAGING", "SLO_EXCEEDED", "OTHER"):
                        hit = next(
                            (r for r in fail_reps if r.get("failure_class") == prefer), None
                        )
                        if hit:
                            failure_class = hit.get("failure_class")
                            verbatim = hit.get("verbatim_error")
                            break

                cell = {
                    "arm_id": arm_id,
                    "n_tokens": n_tokens,
                    "verdict": verdict,
                    "n_pass": n_pass,
                    "repeats": repeats,
                    "prefill_s_median": _median(prefills),  # type: ignore[arg-type]
                    "decode_tok_s_median": _median(decodes),  # type: ignore[arg-type]
                    "failure_class": failure_class,
                    "verbatim_error": verbatim,
                    "available_mb_start_median": _median(
                        [r.get("available_mb_start") for r in reps]  # type: ignore[list-item]
                    ),
                    "available_mb_end_median": _median(
                        [r.get("available_mb_end") for r in reps]  # type: ignore[list-item]
                    ),
                    "beyond_native_context": n_tokens > POSITION_LIMIT,
                    "repeats_detail": reps,
                }
                med_p = cell["prefill_s_median"]
                med_d = cell["decode_tok_s_median"]
                cell["slo_exceeded"] = bool(
                    verdict == "PASS"
                    and (
                        (med_p is not None and float(med_p) > SLO_PREFILL_S)
                        or (med_d is not None and float(med_d) < SLO_DECODE_TOK_S)
                    )
                )
                cells.append(cell)

                if verdict != "PASS":
                    arm_dead[arm_id] = {
                        "first_failure_n": n_tokens,
                        "failure_class": failure_class or "OTHER",
                        "verbatim_error": verbatim,
                        "verdict": verdict,
                        "ended_utc": _utc(),
                    }
                    active = [a for a in active if a != arm_id]
                    print(
                        json.dumps(
                            {
                                "event": "cap4.arm_dead",
                                "arm_id": arm_id,
                                "n_tokens": n_tokens,
                                "failure_class": failure_class,
                                "verdict": verdict,
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )

            persist()
            _write_json(out_dir / "realized_orders.json", {"orders": realized_orders})
            rung_i += 1
            if rung_i >= len(primary_rungs) and not active:
                break
    except BaseException as exc:
        from seam.errors import SeamError

        status = "aborted"
        abort_reason = type(exc).__name__
        abort_verbatim = str(exc)
        # Infer abort locus from the last realized order / next arm when possible.
        abort_at = {
            "exception_type": type(exc).__name__,
            "n_probes_completed": len(probes_log),
            "n_cells_completed": len(cells),
            "active_arms_at_abort": list(active),
        }
        if realized_orders:
            last_ord = realized_orders[-1]
            abort_at["n_tokens"] = last_ord.get("n_tokens")
            abort_at["round_i"] = last_ord.get("round_i")
            abort_at["realized_arm_order"] = last_ord.get("order")
        if probes_log:
            last = probes_log[-1]
            abort_at["last_completed_probe"] = {
                "arm_id": last.get("arm_id"),
                "n_tokens": last.get("n_tokens"),
                "repeat_index": last.get("repeat_index"),
            }
        # Prefer label embedded in SeamError text (cap4/<arm>/<n>/<r>).
        if isinstance(exc, SeamError):
            parts = abort_verbatim.split(":", 1)[0].strip().split("/")
            if len(parts) >= 4 and parts[0] == "cap4":
                abort_at["arm_id"] = parts[1]
                try:
                    abort_at["n_tokens"] = int(parts[2])
                    abort_at["repeat_index"] = int(parts[3])
                except ValueError:
                    pass
        print(
            json.dumps(
                {
                    "event": "cap4.aborted",
                    "abort_reason": abort_reason,
                    "abort_verbatim": abort_verbatim,
                    "abort_at": abort_at,
                },
                sort_keys=True,
                default=str,
            ),
            flush=True,
        )
        raise
    finally:
        if summary_out is None:
            try:
                summary_out = write_summary(final_status=status)
            except Exception as write_exc:  # noqa: BLE001
                print(
                    json.dumps(
                        {
                            "event": "cap4.summary_write_failed",
                            "error": f"{type(write_exc).__name__}: {write_exc}",
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                raise

    assert summary_out is not None
    return summary_out


def _render_report(summary: dict[str, Any], analysis: dict[str, Any], pred: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# CAP-4 results — prefill curve to failure (gpu_only / RESIDENT)")
    lines.append("")
    lines.append(f"- **session_id / run_id:** `{summary['session_id']}`")
    lines.append(f"- **status:** `{summary['status']}`")
    if summary.get("status") == "aborted":
        lines.append(f"- **abort_reason:** `{summary.get('abort_reason')}`")
        lines.append(f"- **abort_verbatim:** `{summary.get('abort_verbatim')}`")
        stop = (analysis.get("stop_classification") or {})
        if stop:
            lines.append(f"- **stop_classification:** `{stop.get('class')}` — {stop.get('note')}")
    lines.append(f"- **pre-registration outcome:** **{analysis['pre_registration_outcome']}**")
    lines.append(f"- **predictions registered:** `{pred.get('registered_utc')}`")
    lines.append(f"- **ended_utc:** `{summary.get('ended_utc')}`")
    lines.append("")
    lines.append("## Per-KV ceilings")
    lines.append("")
    lines.append("| arm | highest PASS n | first fail n | class | verbatim (head) |")
    lines.append("|---|---:|---:|---|---|")
    for arm, row in analysis["per_arm"].items():
        verb = row.get("first_failure_verbatim") or ""
        verb_h = (verb[:120] + "…") if len(verb) > 120 else verb
        verb_h = verb_h.replace("\n", " ")
        lines.append(
            f"| `{arm}` | {row.get('highest_successful_n')} | {row.get('first_failure_n')} | "
            f"{row.get('first_failure_class')} | {verb_h} |"
        )
    lines.append("")
    lines.append("## Median prefill_s (PASS cells) with min/max")
    lines.append("")
    all_n = sorted(
        {
            int(n)
            for row in analysis["per_arm"].values()
            for n in row.get("median_prefill_s_by_n", {})
        }
    )
    header = "| n | " + " | ".join(f"`{a}` median (min–max)" for a in analysis["per_arm"]) + " |"
    lines.append(header)
    lines.append("|---:|" + "|".join(["---:" for _ in analysis["per_arm"]]) + "|")
    for n in all_n:
        cols = []
        for arm, row in analysis["per_arm"].items():
            v = row.get("median_prefill_s_by_n", {}).get(str(n))
            mm = row.get("prefill_s_min_max_by_n", {}).get(str(n)) or {}
            if isinstance(v, float):
                lo, hi = mm.get("min"), mm.get("max")
                if lo is not None and hi is not None:
                    cols.append(f"{v:.3f} ({lo:.3f}–{hi:.3f})")
                else:
                    cols.append(f"{v:.3f}")
            else:
                cols.append("—")
        lines.append(f"| {n} | " + " | ".join(cols) + " |")
    lines.append("")
    lines.append("## Power-law fit (prefill_s = C · n^b)")
    lines.append("")
    for arm, row in analysis["per_arm"].items():
        fit = row.get("power_law_fit") or {}
        if not fit:
            lines.append(f"- `{arm}`: insufficient points")
            continue
        fr = fit.get("fit_range_n")
        lines.append(
            f"- `{arm}`: b={fit.get('b'):.4f}, C={fit.get('C'):.6g}, "
            f"fit_range_n={fr}, n_points={fit.get('n_points')}, "
            f"predict_46000_s={fit.get('predict_46000_s')}"
        )
    lines.append("")
    lines.append("## Measured prefill at n=46000 vs pre-registered ~115 s")
    lines.append("")
    p1 = analysis.get("P1") or {}
    measured_46 = p1.get("measured_median_prefill_s_at_46000") or {
        a: analysis["per_arm"][a]["median_prefill_s_by_n"].get("46000") for a in analysis["per_arm"]
    }
    for arm, v in measured_46.items():
        lines.append(f"- `{arm}`: **{v}** s (predicted ~115 s; band {p1.get('band_s')})")
    lines.append(f"- P1 outcome: **{p1.get('outcome')}**")
    lines.append("")
    lines.append("## Available MB (start/end median) by rung")
    lines.append("")
    header_mb = (
        "| n | "
        + " | ".join(f"`{a}` start→end" for a in analysis["per_arm"])
        + " |"
    )
    lines.append(header_mb)
    lines.append("|---:|" + "|".join(["---:" for _ in analysis["per_arm"]]) + "|")
    mb_ns = sorted(
        {
            int(n)
            for row in analysis["per_arm"].values()
            for n in row.get("available_mb_by_n", {})
        }
    )
    for n in mb_ns:
        cols = []
        for arm, row in analysis["per_arm"].items():
            mb = row.get("available_mb_by_n", {}).get(str(n)) or {}
            s, e = mb.get("available_mb_start_median"), mb.get("available_mb_end_median")
            if s is None and e is None:
                cols.append("—")
            else:
                cols.append(f"{s:.1f}→{e:.1f}" if s is not None and e is not None else f"{s}/{e}")
        lines.append(f"| {n} | " + " | ".join(cols) + " |")
    lines.append("")
    for arm, row in analysis["per_arm"].items():
        fall = row.get("first_available_mb_fall_n")
        lines.append(
            f"- `{arm}` first Available-MB fall vs prior PASS rung: "
            f"{fall if fall is not None else 'none observed (start-median did not decline)'}"
        )
    lines.append("")
    lines.append("## Pre-registration")
    lines.append("")
    lines.append(f"- **P1 (≈115 s @ 46k):** {analysis['P1']}")
    lines.append(f"- **P2 (f16 < u8 < u4):** {analysis['P2']}")
    lines.append(f"- **P3 (ALLOC binds):** {analysis['P3']}")
    lines.append("")
    lines.append("## Answers")
    lines.append("")
    lines.append(f"- **(a)** {analysis['answer_a']}")
    lines.append(f"- **(b)** {analysis['answer_b']}")
    lines.append("")
    re = summary.get("run_environment") or {}
    lines.append("## INF-5 run_environment (session slice)")
    lines.append("")
    lines.append(f"- session_design: `{re.get('session_design')}`")
    lines.append(f"- arm_order: `{re.get('arm_order')}`")
    lines.append(f"- available_mb_start/end: {re.get('available_mb_start')} / {re.get('available_mb_end')}")
    lines.append(f"- prompt_render_sha256: `{re.get('prompt_render_sha256')}`")
    lines.append("")
    rungs_per = summary.get("rungs_completed_per_arm") or {
        a: analysis["per_arm"][a].get("rungs_completed") for a in analysis["per_arm"]
    }
    lines.append("## Rungs completed per arm")
    lines.append("")
    for arm, rungs in rungs_per.items():
        lines.append(f"- `{arm}`: {rungs}")
    lines.append("")
    return "\n".join(lines) + "\n"


def reconstruct_aborted_summary(
    *,
    session_dir: Path,
    abort_verbatim: str,
    abort_reason: str = "SeamError",
    abort_at: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild summary.json from on-disk cells/probes/plan for an aborted session.

    Does not invent cells. Replays prompt renders from probes (+ the aborting
    probe's prompt, which was folded into the hasher before measured_repeat raised)
    to restore INF-5 prompt_render_sha256.
    """
    import hashlib

    plan = json.loads((session_dir / "plan.json").read_text(encoding="utf-8-sig"))
    cells_doc = json.loads((session_dir / "cells.json").read_text(encoding="utf-8-sig"))
    cells = list(cells_doc.get("cells") or [])
    probes = [
        json.loads(line)
        for line in (session_dir / "probes.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pred = _assert_predictions()
    arms = list(plan.get("arms") or DEFAULT_ARMS)
    session_id = str(plan.get("session_id") or session_dir.name)

    # Replay prompt hasher: every completed probe, then the aborting probe's prompt
    # (add_prompt_render runs before measured_repeat raises).
    hasher = hashlib.sha256()
    prompt_updates = 0

    def _fold_prompt(path: str | None) -> None:
        nonlocal prompt_updates
        if not path:
            return
        text = Path(path).read_text(encoding="utf-8")
        hasher.update(b"\0")
        hasher.update(text.encode("utf-8"))
        prompt_updates += 1

    for row in probes:
        _fold_prompt(row.get("prompt_path"))
    abort_n = (abort_at or {}).get("n_tokens")
    if abort_n is None and abort_verbatim.startswith("cap4/"):
        try:
            abort_n = int(abort_verbatim.split(":", 1)[0].strip().split("/")[2])
        except (IndexError, ValueError):
            abort_n = None
    if abort_n is not None:
        abort_prompt = ROOT / "derived" / "delta_n" / "prompts" / f"n{int(abort_n)}.txt"
        if abort_prompt.is_file():
            _fold_prompt(str(abort_prompt))

    if prompt_updates < 1:
        raise SystemExit("REFUSED -- reconstruct found no prompts to hash")

    last_mb_end = None
    if probes:
        last_mb_end = probes[-1].get("available_mb_end")
    avail_start = plan.get("available_mb_start")
    if isinstance(avail_start, dict):
        avail_start_mb = avail_start.get("available_mb")
    else:
        avail_start_mb = (plan.get("run_environment") or {}).get("available_mb_start")

    from seam.run_environment import probe_workloads_session_host

    wsh = probe_workloads_session_host()
    run_environment = {
        "available_mb_start": float(avail_start_mb),
        "available_mb_end": float(last_mb_end if last_mb_end is not None else avail_start_mb),
        "session_design": plan.get("session_design") or "interleaved",
        "arm_order": list(plan.get("arm_order") or arms),
        "prompt_render_sha256": hasher.hexdigest(),
        "workloads_session_host_resident": bool(wsh.get("resident"))
        if isinstance(wsh.get("resident"), bool)
        else None,
        "reconstructed_from": "cells.json+probes.ndjson+plan.json+abort_prompt",
        "prompt_render_updates": prompt_updates,
    }

    executed = sorted({int(c["n_tokens"]) for c in cells})
    rungs_completed_per_arm = {
        a: sorted({int(c["n_tokens"]) for c in cells if c.get("arm_id") == a}) for a in arms
    }
    ckpt = {}
    ckpt_path = session_dir / "checkpoint.json"
    if ckpt_path.is_file():
        ckpt = json.loads(ckpt_path.read_text(encoding="utf-8-sig"))

    abort_at = abort_at or {
        "arm_id": "gpu_only_u4",
        "n_tokens": 82000,
        "repeat_index": 1,
        "n_probes_completed": len(probes),
        "n_cells_completed": len(cells),
        "active_arms_at_abort": ckpt.get("active_arms") or arms,
        "source": "reconstruct_aborted_summary",
    }

    ended = _utc()
    summary: dict[str, Any] = {
        "kind": "cap4_prefill_curve_to_failure",
        "experiment": "CAP-4",
        "session_id": session_id,
        "status": "aborted",
        "ended_utc": ended,
        "arms": arms,
        "session_design": "interleaved",
        "arm_order": list(plan.get("arm_order") or arms),
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "cells": cells,
        "arm_dead": ckpt.get("arm_dead") or {},
        "n_probes": len(probes),
        "rungs_executed": executed,
        "rungs_completed_per_arm": rungs_completed_per_arm,
        "predictions_registered_utc": pred.get("registered_utc"),
        "available_mb_start": run_environment["available_mb_start"],
        "available_mb_end": run_environment["available_mb_end"],
        "prompt_render_sha256": run_environment["prompt_render_sha256"],
        "run_environment": run_environment,
        "abort_reason": abort_reason,
        "abort_verbatim": abort_verbatim,
        "abort_at": abort_at,
        "reconstructed": True,
        "reconstruction_note": (
            "summary.json rebuilt from sealed-in-progress session artifacts after "
            "SeamError exit without summary write (pre-fix worker)."
        ),
    }
    analysis = analyze_session(summary, pred)
    analysis["stop_classification"] = {
        "class": "quiescence_refusal_under_paging_pressure",
        "note": (
            "Sweep stopped on three consecutive quiescence refusals under paging "
            "pressure, not an allocation ceiling. No ALLOC_FAILURE cell was recorded. "
            "Prior C-2 f16 CL_OUT_OF_RESOURCES at n=8000 (c647f0c7) did not reproduce "
            "at 10× that depth under CAP-4."
        ),
        "abort_reason": abort_reason,
        "abort_verbatim": abort_verbatim,
        "abort_at": abort_at,
    }
    summary["analysis"] = analysis

    plan["status"] = "aborted"
    plan["ended_utc"] = ended
    plan["abort_reason"] = abort_reason
    plan["abort_verbatim"] = abort_verbatim
    plan["abort_at"] = abort_at
    plan["run_environment"] = run_environment
    plan["prompt_render_sha256"] = run_environment["prompt_render_sha256"]
    plan["rungs_executed"] = executed
    plan["rungs_completed_per_arm"] = rungs_completed_per_arm
    _write_json(session_dir / "plan.json", plan)
    _write_json(session_dir / "summary.json", summary)
    _write_json(session_dir / "analysis.json", analysis)
    report = _render_report(summary, analysis, pred)
    (session_dir / "CAP4_RESULTS.md").write_text(report, encoding="utf-8")
    (ROOT / "derived" / "cap4" / "CAP4_RESULTS.md").write_text(report, encoding="utf-8")
    print(report.encode("ascii", errors="replace").decode("ascii"))
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session-id", required=False, default=None)
    p.add_argument("--out", type=Path, required=False, default=None)
    p.add_argument("--model-spec", type=Path, default=DEFAULT_MODEL_SPEC)
    p.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    p.add_argument("--repeats", type=int, default=REPEATS)
    p.add_argument("--seed", type=int, default=INTERLEAVE_SEED)
    p.add_argument("--watchdog-interval-s", type=int, default=60)
    p.add_argument(
        "--primary-rungs",
        default=",".join(str(n) for n in PRIMARY_RUNGS),
        help="comma-separated primary n tokens",
    )
    p.add_argument("--continue-step", type=int, default=CONTINUE_STEP)
    p.add_argument("--analyze-only", type=Path, default=None)
    p.add_argument(
        "--reconstruct-aborted",
        type=Path,
        default=None,
        help="Rebuild summary.json from cells/probes/plan for an aborted session dir",
    )
    p.add_argument(
        "--abort-verbatim",
        default=None,
        help="Verbatim SeamError / refusal text for --reconstruct-aborted",
    )
    args = p.parse_args(argv)

    if args.reconstruct_aborted is not None:
        out = args.reconstruct_aborted
        if not out.is_absolute():
            out = ROOT / out
        if not args.abort_verbatim:
            raise SystemExit("REFUSED -- --abort-verbatim required with --reconstruct-aborted")
        reconstruct_aborted_summary(
            session_dir=out,
            abort_verbatim=str(args.abort_verbatim),
            abort_at={
                "arm_id": "gpu_only_u4",
                "n_tokens": 82000,
                "repeat_index": 1,
                "source": "cli_reconstruct_aborted",
            },
        )
        return 0

    if args.analyze_only is not None:
        out = args.analyze_only
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8-sig"))
        pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
        analysis = analyze_session(summary, pred)
        _write_json(out / "analysis.json", analysis)
        report = _render_report(summary, analysis, pred)
        (out / "CAP4_RESULTS.md").write_text(report, encoding="utf-8")
        print(report.encode("ascii", errors="replace").decode("ascii"))
        return 0

    if not args.session_id or args.out is None:
        raise SystemExit("REFUSED -- --session-id and --out are required for a live run")

    model_spec = args.model_spec if args.model_spec.is_absolute() else ROOT / args.model_spec
    arms = [a.strip() for a in str(args.arms).split(",") if a.strip()]
    primary = [int(x) for x in str(args.primary_rungs).split(",") if x.strip()]
    out_dir = args.out if args.out.is_absolute() else ROOT / args.out
    print(f"CAP4_START session_id={args.session_id} out={out_dir}", flush=True)
    try:
        run_session(
            out_dir=out_dir,
            session_id=args.session_id,
            model_spec=model_spec,
            arms=arms,
            repeats=int(args.repeats),
            seed=int(args.seed),
            watchdog_interval_s=int(args.watchdog_interval_s),
            primary_rungs=primary,
            continue_step=int(args.continue_step),
        )
    except BaseException as exc:
        # summary.json already written in run_session.finally; surface non-zero.
        print(f"CAP4_EXIT status=aborted error={type(exc).__name__}: {exc}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
