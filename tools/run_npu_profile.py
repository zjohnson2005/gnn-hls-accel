"""NPU-1 and NPU-2 cells. This runner does not open a preregistration.

NPU-2 loads the int8 IR and stops. An int8 load is infeasible and is never
generated. NPU-1 loads the int4 IR once per requested NPUW_LLM_MAX_PROMPT_LEN.
The length is a load-time setting. At each loaded setting the runner bisects
the 10 s TTFT SLO from 64 up to that setting, records decode tok/s at the
highest passing rung, and records MAX_PROMPT_LEN + 1 as infeasible without
generating it.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.backends.local_openvino import (  # noqa: E402
    _make_ttft_streamer,
    _text_from_generate_result,
    resolve_ttft_ns,
)
from seam.model_provenance import load_local_spec  # noqa: E402
from seam.npu_validity import decide_npu_cell  # noqa: E402
from seam.tools.boot4_text import rendered_exact_prompt  # noqa: E402
from tools.run_c1_ceiling import classify_c1_failure  # noqa: E402

SLO_S = 10.0
SHORT_PROMPT_TOKENS = 64
NPU_SERIES_TOKENS = 400
REPEATS = 3
MAX_NEW_TOKENS = 8
SESSION_BUDGET_S = 7200
# XPS feasibility pilot, 2026-10-03. Not a measurement. The prefill figure is
# one 64-token generate. The load figure is the ceiling of that pilot's walls.
PILOT_PREFILL_S_AT_64 = 1.4136199
PILOT_LOAD_S = 78.0
LADDER_START = (1024, 2048, 4096, 8192)


def error_class_for(message: str) -> str | None:
    labeled = classify_c1_failure(
        {
            "outcome": "fail",
            "failure_mode": message,
            "exception": {"type": "RuntimeError", "message": message},
        }
    )
    kind = labeled.get("error_class")
    return None if kind is None else str(kind)


def npu2_load_record(load_error: str | None) -> dict[str, Any]:
    """Int8 stops at load. ``generated`` stays false even when the load succeeds."""
    decision = decide_npu_cell(
        output_text="",
        gpu_output_text="",
        prompt_text="",
        max_prompt_len=None,
        weight_precision="int8",
        prompt_tokens=0,
    )
    decision["generated"] = False
    decision["load_error"] = load_error
    decision["error_class"] = error_class_for(load_error) if load_error else None
    return decision


def ir_quantization(spec: dict[str, Any]) -> dict[str, Any]:
    """The pinned IR is group-wise INT4_SYM. Channel-wise is a later arm."""
    pub = spec.get("publisher_quantization")
    if not isinstance(pub, dict):
        pub = {}
    group = pub.get("group_size")
    mode = pub.get("mode")
    return {
        "mode": mode,
        "group_size": group,
        "ratio": pub.get("ratio"),
        "channel_wise": group == -1,
        "ir_note": (
            "INT4_SYM group_size 128 is group-wise, not channel-wise. "
            "A channel-wise IR is a later arm and is parked until a conversion is approved."
        ),
    }


def process_rss_mb() -> dict[str, Any]:
    try:
        import psutil
    except Exception as exc:
        return {"rss_mb": None, "error": f"{type(exc).__name__}: {exc}"}
    try:
        rss = psutil.Process().memory_info().rss / (1024.0 * 1024.0)
    except Exception as exc:
        return {"rss_mb": None, "error": f"{type(exc).__name__}: {exc}"}
    return {"rss_mb": rss, "error": None}


def median_number(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _timed_slo_miss(row: dict[str, Any]) -> bool:
    """A rung whose recorded prefills miss the SLO.

    A null prefill is a refused or infeasible cell. It is not a latency miss.
    """
    if row.get("slo_pass"):
        return False
    prefills = row.get("prefill_s")
    if isinstance(prefills, list):
        return bool(prefills) and all(isinstance(value, (int, float)) for value in prefills)
    return isinstance(prefills, (int, float))


def bind_setting(*, load_ok: bool, cap: int, rungs: list[dict[str, Any]]) -> dict[str, Any]:
    """TOOLCHAIN_CAP when the highest feasible rung passes the SLO.

    LATENCY only when a timed rung misses the SLO. An infeasible or refused
    rung, including MAX_PROMPT_LEN itself when it was never timed, does not
    count. ``cap`` is the loaded setting and is not itself a pass.
    """
    del cap
    if not load_ok:
        return {"binding": "LOAD_FAIL", "ttft_limit_n": None, "decode_tok_s_at_limit": None}
    passing = [row for row in rungs if row.get("slo_pass")]
    chosen = max(passing, key=lambda row: int(row["n_tokens"])) if passing else None
    binding = "LATENCY" if any(_timed_slo_miss(row) for row in rungs) else "TOOLCHAIN_CAP"
    rates: list[float] = []
    if chosen is not None:
        rates = [
            float(value)
            for value in chosen.get("decode_tok_s") or []
            if isinstance(value, (int, float))
        ]
    return {
        "binding": binding,
        "ttft_limit_n": None if chosen is None else int(chosen["n_tokens"]),
        "decode_tok_s_at_limit": median_number(rates),
    }


def setting_estimate_s(
    high: int,
    *,
    low: int = SHORT_PROMPT_TOKENS,
    resolution: int = 64,
    repeats: int = REPEATS,
) -> int:
    """Scheduling bound. Prefill at ``high`` is the 64-token pilot scaled linearly."""
    from tools.ttft_slo_canary import estimate_bisect_planned_probes

    probes = estimate_bisect_planned_probes(
        n_arms=1,
        low=low,
        high=high,
        resolution=resolution,
        repeats=repeats,
    )
    per_probe_s = (PILOT_PREFILL_S_AT_64 * (high / float(SHORT_PROMPT_TOKENS))) + SLO_S
    return math.ceil(PILOT_LOAD_S + probes * per_probe_s)


def scheduling_plan() -> dict[str, Any]:
    rows = [{"max_prompt_len": n, "estimate_s": setting_estimate_s(n)} for n in LADDER_START]
    total = sum(int(row["estimate_s"]) for row in rows)
    return {
        "session_budget_s": SESSION_BUDGET_S,
        "settings": rows,
        "sum_s": total,
        "fits_one_session": total <= SESSION_BUDGET_S,
        "split": "one detached session per MAX_PROMPT_LEN",
        "tail_start": LADDER_START[-1] * 2,
        "pilot_prefill_s_at_64": PILOT_PREFILL_S_AT_64,
        "pilot_load_s": PILOT_LOAD_S,
        "pilot_note": (
            "XPS feasibility pilot 2026-10-03, not a measurement. "
            "Longer-prompt prefill is extrapolated linearly from the 64-token pilot."
        ),
    }


def over_max_record(max_prompt_len: int) -> dict[str, Any]:
    """MAX_PROMPT_LEN + 1 is infeasible. The caller must not generate."""
    length = max_prompt_len + 1
    decision = decide_npu_cell(
        output_text="",
        gpu_output_text="",
        prompt_text="",
        max_prompt_len=max_prompt_len,
        weight_precision="int4",
        prompt_tokens=length,
    )
    decision["generated"] = False
    decision["error_class"] = None
    return decision


def rung_record(
    *,
    n_tokens: int,
    max_prompt_len: int,
    npu_text: str,
    gpu_text: str,
    prefill_s: float | None,
    decode_tok_s: float | None,
    prompt_tokens: int | None = None,
    output_tokens: list[Any] | None = None,
) -> dict[str, Any]:
    decision = decide_npu_cell(
        output_text=npu_text,
        gpu_output_text=gpu_text,
        prompt_text="",
        max_prompt_len=max_prompt_len,
        weight_precision="int4",
        prompt_tokens=prompt_tokens if prompt_tokens is not None else n_tokens,
        output_tokens=output_tokens,
    )
    decision["n_tokens"] = n_tokens
    decision["prefill_s"] = prefill_s if decision["timed"] else None
    decision["decode_tok_s"] = decode_tok_s if decision["timed"] else None
    decision["generated"] = True
    decision["error_class"] = None
    return decision


def canary_marker(fragment: dict[str, Any] | None) -> dict[str, bool]:
    """Any unarmed canary writes UNGUARDED true. An armed gate writes false."""
    armed = False
    if isinstance(fragment, dict) and not fragment.get("smoke_skip"):
        gate = fragment.get("canary_gate")
        if isinstance(gate, dict):
            armed = bool(gate.get("armed"))
        elif "armed" in fragment:
            armed = bool(fragment.get("armed"))
    return {"armed": armed, "UNGUARDED": not armed}


def summarize_rung(n_tokens: int, repeats: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-rung prefill and the realized prompt length, including refused rungs."""

    def realized(row: dict[str, Any]) -> int | None:
        if isinstance(row.get("prompt_length"), int):
            return int(row["prompt_length"])
        if isinstance(row.get("prompt_tokens"), int):
            return int(row["prompt_tokens"])
        return None

    return {
        "n_tokens": n_tokens,
        "repeats": repeats,
        "slo_pass": slo_pass(repeats),
        "prefill_s": [row.get("prefill_s") for row in repeats],
        "decode_tok_s": [row.get("decode_tok_s") for row in repeats],
        "prompt_tokens": [realized(row) for row in repeats],
        "exact_match_vs_gpu": [row.get("exact_match_vs_gpu") for row in repeats],
        "timed": [row.get("timed") for row in repeats],
        "reason": [row.get("reason") for row in repeats],
    }


