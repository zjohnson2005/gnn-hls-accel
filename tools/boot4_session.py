"""Shared boot-4 measurement session: gates, canary, per-point files, seal.

The runners call this module. It does not open a preregistration or an amendment.
Warm points are n_cached 12000, 24000, and 46000, delta text of 183 tokens, three
turn-2 repeats. Decode length comes from configs/delta_n.yaml acceptance.max_new_tokens.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STUB_MARK = "measurement body is not started"
N_CACHED = (12000, 24000, 46000)
DELTA_TOKENS = 183
TURN2_REPEATS = 3
WARM_PLANNED_PROBES = 4
SMOKE_N_CACHED = 64
SMOKE_DELTA_TOKENS = 8
DECODE_N = (2000, 4000, 8000)
DECODE_REPEATS = 3
SMOKE_DECODE_N = 32


def runner_body_is_stub(path: Path) -> bool:
    return STUB_MARK in path.read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    """JSON written by this process or by PowerShell. Accepts a UTF-8 BOM."""
    from seam.json_io import load_json

    return load_json(path)


def advantage_percent(*, median_f16: float, median_other: float) -> float:
    """(median_other - median_f16) / median_other * 100. Lower TTFT is the advantage."""
    if median_other == 0:
        raise ValueError("median_other is 0")
    return (float(median_other) - float(median_f16)) / float(median_other) * 100.0


def _utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_gates() -> dict[str, Any]:
    from seam.measurement_gates import evaluate_measurement_gates

    report = evaluate_measurement_gates(ROOT)
    if not report.all_passed:
        raise SystemExit("REFUSED -- gates: " + "; ".join(report.refusal_reasons))
    return report.to_dict()


def load_harness(model_spec: Path) -> dict[str, Any]:
    from seam.config import resolve_config
    from seam.model_provenance import load_local_spec
    from seam.tools.delta_n import _DELTA_N_PATH, _MEASUREMENT_PATH, _PLATFORM_PATH

    spec_path = model_spec if model_spec.is_absolute() else ROOT / model_spec
    resolved = resolve_config(
        [ROOT / _PLATFORM_PATH, ROOT / _MEASUREMENT_PATH, ROOT / _DELTA_N_PATH],
        repo_root=ROOT,
    )
    cfg = resolved.data
    loaded = load_local_spec(spec_path)
    model_dir = str(loaded["ir_dir"])
    if not Path(model_dir).is_dir():
        raise SystemExit(f"REFUSED -- model IR missing: {model_dir}")
    if "arms" not in cfg:
        raise SystemExit("REFUSED -- resolved config missing arms")
    if "topology" not in cfg or "p_cpus" not in cfg["topology"]:
        raise SystemExit("REFUSED -- resolved config missing topology.p_cpus")
    acceptance = cfg.get("acceptance") or {}
    if acceptance.get("max_new_tokens") is None:
        raise SystemExit("REFUSED -- acceptance.max_new_tokens missing")
    return {
        "cfg": cfg,
        "model_spec": spec_path,
        "model_name": str(loaded.get("name") or spec_path.stem),
        "model_dir": model_dir,
        "arms": {a["id"]: a for a in cfg["arms"]},
        "p_cpus": [int(c) for c in cfg["topology"]["p_cpus"]],
        "filler_unit": str(cfg["ladder"]["filler_unit"]),
        "max_new_tokens": int(acceptance["max_new_tokens"]),
    }


def _child_spec(harness: dict[str, Any], arm_id: str, work: Path) -> dict[str, Any]:
    from seam.tools.ceiling_a import _child_spec_for_arm

    arm = harness["arms"].get(arm_id)
    if arm is None:
        raise SystemExit(f"REFUSED -- unknown arm {arm_id}")
    unused = work / "prompt_unused.txt"
    unused.write_text("unused\n", encoding="utf-8")
    spec = _child_spec_for_arm(
        cfg=harness["cfg"],
        arm=arm,
        model_dir=harness["model_dir"],
        prompt={"path": str(unused)},
        p_cpus=harness["p_cpus"],
    )
    spec["filler_unit"] = harness["filler_unit"]
    return spec


def _canary_model(specs: list[Path]) -> Path:
    for spec in specs:
        if "Qwen3-4B-int4-ov" in spec.name:
            return spec if spec.is_absolute() else ROOT / spec
    raise SystemExit("REFUSED -- canary model spec Qwen3-4B-int4-ov is not in --model-spec")


def _open_canary(
    *,
    model_spec: Path,
    work: Path,
    plan_path: Path,
    planned: int,
) -> Any:
    from tools.ttft_slo_canary import CanaryBudgetRefuse, TtftSloCanaryGuard

    try:
        guard = TtftSloCanaryGuard(
            root=ROOT,
            model_spec=model_spec,
            work_dir=work / "canaries",
            plan_path=plan_path,
            planned_probe_count=int(planned),
            allow_unguarded=False,
            discard_warmup=True,
        )
    except CanaryBudgetRefuse as exc:
        raise SystemExit(f"REFUSED -- {exc.detail}") from exc
    return guard


def _point_failure(record: dict[str, Any]) -> dict[str, Any]:
    from tools.run_c1_ceiling import classify_c1_failure

    child = record.get("result") or record
    return classify_c1_failure(child)


def cell_status(points: list[dict[str, Any]]) -> str:
    """A recorded failure_kind is data. An unexplained non-pass is a harness failure."""
    saw_kind = False
    unexplained = False
    for point in points:
        if point.get("failure_kind"):
            saw_kind = True
        elif point.get("outcome") not in (None, "pass"):
            unexplained = True
        repeats = point.get("repeats")
        if isinstance(repeats, list):
            for repeat in repeats:
                if repeat.get("failure_kind"):
                    saw_kind = True
                elif repeat.get("outcome") not in (None, "pass"):
                    unexplained = True
            if point.get("median_decode_tok_s") is None and not any(
                item.get("failure_kind") for item in repeats
            ):
                unexplained = True
    if saw_kind:
        return "partial"
    if unexplained:
        return "failed"
    return "complete"


def cell_exit_code(status: str) -> int:
    """Point data continues the boot. Guard and harness statuses stop it."""
    if status in {"complete", "partial"}:
        return 0
    return 1


def _publish_cell_status(status: str) -> None:
    import os

    path = os.environ.get("SEAM_CELL_STATUS_PATH")
    if not path:
        return
    Path(path).write_text(status + "\n", encoding="utf-8")


def _median(values: list[float]) -> float:
    if not values:
        raise ValueError("median of an empty sample")
    return float(statistics.median(values))


def seal_session(session_dir: Path) -> Path:
    """Copy plan, summary, and point files into a write-once sealed_<id> directory."""
    import os

    if os.environ.get("SEAM_REHEARSAL") == "1":
        raise SystemExit("REFUSED -- rehearsal does not seal")
    summary_path = session_dir / "summary.json"
    summary = read_json(summary_path)
    sid = str(summary["session_id"])
    dest = session_dir.parent / f"sealed_{sid}"
    if dest.exists():
        raise SystemExit(f"REFUSED -- seal destination exists: {dest}")
    dest.mkdir()
    rels: list[str] = []
    for name in ("plan.json", "summary.json"):
        shutil.copy2(session_dir / name, dest / name)
        rels.append(name)
    points = session_dir / "points"
    if points.is_dir():
        (dest / "points").mkdir()
        for path in sorted(points.glob("*.json")):
            shutil.copy2(path, dest / "points" / path.name)
            rels.append(f"points/{path.name}")
    manifest = {rel: hashlib.sha256((dest / rel).read_bytes()).hexdigest() for rel in rels}
    _write(dest / "manifest.sha256.json", manifest)
    (dest / ".sealed").write_text("sealed\n", encoding="utf-8")
    return dest


def _finish(
    *,
    guard: Any,
    out_dir: Path,
    summary: dict[str, Any],
    plan: dict[str, Any],
) -> int:
    from tools.ttft_slo_canary import CanaryUnarmedSealRefuse

    summary["canaries"] = list(guard.canaries)
    summary["canary"] = guard.plan_fragment()
    try:
        summary["canary_finalize"] = guard.finalize_or_refuse()
    except CanaryUnarmedSealRefuse as exc:
        summary["status"] = "REFUSED_CANARY"
        summary["ended_utc"] = _utc()
        _write(out_dir / "summary.json", summary)
        plan["status"] = "REFUSED_CANARY"
        _write(out_dir / "plan.json", plan)
        raise SystemExit(f"REFUSED -- {exc}") from exc
    summary["ended_utc"] = _utc()
    summary["sealed_dir"] = str(out_dir.parent / f"sealed_{summary['session_id']}")
    _write(out_dir / "summary.json", summary)
    plan["status"] = summary["status"]
    _write(out_dir / "plan.json", plan)
    sealed = seal_session(out_dir)
    print(json.dumps({"event": "sealed", "dir": str(sealed)}, sort_keys=True), flush=True)
    _publish_cell_status(str(summary["status"]))
    return cell_exit_code(str(summary["status"]))


def run_warm_smoke(*, arm: str, model_spec: Path) -> int:
    from seam.tools.delta_n import run_child

    harness = load_harness(model_spec)
    with tempfile.TemporaryDirectory(prefix="boot4-warm-smoke-") as tmp:
        work = Path(tmp)
        spec = _child_spec(harness, arm, work)
        spec["resident_two_turn"] = True
        spec["n_cached"] = SMOKE_N_CACHED
        spec["delta_tokens"] = SMOKE_DELTA_TOKENS
        spec["turn2_repeats"] = 1
        spec["turn1_max_new_tokens"] = 1
        spec["turn2_max_new_tokens"] = 1
        record = run_child(
            root=ROOT,
            work_dir=work,
            spec=spec,
            timeout_s=float(harness["cfg"]["generation"]["timeout_s"]),
            tag="smoke",
        )
    generation = (record.get("child") or {}).get("generation") or {}
    turn2 = generation.get("turn2") or []
    print(
        json.dumps(
            {
                "event": "warm_smoke",
                "arm": arm,
                "outcome": record.get("outcome"),
                "n_cached": SMOKE_N_CACHED,
                "delta_tokens": SMOKE_DELTA_TOKENS,
                "turn1_prefill_s": (generation.get("turn1") or {}).get("prefill_s"),
                "turn1_prompt_tokens": (generation.get("turn1") or {}).get(
                    "prompt_tokens_reported"
                ),
                "turn2_prefill_s": (turn2[0].get("prefill_s") if turn2 else None),
                "turn2_prompt_tokens": (turn2[0].get("prompt_tokens_reported") if turn2 else None),
                "failure_mode": record.get("failure_mode"),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if record.get("outcome") == "pass" else 1


def run_decode_smoke(*, arm: str, model_spec: Path) -> int:
    from seam.tools.delta_n import run_child

    harness = load_harness(model_spec)
    with tempfile.TemporaryDirectory(prefix="boot4-decode-smoke-") as tmp:
        work = Path(tmp)
        spec = _child_spec(harness, arm, work)
        spec["build_exact_n"] = SMOKE_DECODE_N
        spec["prompt_salt"] = "s"
        spec["max_new_tokens"] = harness["max_new_tokens"]
        spec["min_new_tokens"] = harness["max_new_tokens"]
        spec["decode_span_rate"] = True
        record = run_child(
            root=ROOT,
            work_dir=work,
            spec=spec,
            timeout_s=float(harness["cfg"]["generation"]["timeout_s"]),
            tag="smoke",
        )
    generation = (record.get("child") or {}).get("generation") or {}
    print(
        json.dumps(
            {
                "event": "decode_smoke",
                "arm": arm,
                "model": harness["model_name"],
                "outcome": record.get("outcome"),
                "n": SMOKE_DECODE_N,
                "max_new_tokens": harness["max_new_tokens"],
                "prefill_s": generation.get("prefill_s"),
                "decode_tok_s": generation.get("decode_tok_s"),
                "completion_tokens_reported": generation.get("completion_tokens_reported"),
                "decode_span": generation.get("decode_span"),
                "failure_mode": record.get("failure_mode"),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if record.get("outcome") == "pass" else 1


def _warm_advantages(out_dir: Path, this_summary: dict[str, Any]) -> dict[str, Any] | None:
    by_arm: dict[str, dict[str, float]] = {}
    parent = out_dir.parent
    if parent.is_dir():
        for path in parent.glob("*/summary.json"):
            if path.parent.name.startswith("sealed_"):
                continue
            doc = read_json(path)
            if doc.get("kind") != "warm_kv":
                continue
            arm = doc.get("arm")
            medians = doc.get("turn2_median_prefill_s")
            if isinstance(arm, str) and isinstance(medians, dict) and medians:
                by_arm[arm] = {str(k): float(v) for k, v in medians.items()}
    arm = this_summary.get("arm")
    medians = this_summary.get("turn2_median_prefill_s")
    if isinstance(arm, str) and isinstance(medians, dict) and medians:
        by_arm[arm] = {str(k): float(v) for k, v in medians.items()}
    needed = ("gpu_only_f16", "gpu_only_u8", "gpu_only_u4")
    if any(name not in by_arm for name in needed):
        return None
    points = sorted(set(by_arm["gpu_only_f16"]))
    out: dict[str, Any] = {}
    for n in points:
        f16 = by_arm["gpu_only_f16"][n]
        out[n] = {
            "median_f16": f16,
            "median_u8": by_arm["gpu_only_u8"][n],
            "median_u4": by_arm["gpu_only_u4"][n],
            "f16_advantage_percent_vs_u8": advantage_percent(
                median_f16=f16, median_other=by_arm["gpu_only_u8"][n]
            ),
            "f16_advantage_percent_vs_u4": advantage_percent(
                median_f16=f16, median_other=by_arm["gpu_only_u4"][n]
            ),
        }
    return out


def run_warm(*, arm: str, model_spec: Path, session_id: str, out_dir: Path) -> int:
    from seam.tools.delta_n import measured_repeat
    from tools.ttft_slo_canary import CanaryDriftAbort

    gates = require_gates()
    harness = load_harness(model_spec)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan: dict[str, Any] = {
        "kind": "warm_kv",
        "session_id": session_id,
        "started_utc": _utc(),
        "arm": arm,
        "model_spec": str(harness["model_spec"]),
        "model_name": harness["model_name"],
        "n_cached": list(N_CACHED),
        "delta_tokens": DELTA_TOKENS,
        "turn2_repeats": TURN2_REPEATS,
        "turn1_max_new_tokens": 1,
        "turn2_max_new_tokens": 1,
        "residency": "RESIDENT",
        "executed_points": len(N_CACHED),
        "planned_probe_count": WARM_PLANNED_PROBES,
        "canary_budget_note": (
            "planned_probe_count is 4 so floor(planned/(C+1)) >= 1 with C=3. "
            "The cell executes the two n_cached points."
        ),
        "gates": gates,
        "status": "running",
    }
    plan_path = out_dir / "plan.json"
    _write(plan_path, plan)
    guard = _open_canary(
        model_spec=_canary_model([harness["model_spec"]]),
        work=out_dir / "work",
        plan_path=plan_path,
        planned=WARM_PLANNED_PROBES,
    )
    plan["canary"] = guard.plan_fragment()
    _write(plan_path, plan)
    points: list[dict[str, Any]] = []
    probes_log: list[dict[str, Any]] = []
    try:
        guard.opening()
        for n_cached in N_CACHED:
            work = out_dir / "work"
            spec = _child_spec(harness, arm, work)
            spec["resident_two_turn"] = True
            spec["n_cached"] = int(n_cached)
            spec["delta_tokens"] = DELTA_TOKENS
            spec["turn2_repeats"] = TURN2_REPEATS
            spec["turn1_max_new_tokens"] = 1
            spec["turn2_max_new_tokens"] = 1
            measured = measured_repeat(
                root=ROOT,
                cfg=harness["cfg"],
                p_cpus=harness["p_cpus"],
                work_dir=work,
                child_spec=spec,
                label=f"warm-{arm}-n{n_cached}",
                tag=f"n{n_cached}",
            )
            child = measured["result"]
            classified = _point_failure(child)
            generation = (child.get("child") or {}).get("generation") or {}
            turn2 = list(generation.get("turn2") or [])
            prefills = [
                float(item["prefill_s"]) for item in turn2 if item.get("prefill_s") is not None
            ]
            point = {
                "arm": arm,
                "n_cached": int(n_cached),
                "rung": int(n_cached),
                "outcome": child.get("outcome"),
                "failure_kind": classified.get("failure_kind"),
                "failure_mode": child.get("failure_mode"),
                "memory": classified.get("memory") or {},
                "turn1_prefill_s": (generation.get("turn1") or {}).get("prefill_s"),
                "turn2_prefill_s": prefills,
                "turn2_median_prefill_s": _median(prefills)
                if len(prefills) == TURN2_REPEATS
                else None,
                "turn2_prompt_tokens_reported": [
                    item.get("prompt_tokens_reported") for item in turn2
                ],
            }
            _write(out_dir / "points" / f"n{n_cached}.json", point)
            points.append(point)
            probes_log.append({"wall_s": child.get("parent_wall_s")})
            guard.after_probe(probes_log)
    except CanaryDriftAbort as exc:
        summary = {
            "kind": "warm_kv",
            "session_id": session_id,
            "arm": arm,
            "status": "FAIL_CANARY_DRIFT",
            "abort_reason": str(exc.detail),
            "points": points,
            "canaries": list(guard.canaries),
        }
        _write(out_dir / "summary.json", summary)
        raise SystemExit(f"REFUSED -- FAIL_CANARY_DRIFT: {exc.detail}") from exc

    medians = {
        str(point["n_cached"]): point["turn2_median_prefill_s"]
        for point in points
        if point.get("turn2_median_prefill_s") is not None
    }
    status = cell_status(points)
    summary = {
        "kind": "warm_kv",
        "session_id": session_id,
        "arm": arm,
        "model_name": harness["model_name"],
        "status": status,
        "points": points,
        "turn2_median_prefill_s": medians,
        "delta_tokens": DELTA_TOKENS,
        "n_cached": list(N_CACHED),
    }
    summary["f16_advantage_percent"] = _warm_advantages(out_dir, summary)
    return _finish(guard=guard, out_dir=out_dir, summary=summary, plan=plan)


def run_decode(
    *,
    arm: str,
    model_specs: list[Path],
    session_id: str,
    out_dir: Path,
) -> int:
    from seam.tools.delta_n import measured_repeat
    from tools.ttft_slo_canary import CanaryDriftAbort

    if len(model_specs) < 2:
        raise SystemExit("REFUSED -- decode measurement requires both model specs")
    gates = require_gates()
    loaded = [load_harness(spec) for spec in model_specs]
    out_dir.mkdir(parents=True, exist_ok=True)
    planned = len(loaded) * len(DECODE_N) * DECODE_REPEATS
    plan: dict[str, Any] = {
        "kind": "decode_match",
        "session_id": session_id,
        "started_utc": _utc(),
        "arm": arm,
        "models": [item["model_name"] for item in loaded],
        "n": list(DECODE_N),
        "repeats": DECODE_REPEATS,
        "max_new_tokens": loaded[0]["max_new_tokens"],
        "min_new_tokens": loaded[0]["max_new_tokens"],
        "ignore_eos": True,
        "decode_tok_s": "63 / (t_last - t_first)",
        "planned_probe_count": planned,
        "gates": gates,
        "status": "running",
    }
    plan_path = out_dir / "plan.json"
    _write(plan_path, plan)
    guard = _open_canary(
        model_spec=_canary_model([item["model_spec"] for item in loaded]),
        work=out_dir / "work",
        plan_path=plan_path,
        planned=planned,
    )
    plan["canary"] = guard.plan_fragment()
    _write(plan_path, plan)
    points: list[dict[str, Any]] = []
    probes_log: list[dict[str, Any]] = []
    try:
        guard.opening()
        for harness in loaded:
            for n_tokens in DECODE_N:
                repeats: list[dict[str, Any]] = []
                for repeat in range(DECODE_REPEATS):
                    work = out_dir / "work"
                    spec = _child_spec(harness, arm, work)
                    spec["build_exact_n"] = int(n_tokens)
                    spec["prompt_salt"] = f"n{n_tokens}"
                    spec["max_new_tokens"] = harness["max_new_tokens"]
                    spec["min_new_tokens"] = harness["max_new_tokens"]
                    spec["decode_span_rate"] = True
                    measured = measured_repeat(
                        root=ROOT,
                        cfg=harness["cfg"],
                        p_cpus=harness["p_cpus"],
                        work_dir=work,
                        child_spec=spec,
                        label=f"decode-{harness['model_name']}-n{n_tokens}-r{repeat}",
                        tag=f"{harness['model_name']}_n{n_tokens}_r{repeat}",
                    )
                    child = measured["result"]
                    generation = (child.get("child") or {}).get("generation") or {}
                    repeats.append(
                        {
                            "repeat": repeat,
                            "outcome": child.get("outcome"),
                            "failure_kind": _point_failure(child).get("failure_kind"),
                            "prefill_s": generation.get("prefill_s"),
                            "decode_tok_s": generation.get("decode_tok_s"),
                            "completion_tokens_reported": generation.get(
                                "completion_tokens_reported"
                            ),
                            "decode_span": generation.get("decode_span"),
                        }
                    )
                    probes_log.append({"wall_s": child.get("parent_wall_s")})
                    guard.after_probe(probes_log)
                rates = [
                    float(item["decode_tok_s"])
                    for item in repeats
                    if item.get("decode_tok_s") is not None and item.get("outcome") == "pass"
                ]
                point = {
                    "model": harness["model_name"],
                    "arm": arm,
                    "n": int(n_tokens),
                    "repeats": repeats,
                    "median_decode_tok_s": _median(rates) if len(rates) == DECODE_REPEATS else None,
                }
                safe_name = harness["model_name"].replace(" ", "_")
                _write(out_dir / "points" / f"{safe_name}_n{n_tokens}.json", point)
                points.append(point)
    except CanaryDriftAbort as exc:
        summary = {
            "kind": "decode_match",
            "session_id": session_id,
            "arm": arm,
            "status": "FAIL_CANARY_DRIFT",
            "abort_reason": str(exc.detail),
            "points": points,
            "canaries": list(guard.canaries),
        }
        _write(out_dir / "summary.json", summary)
        raise SystemExit(f"REFUSED -- FAIL_CANARY_DRIFT: {exc.detail}") from exc

    status = cell_status(points)
    summary = {
        "kind": "decode_match",
        "session_id": session_id,
        "arm": arm,
        "status": status,
        "models": [item["model_name"] for item in loaded],
        "n": list(DECODE_N),
        "max_new_tokens": loaded[0]["max_new_tokens"],
        "points": points,
        "median_decode_tok_s": {
            f"{point['model']}:{point['n']}": point.get("median_decode_tok_s") for point in points
        },
    }
    return _finish(guard=guard, out_dir=out_dir, summary=summary, plan=plan)


def new_session_id() -> str:
    return str(uuid.uuid4())