def new_npu_series(derivation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Non-gating n=400 samples on the loaded NPU pipeline.

    The GPU canary is the guard. This series only builds an NPU pool.
    """
    return {
        "label": "npu_canary_series",
        "gates": False,
        "device": "NPU",
        "n_tokens": NPU_SERIES_TOKENS,
        "n_derivation": derivation,
        "samples": [],
    }


def stamp_canary(
    plan: dict[str, Any],
    summary: dict[str, Any],
    guard: Any,
    series: dict[str, Any] | None = None,
) -> dict[str, bool]:
    """Write the guard's armed bit and UNGUARDED onto the plan and the summary."""
    fragment = guard.plan_fragment()
    marker = canary_marker(fragment)
    plan["canary"] = fragment
    plan["armed"] = marker["armed"]
    plan["UNGUARDED"] = marker["UNGUARDED"]
    summary["canary"] = fragment
    summary["canaries"] = list(guard.canaries)
    summary["armed"] = marker["armed"]
    summary["UNGUARDED"] = marker["UNGUARDED"]
    if series is not None:
        series["n_derivation"] = guard.n_derivation
        plan["npu_canary_series"] = series
        summary["npu_canary_series"] = series
    return marker


def drive_npu_rung(
    n_tokens: int,
    *,
    repeats: int,
    one_repeat: Callable[[int], dict[str, Any]],
    guard: Any | None,
    probes_log: list[dict[str, Any]],
    on_interval: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """One rung. ``after_probe`` runs once per repeat, as in the GPU ceiling runner.

    The NPU n=400 series is recorded when that call fires a canary, and its
    result is not a gate.
    """
    rows: list[dict[str, Any]] = []
    for _ in range(repeats):
        started = time.perf_counter()
        row = one_repeat(n_tokens)
        row["wall_s"] = time.perf_counter() - started
        rows.append(row)
        if guard is None:
            continue
        probes_log.append(row)
        canaries_before = len(guard.canaries)
        guard.after_probe(probes_log)
        if on_interval is not None and len(guard.canaries) > canaries_before:
            on_interval(len(probes_log) - 1)
    return summarize_rung(n_tokens, rows)


def slo_pass(repeats: list[dict[str, Any]], slo_s: float = SLO_S) -> bool:
    timed = [row for row in repeats if row.get("timed") and row.get("prefill_s") is not None]
    if len(timed) != len(repeats) or not timed:
        return False
    values = sorted(float(row["prefill_s"]) for row in timed)
    mid = values[len(values) // 2]
    return mid <= slo_s


def slo_bisect(
    low: int,
    high: int,
    resolution: int,
    probe: Callable[[int], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Visit  ``low``, ``high``, then midpoints until the gap is ``resolution``.

    ``probe`` returns a rung summary with ``slo_pass``. Nothing above ``high``
    is visited; the over-max cell is separate.
    """
    if resolution < 1:
        raise SystemExit("REFUSED -- resolution must be positive")
    if high < low:
        raise SystemExit("REFUSED -- high is below low")
    visited: list[dict[str, Any]] = []

    def visit(n_tokens: int) -> bool:
        row = probe(n_tokens)
        visited.append(row)
        return bool(row["slo_pass"])

    lo_ok = visit(low)
    hi_ok = lo_ok if high == low else visit(high)
    lo, hi = low, high
    if not lo_ok or hi_ok:
        return visited
    while hi - lo > resolution:
        mid = ((lo + hi) // 2 // resolution) * resolution
        if mid <= lo or mid >= hi:
            break
        if visit(mid):
            lo = mid
        else:
            hi = mid
    return visited


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _filler() -> str:
    import yaml

    doc = yaml.safe_load((ROOT / "configs" / "delta_n.yaml").read_text(encoding="utf-8"))
    return str(doc["ladder"]["filler_unit"])


def _metrics(result: object) -> dict[str, Any]:
    texts = getattr(result, "texts", None)
    text = str(texts[0]) if texts else str(result)
    metrics = getattr(result, "perf_metrics", None)
    prefill_s = None
    prompt_tokens = None
    completion_tokens = None
    if metrics is not None:
        try:
            prompt_tokens = int(metrics.get_num_input_tokens())
            completion_tokens = int(metrics.get_num_generated_tokens())
            ttft_ms = float(metrics.get_ttft().mean)
        except Exception as exc:
            return {
                "ok": True,
                "text": text,
                "prefill_s": None,
                "decode_tok_s": None,
                "prompt_tokens": prompt_tokens,
                "metric_error": f"{type(exc).__name__}: {exc}",
            }
        if ttft_ms > 0.0:
            prefill_s = ttft_ms / 1000.0
    decode_tok_s = None
    return {
        "ok": True,
        "text": text,
        "prefill_s": prefill_s,
        "decode_tok_s": decode_tok_s,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "metric_error": None,
    }


def _arm_canary(out: Path, model_spec: Path, planned: int) -> dict[str, Any]:
    from tools.ttft_slo_canary import (
        CanaryBudgetRefuse,
        CanaryDriftAbort,
        TtftSloCanaryGuard,
    )

    try:
        guard = TtftSloCanaryGuard(
            root=ROOT,
            model_spec=model_spec,
            work_dir=out / "work" / "canaries",
            plan_path=out / "plan.json",
            planned_probe_count=planned,
            allow_unguarded=False,
        )
    except CanaryBudgetRefuse as exc:
        raise SystemExit(f"REFUSED -- {exc.detail}") from exc
    tripped: str | None = None
    try:
        guard.opening()
    except CanaryDriftAbort as exc:
        tripped = exc.detail
    fragment = guard.plan_fragment()
    return {"guard": guard, "canary": fragment, "trip": tripped, **canary_marker(fragment)}


def run_hardware(args: argparse.Namespace) -> int:
    """Load and, when the protocol allows, generate. Writes plan.json and summary.json."""
    import openvino as ov
    import openvino_genai as ov_genai

    spec = load_local_spec(args.model_spec)
    ir = Path(str(spec["ir_dir"]))
    if not ir.is_absolute():
        ir = ROOT / ir
    weight = "int8" if args.cell == "npu2-load" else "int4"
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    plan: dict[str, Any] = {
        "session_id": session_id,
        "cell": args.cell,
        "model_spec": str(args.model_spec),
        "weight_precision": weight,
        "slo_s": SLO_S,
        "prefill_chunk_size": args.prefill_chunk_size,
        "prefill_chunk_citation": "openvino#34617",
        "max_prompt_len_property": "NPUW_LLM_MAX_PROMPT_LEN",
        "requested_max_prompt_len": args.max_prompt_len,
        "ir_quantization": ir_quantization(spec) if weight == "int4" else None,
    }
    _write(out / "plan.json", plan)

    guard_holder: dict[str, Any] = {"guard": None}

    def write_summary(summary: dict[str, Any]) -> None:
        guard = guard_holder["guard"]
        if guard is not None:
            stamp_canary(plan, summary, guard, plan.get("npu_canary_series"))
        else:
            summary.update(
                canary_marker(plan.get("canary") if isinstance(plan.get("canary"), dict) else None)
            )
        _write(out / "plan.json", plan)
        _write(out / "summary.json", summary)

    def arm(planned: int) -> bool:
        if args.no_canary:
            plan["canary"] = {"armed": False, "smoke_skip": True}
            plan.update(canary_marker(plan["canary"]))
            _write(out / "plan.json", plan)
            return True
        try:
            armed = _arm_canary(out, args.model_spec, planned)
        except SystemExit as exc:
            summary = {"session_id": session_id, "status": "REFUSED_CANARY", "detail": str(exc)}
            write_summary(summary)
            print(str(exc))
            return False
        guard_holder["guard"] = armed["guard"]
        stamp_canary(plan, {}, armed["guard"], None)
        _write(out / "plan.json", plan)
        if armed["trip"]:
            summary = {
                "session_id": session_id,
                "status": "FAIL_CANARY_DRIFT",
                "abort_reason": "FAIL_CANARY_DRIFT",
                "canary_trip_detail": armed["trip"],
            }
            write_summary(summary)
            print(f"REFUSED -- canary drift: {armed['trip']}")
            return False
        return True

    if args.cell == "npu2-load" and not arm(4):
        return 1

    core = ov.Core()
    props: dict[str, Any] = {}
    if weight == "int4":
        if args.max_prompt_len is None:
            raise SystemExit("REFUSED -- MAX_PROMPT_LEN is required")
        props["NPUW_LLM_PREFILL_CHUNK_SIZE"] = int(args.prefill_chunk_size)
        props["NPUW_LLM_MAX_PROMPT_LEN"] = int(args.max_prompt_len)
    load_error = None
    pipe = None
    max_prompt_len = None
    rss_before = process_rss_mb()
    load_t0 = time.perf_counter()
    try:
        pipe = ov_genai.LLMPipeline(str(ir), "NPU", **props)
    except Exception as exc:
        load_error = f"{type(exc).__name__}: {exc}"
    load_s = time.perf_counter() - load_t0
    rss_after = process_rss_mb()
    read_errors: list[str] = []
    if pipe is not None and weight == "int4":
        try:
            max_prompt_len = int(pipe.get_property("NPUW_LLM_MAX_PROMPT_LEN"))
        except Exception as exc:
            read_errors.append(f"pipeline: {type(exc).__name__}: {exc}")
            try:
                max_prompt_len = int(core.get_property("NPU", "NPUW_LLM_MAX_PROMPT_LEN"))
            except Exception as exc2:
                read_errors.append(f"core: {type(exc2).__name__}: {exc2}")
    plan["max_prompt_len_read_errors"] = read_errors

    load_fields = {
        "load_s": load_s,
        "process_rss_mb_before": rss_before["rss_mb"],
        "process_rss_mb_after": rss_after["rss_mb"],
        "process_rss_error": rss_before["error"] or rss_after["error"],
        "requested_max_prompt_len": args.max_prompt_len,
        "max_prompt_len_readback": max_prompt_len,
    }

    if args.cell == "npu2-load":
        summary = npu2_load_record(load_error)
        summary.update(
            {"session_id": session_id, "status": "infeasible", "cell": args.cell, **load_fields}
        )
        write_summary(summary)
        print(json.dumps({"ok": True, "status": "infeasible", "generated": False}))
        return 0

    quant = ir_quantization(spec)
    if load_error or pipe is None:
        if not arm(4):
            return 1
        summary = {
            "session_id": session_id,
            "cell": args.cell,
            "status": "infeasible",
            "binding": "LOAD_FAIL",
            "ttft_limit_n": None,
            "load_error": load_error,
            "max_prompt_len": None,
            "error_class": error_class_for(load_error) if load_error else None,
            "generated": False,
            "timed": False,
            "over_max": None,
            "ir_quantization": quant,
            "measurement": True,
            **load_fields,
        }
        write_summary(summary)
        print(json.dumps({"ok": True, "status": "infeasible", "binding": "LOAD_FAIL"}))
        return 0

    if max_prompt_len is None:
        summary = {
            "session_id": session_id,
            "cell": args.cell,
            "status": "REFUSED",
            "binding": None,
            "load_error": None,
            "max_prompt_len": None,
            "generated": False,
            "timed": False,
            "ir_quantization": quant,
            "detail": "load returned no NPUW_LLM_MAX_PROMPT_LEN readback",
            **load_fields,
        }
        write_summary(summary)
        print(json.dumps({"ok": False, "status": "REFUSED"}))
        return 1

    if int(max_prompt_len) != int(args.max_prompt_len):
        summary = {
            "session_id": session_id,
            "cell": args.cell,
            "status": "REFUSED",
            "binding": None,
            "generated": False,
            "timed": False,
            "ir_quantization": quant,
            "detail": "readback does not match the requested MAX_PROMPT_LEN",
            **load_fields,
        }
        write_summary(summary)
        print(json.dumps({"ok": False, "status": "REFUSED", "max_prompt_len": max_prompt_len}))
        return 1

    plan["max_prompt_len"] = max_prompt_len
    _write(out / "plan.json", plan)
    cap = int(max_prompt_len)
    if args.load_only:
        if not arm(4):
            return 1
        bound = setting_estimate_s(cap, low=int(args.low), resolution=int(args.resolution))
        summary = {
            "session_id": session_id,
            "cell": args.cell,
            "status": "loaded_bisect_deferred",
            "binding": None,
            "ttft_limit_n": None,
            "max_prompt_len": cap,
            "generated": False,
            "timed": False,
            "bisect_estimate_s": bound,
            "detail": "load succeeded; the bisection bound does not fit one session",
            "ir_quantization": quant,
            "measurement": True,
            **load_fields,
        }
        write_summary(summary)
        print(json.dumps({"ok": True, "status": "loaded_bisect_deferred", "max_prompt_len": cap}))
        return 0

    from tools.ttft_slo_canary import estimate_bisect_planned_probes

    planned = estimate_bisect_planned_probes(
        n_arms=1,
        low=int(args.low),
        high=cap,
        resolution=int(args.resolution),
        repeats=REPEATS,
    )
    if not arm(planned):
        return 1
    tokenizer = ov_genai.Tokenizer(str(ir))
    filler = _filler()

    def one_generate(device_pipe: object, n_tokens: int) -> dict[str, Any]:
        prompt = rendered_exact_prompt(tokenizer, n_tokens, unit=filler, salt="npu")
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = MAX_NEW_TOKENS
        streamer = _make_ttft_streamer(ov_genai)
        streamer.t0_ns = time.perf_counter_ns()
        try:
            result = device_pipe.generate(prompt, cfg, streamer)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            return {
                "ok": False,
                "text": "",
                "error": message,
                "error_class": error_class_for(message),
                "prefill_s": None,
                "decode_tok_s": None,
                "prompt_tokens": None,
            }
        text = _text_from_generate_result(result)
        measured = _metrics(result)
        measured["text"] = text
        ttft_ns, ttft_source = resolve_ttft_ns(None, streamer.ttft_ns)
        if ttft_ns:
            measured["prefill_s"] = ttft_ns / 1e9
            measured["ttft_source"] = ttft_source
        else:
            measured["metric_error"] = "ttft unavailable"
        written = int(getattr(streamer, "tokens_written", 0))
        first = streamer.first_token_ns
        last = streamer.last_token_ns
        if written > 1 and first is not None and last is not None and last > first:
            measured["decode_tok_s"] = (written - 1) / ((last - first) / 1e9)
        measured["prompt_tokens"] = measured.get("prompt_tokens") or n_tokens
        return measured

    gpu = ov_genai.LLMPipeline(str(ir), "GPU")

    def paired(n_tokens: int) -> dict[str, Any]:
        npu_row = one_generate(pipe, n_tokens)
        gpu_row = one_generate(gpu, n_tokens)
        if not npu_row.get("ok", True):
            return {
                "n_tokens": n_tokens,
                "timed": False,
                "generated": True,
                "status": "REFUSED",
                "error_class": npu_row.get("error_class"),
                "prefill_s": None,
                "decode_tok_s": None,
                "exact_match_vs_gpu": None,
                "prompt_tokens": npu_row.get("prompt_tokens"),
                "reason": None,
                "slo_pass": False,
            }
        row = rung_record(
            n_tokens=n_tokens,
            max_prompt_len=max_prompt_len,
            npu_text=str(npu_row.get("text") or ""),
            gpu_text=str(gpu_row.get("text") or ""),
            prefill_s=npu_row.get("prefill_s"),
            decode_tok_s=npu_row.get("decode_tok_s"),
            prompt_tokens=npu_row.get("prompt_tokens"),
        )
        row["slo_pass"] = slo_pass([row])
        row["gpu_error_class"] = gpu_row.get("error_class")
        row["metric_error"] = npu_row.get("metric_error")
        return row

    guard = guard_holder["guard"]
    probes_log: list[dict[str, Any]] = []
    series = new_npu_series(None if guard is None else guard.n_derivation)
    plan["npu_canary_series"] = series

    def on_interval(after_probe_count: int) -> None:
        sample = one_generate(pipe, NPU_SERIES_TOKENS)
        series["n_derivation"] = None if guard is None else guard.n_derivation
        series["samples"].append(
            {
                "label": "npu_canary_series",
                "gates": False,
                "n_tokens": NPU_SERIES_TOKENS,
                "after_probe_count": after_probe_count,
                "prefill_s": sample.get("prefill_s"),
                "prompt_tokens": sample.get("prompt_tokens"),
                "ok": bool(sample.get("ok", True)),
                "error": sample.get("error"),
            }
        )

    def probe(n_tokens: int) -> dict[str, Any]:
        rung = drive_npu_rung(
            n_tokens,
            repeats=REPEATS,
            one_repeat=paired,
            guard=guard,
            probes_log=probes_log,
            on_interval=None if guard is None else on_interval,
        )
        if guard is not None:
            series["n_derivation"] = guard.n_derivation
        return rung

    high = cap
    from tools.ttft_slo_canary import CanaryDriftAbort, CanaryUnarmedSealRefuse

    try:
        rungs = slo_bisect(int(args.low), high, int(args.resolution), probe)
    except CanaryDriftAbort as exc:
        summary = {
            "session_id": session_id,
            "cell": args.cell,
            "status": "FAIL_CANARY_DRIFT",
            "abort_reason": "FAIL_CANARY_DRIFT",
            "canary_trip_detail": exc.detail,
            "max_prompt_len": high,
            "measurement": True,
            **load_fields,
        }
        write_summary(summary)
        print(f"REFUSED -- canary drift: {exc.detail}")
        return 1
    bound = bind_setting(load_ok=True, cap=high, rungs=rungs)
    over = over_max_record(high)
    summary = {
        "session_id": session_id,
        "cell": args.cell,
        "status": "complete",
        "max_prompt_len": high,
        "low": int(args.low),
        "resolution": int(args.resolution),
        "rungs": rungs,
        "over_max": over,
        "ir_quantization": quant,
        "measurement": True,
        **load_fields,
        **bound,
    }
    if guard is not None:
        try:
            guard.finalize_or_refuse()
        except CanaryUnarmedSealRefuse as exc:
            summary["status"] = "REFUSED_UNARMED_CANARY"
            summary["abort_reason"] = "REFUSED_UNARMED_CANARY"
            summary["canary_unarmed_detail"] = str(exc)
            write_summary(summary)
            print(f"REFUSED -- {exc.detail}")
            return 1
    write_summary(summary)
    print(json.dumps({"ok": True, "status": "complete", "rungs": len(rungs)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cell",
        required=True,
        choices=("npu2-load", "npu1-setting"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model-spec", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--max-prompt-len", type=int)
    parser.add_argument("--load-only", action="store_true")
    parser.add_argument("--low", type=int, default=64)
    parser.add_argument("--resolution", type=int, default=64)
    parser.add_argument("--prefill-chunk-size", type=int, default=1024)
    parser.add_argument("--no-canary", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        _write(
            args.out / "summary.json",
            {"cell": args.cell, "smoke": True, "status": "smoke", "generated": False},
        )
        print(f"SMOKE_OK {args.cell}")
        return 0
    if args.model_spec is None:
        raise SystemExit("REFUSED -- model spec is required")
    return run_hardware(args)


if __name__ == "__main__":
    raise SystemExit(main())
