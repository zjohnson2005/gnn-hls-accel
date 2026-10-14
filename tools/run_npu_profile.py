"""NPU-1 and NPU-2 cells. This runner does not open a preregistration.

NPU-2 loads the int8 IR and stops. An int8 load is infeasible and is never
generated. NPU-1 loads the int4 IR once per requested MAX_PROMPT_LEN (with
MIN_RESPONSE_LEN; amendment 2026-10-07). The length is a load-time setting.
Each load is confirmed by a realized-capacity check (cap - 64 accepted,
cap + 64 refused by the runtime length check), not by a readback. Every
generate is single-template (apply_chat_template False, list call form) and
prompt_length is the pipeline-reported input count. At each loaded setting the
runner bisects
the 10 s TTFT SLO from 64 up to that setting, records decode tok/s at the
highest passing rung, and records MAX_PROMPT_LEN + 1 as infeasible without
generating it.

--envelope (NPU amendment 2026-10-13b) runs the same ladder on an int8 IR:
pinned IR read before load, bisection to cap - 64, a paired 64-token
validity generate per rung (2026-10-12 rule), TTFT-only repeats, binding
TOOLCHAIN_CAP / LATENCY / VALIDITY, and an untimed content check at the
limit rung. Without it the int4 path is unchanged.
"""

from __future__ import annotations

import argparse
import itertools
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
from seam.ir_quantization import ir_quantization as read_ir_quantization  # noqa: E402
from seam.model_provenance import load_local_spec  # noqa: E402
from seam.npu_validity import (  # noqa: E402
    REPEAT_FRACTION_MAX,
    decide_npu_cell,
    fourgram_repeat_fraction,
    output_parses,
    whitespace_tokens,
)
from seam.tools.boot4_text import (  # noqa: E402
    id_count,
    render_user,
    rendered_exact_prompt,
)
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
# Amendment 2026-10-07: the documented GenAI key. NPUW_LLM_MAX_PROMPT_LEN is
# not passed (it did not apply at 2048 in NPU-MAXLEN-DIAG run 2).
MAX_PROMPT_LEN_PROPERTY = "MAX_PROMPT_LEN"
MIN_RESPONSE_LEN = MAX_NEW_TOKENS
CAPACITY_MARGIN = 64
LENGTH_CHECK_TEXT = "input_ids.get_size() <= m_max_prompt_len"


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
    decode = median_number(rates)
    record: dict[str, Any] = {
        "binding": binding,
        "ttft_limit_n": None if chosen is None else int(chosen["n_tokens"]),
        "decode_tok_s_at_limit": decode,
    }
    if chosen is not None and decode is None:
        reasons = sorted(
            {
                str(r.get("decode_reason"))
                for r in chosen.get("repeats") or []
                if isinstance(r, dict)
            }
        )
        record["decode_tok_s_at_limit_reason"] = (
            "no repeat at the limit rung streamed two or more tokens"
            + (f" ({', '.join(reasons)})" if reasons else "")
        )
    return record


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


def over_max_record(max_prompt_len: int, *, weight_precision: str = "int4") -> dict[str, Any]:
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
    # decide_npu_cell labels int8 infeasible at load; MAX_PROMPT_LEN + 1 is a
    # length refusal for either IR, so only the label follows the IR.
    decision["weight_precision"] = weight_precision
    decision["generated"] = False
    decision["error_class"] = None
    decision["max_prompt_len_property"] = MAX_PROMPT_LEN_PROPERTY
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
    decision["max_prompt_len_property"] = MAX_PROMPT_LEN_PROPERTY
    return decision


def npu_load_props(max_prompt_len: int, prefill_chunk_size: int) -> dict[str, Any]:
    """Int4 NPU load config. Amendment 2026-10-07 item 1."""
    return {
        "NPUW_LLM_PREFILL_CHUNK_SIZE": int(prefill_chunk_size),
        MAX_PROMPT_LEN_PROPERTY: int(max_prompt_len),
        "MIN_RESPONSE_LEN": int(MIN_RESPONSE_LEN),
    }


def generation_config(
    ov_genai: Any,
    *,
    max_new_tokens: int = MAX_NEW_TOKENS,
    min_new_tokens: int | None = MAX_NEW_TOKENS,
    apply_chat_template: bool = False,
) -> Any:
    """Greedy, MAX_NEW_TOKENS, one chat template (the prompt is pre-rendered).

    The defaults are the NPU-1 config. NPU-NATSTOP passes min_new_tokens None
    (not set, nothing forced) and chooses the template.
    """
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = max_new_tokens
    if min_new_tokens is not None:
        # Amendment 2026-10-08 item 2: exactly MAX_NEW_TOKENS so decode is measurable.
        cfg.min_new_tokens = min_new_tokens
    cfg.do_sample = False
    cfg.apply_chat_template = apply_chat_template
    return cfg


def generate_once(
    ov_genai: Any, device_pipe: Any, prompt: str, cfg: Any | None = None
) -> dict[str, Any]:
    """One generate in the list call form, so the result carries perf_metrics.

    ``prompt_tokens`` is the pipeline-reported input count only. It is None
    when the pipeline does not report it; the caller must not time that cell.
    ``cfg`` defaults to generation_config(ov_genai).
    """
    if cfg is None:
        cfg = generation_config(ov_genai)
    streamer = _make_ttft_streamer(ov_genai)
    streamer.t0_ns = time.perf_counter_ns()
    try:
        result = device_pipe.generate([prompt], cfg, streamer)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        return {
            "ok": False,
            "text": "",
            "error": message,
            "error_class": error_class_for(message),
            "length_check_refusal": LENGTH_CHECK_TEXT in message,
            "prefill_s": None,
            "decode_tok_s": None,
            "prompt_tokens": None,
        }
    text = _text_from_generate_result(result)
    measured = _metrics(result)
    measured["text"] = text
    if getattr(result, "perf_metrics", None) is None:
        measured["metric_error"] = f"no perf_metrics on {type(result).__name__}"
    ttft_ns, ttft_source = resolve_ttft_ns(None, streamer.ttft_ns)
    if ttft_ns:
        measured["prefill_s"] = ttft_ns / 1e9
        measured["ttft_source"] = ttft_source
    else:
        measured["metric_error"] = "ttft unavailable"
    written = int(getattr(streamer, "tokens_written", 0))
    measured["token_ids"] = list(getattr(streamer, "token_ids", []))
    first = streamer.first_token_ns
    last = streamer.last_token_ns
    measured["streamer_tokens"] = written
    measured["decode_reason"] = None
    if written > 1 and first is not None and last is not None and last > first:
        measured["decode_tok_s"] = (written - 1) / ((last - first) / 1e9)
    else:
        measured["decode_reason"] = f"streamer_tokens={written}; decode needs two or more"
    return measured


def _text_valid(text: str) -> dict[str, Any]:
    """docs/NPU_PROTOCOL.md validity without a GPU reference."""
    parses = output_parses(text)
    fraction = fourgram_repeat_fraction(whitespace_tokens(text))
    degenerate = fraction is not None and fraction > REPEAT_FRACTION_MAX
    return {"parses": parses, "repeat_4gram_fraction": fraction, "valid": parses and not degenerate}


def capacity_probe(
    *,
    cap: int,
    build_prompt: Callable[[int], str],
    count_tokens: Callable[[str], int],
    generate: Callable[[str], dict[str, Any]],
    margin: int = CAPACITY_MARGIN,
) -> dict[str, Any]:
    """Amendment 2026-10-07 item 2. Replaces readback == request.

    P1: cap - margin realized tokens accepted, pipeline count == realized, valid.
    P2: cap + margin tokens refused by the runtime length check.
    """

    def one(target: int) -> dict[str, Any]:
        row: dict[str, Any] = {"target_tokens": target}
        try:
            prompt = build_prompt(target)
            row["realized_tokens"] = int(count_tokens(prompt))
        except Exception as exc:
            row.update(realized_tokens=None, build_error=f"{type(exc).__name__}: {exc}")
            return row
        out = generate(prompt)
        row.update(
            ok=bool(out.get("ok", True)),
            error=out.get("error"),
            pipeline_input_tokens=out.get("prompt_tokens"),
            prefill_s=out.get("prefill_s"),
            text=out.get("text"),
            length_check_refusal=bool(out.get("length_check_refusal")),
            completion_tokens=out.get("completion_tokens"),
            streamer_tokens=out.get("streamer_tokens"),
        )
        return row

    p1 = one(int(cap) - int(margin))
    p1.update(_text_valid(str(p1.get("text") or "")) if p1.get("ok") else {"valid": False})
    p1["pass"] = bool(
        p1.get("ok")
        and isinstance(p1.get("realized_tokens"), int)
        and p1.get("pipeline_input_tokens") == p1.get("realized_tokens")
        and p1.get("valid")
    )
    p2 = one(int(cap) + int(margin))
    p2["pass"] = bool(
        isinstance(p2.get("realized_tokens"), int)
        and not p2.get("ok", True)
        and p2.get("length_check_refusal")
    )
    return {
        "cap": int(cap),
        "margin": int(margin),
        "length_check_text": LENGTH_CHECK_TEXT,
        "P1": p1,
        "P2": p2,
        "passed": bool(p1["pass"] and p2["pass"]),
        "timed": False,
    }


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


# ---------------------------------------------------------------- int8 envelope
# NPU amendment 2026-10-13b. Used only with --envelope; the int4 path above is
# unchanged. The constants are written here and in the amendment, and a test
# checks they agree. This runner does not open the amendment.

ENVELOPE_MAX_NEW_TOKENS = 64
ENVELOPE_TIMING_MAX_NEW_TOKENS = 1
ENVELOPE_HIGH_MARGIN = 64
VALID_MIN_REAL_TOKENS = 62
VALID_REPEAT_MAX = 27 / 61
THINK_TAGS = ("<think>", "</think>")
CONTENT_QUESTION = "What is the capital of France? Answer in one sentence."
CONTENT_KEYWORD = "paris"
CONTENT_SEPARATOR = "\n\n"
CONTENT_PAD = " a"

# Estimate inputs. Recorded, not cited; they only size the scheduling bound.
# int8 NPU load at 2048 and TTFT at 21-32 tokens: the four F1 NPU cells
# (natstop_f1_b172b287). Decode: F1 child walls, (189.235 - 26.634) / 56.
INT8_LOAD_S_AT_2048 = 139.4185
INT8_TTFT_S_SHORT = 4.150
INT8_DECODE_S_PER_TOKEN = 2.9035892857142853
# int4 loads per setting (34c2240f, f704d565/ca3467ad mean, 47630f52,
# 413d4a2e, d626d0bc, 3a672cd5) and int4 prefill points (34c2240f rung at 64
# and P1 at 960; load-only P1 prefills above).
INT4_LOAD_S = {
    1024: 81.87166820000857,
    2048: 95.07,
    4096: 117.09,
    8192: 195.05,
    16384: 508.77,
    32768: 1963.26,
}
INT4_PREFILL_S = {
    64: 1.2872927333333333,
    960: 1.3240669,
    1984: 2.77,
    4032: 6.54,
    8128: 15.94,
    16320: 58.61,
    32704: 245.76,
}
INT8_LOAD_RATIO = INT8_LOAD_S_AT_2048 / INT4_LOAD_S[2048]
INT8_TTFT_RATIO = INT8_TTFT_S_SHORT / INT4_PREFILL_S[64]
ENVELOPE_GPU_GENERATE_S = 4.0
ENVELOPE_GPU_SETUP_S = 10.0
ENVELOPE_CANARY_S = 12.0
ENVELOPE_OVERHEAD_S = 30.0
ENVELOPE_TIMING_OVERHEAD_S = 0.5


def envelope_ttft_estimate_s(n_tokens: int) -> float:
    """int4 prefill interpolated linearly, times the F1 short-prompt ratio."""
    points = sorted(INT4_PREFILL_S)
    if n_tokens <= points[0]:
        base = INT4_PREFILL_S[points[0]]
    elif n_tokens >= points[-1]:
        base = INT4_PREFILL_S[points[-1]]
    else:
        base = INT4_PREFILL_S[points[-1]]
        for lo, hi in itertools.pairwise(points):
            if n_tokens <= hi:
                span = (n_tokens - lo) / float(hi - lo)
                base = INT4_PREFILL_S[lo] + (INT4_PREFILL_S[hi] - INT4_PREFILL_S[lo]) * span
                break
    return INT8_TTFT_RATIO * base


def envelope_high(cap: int) -> int:
    """MIN_RESPONSE_LEN leaves cap + 8 - n tokens; 64 need n <= cap - 56."""
    return int(cap) - ENVELOPE_HIGH_MARGIN


def envelope_load_estimate_s(cap: int) -> float:
    if cap not in INT4_LOAD_S:
        raise SystemExit(f"REFUSED -- no recorded int4 load at {cap} to scale")
    return INT4_LOAD_S[cap] * INT8_LOAD_RATIO


def envelope_estimate_s(cap: int, *, low: int = SHORT_PROMPT_TOKENS, resolution: int = 64) -> int:
    """Upper bound for one envelope session; every rung priced at the high rung."""
    high = envelope_high(cap)
    points = 2 + math.ceil(math.log2(max(1.0, (high - low) / float(resolution))))
    planned = points * REPEATS
    ttft = envelope_ttft_estimate_s(high)
    generate64 = ttft + (ENVELOPE_MAX_NEW_TOKENS - 1) * INT8_DECODE_S_PER_TOKEN
    rung = (generate64 + ENVELOPE_GPU_GENERATE_S) + (REPEATS - 1) * (
        ttft + ENVELOPE_TIMING_OVERHEAD_S
    )
    interval = max(1, planned // 4)
    canaries = 3 + math.ceil(planned / interval) + 1
    capacity = envelope_ttft_estimate_s(cap - CAPACITY_MARGIN) + (
        (MAX_NEW_TOKENS - 1) * INT8_DECODE_S_PER_TOKEN
    )
    content = generate64 + ENVELOPE_GPU_GENERATE_S
    total = (
        envelope_load_estimate_s(cap)
        + capacity
        + ENVELOPE_GPU_SETUP_S
        + points * rung
        + canaries * ENVELOPE_CANARY_S
        + content
        + ENVELOPE_OVERHEAD_S
    )
    return math.ceil(total)


def envelope_load_only_estimate_s(cap: int) -> int:
    capacity = envelope_ttft_estimate_s(cap - CAPACITY_MARGIN) + (
        (MAX_NEW_TOKENS - 1) * INT8_DECODE_S_PER_TOKEN
    )
    return math.ceil(
        envelope_load_estimate_s(cap) + capacity + ENVELOPE_OVERHEAD_S + 4 * ENVELOPE_CANARY_S
    )


def strip_think(text: str | None) -> str:
    out = text or ""
    for tag in THINK_TAGS:
        out = out.replace(tag, "")
    return out.strip()


def stop_set_of(pipe: Any) -> dict[str, Any]:
    """eos and stop ids from the pipeline's generation config."""
    try:
        cfg = pipe.get_generation_config()
    except Exception as exc:
        return {"ids": [], "error": f"{type(exc).__name__}: {exc}"}
    found: set[int] = set()
    eos = getattr(cfg, "eos_token_id", None)
    if isinstance(eos, int) and eos >= 0:
        found.add(int(eos))
    for value in getattr(cfg, "stop_token_ids", None) or []:
        found.add(int(value))
    return {"ids": sorted(found), "error": None}


def real_token_count(ids: list[int], stop_ids: list[int], decode: Callable[[int], str]) -> int:
    """Ids not in the stop set whose text, think tags removed, is not whitespace."""
    stops = set(stop_ids)
    count = 0
    for token in ids:
        if token in stops:
            continue
        piece = decode(token) or ""
        for tag in THINK_TAGS:
            piece = piece.replace(tag, "")
        if piece.strip():
            count += 1
    return count


def envelope_generation(
    out: dict[str, Any], *, realized: int, stop_ids: list[int], decode: Callable[[int], str]
) -> dict[str, Any]:
    """One validity or content generate, reduced to the fields the rule reads."""
    returned = bool(out.get("ok", True))
    ids = [int(i) for i in out.get("token_ids") or []][:ENVELOPE_MAX_NEW_TOKENS]
    count = real_token_count(ids, stop_ids, decode) if returned else 0
    return {
        "generate_returned": returned,
        "error": out.get("error"),
        "error_class": out.get("error_class"),
        "realized_tokens": realized,
        "pipeline_input_tokens": out.get("prompt_tokens"),
        "prefill_s": out.get("prefill_s"),
        "decode_tok_s": out.get("decode_tok_s"),
        "decode_reason": out.get("decode_reason"),
        "generated_ids": ids,
        "stop": "max" if len(ids) >= ENVELOPE_MAX_NEW_TOKENS else "EOS",
        "real_token_count": count,
        "id_repeat_fraction": fourgram_repeat_fraction(ids),
        "text": out.get("text") if returned else None,
        "metric_error": out.get("metric_error"),
    }


def envelope_valid(gen: dict[str, Any] | None, reference: dict[str, Any] | None) -> dict[str, Any]:
    """2026-10-12 rule. Floor: the reference's real tokens when it stopped by EOS."""
    if not isinstance(gen, dict) or not gen.get("generate_returned"):
        return {"valid": False, "reason": "generate_failed", "k_eff": None}
    if gen.get("pipeline_input_tokens") != gen.get("realized_tokens"):
        return {"valid": False, "reason": "input_count_mismatch", "k_eff": None}
    k_eff = VALID_MIN_REAL_TOKENS
    if (
        isinstance(reference, dict)
        and reference.get("generate_returned")
        and reference.get("stop") == "EOS"
        and isinstance(reference.get("real_token_count"), int)
    ):
        k_eff = min(k_eff, int(reference["real_token_count"]))
    k_eff = max(1, k_eff)
    if int(gen.get("real_token_count") or 0) < k_eff:
        return {"valid": False, "reason": "too_few_real_tokens", "k_eff": k_eff}
    fraction = gen.get("id_repeat_fraction")
    if fraction is not None and float(fraction) > VALID_REPEAT_MAX:
        return {"valid": False, "reason": "id_4gram_repeat", "k_eff": k_eff}
    return {"valid": True, "reason": None, "k_eff": k_eff}


def envelope_binding(*, rungs: list[dict[str, Any]], high: int) -> dict[str, Any]:
    """TOOLCHAIN_CAP, LATENCY or VALIDITY from the lowest failing rung above the limit."""
    passing = [row for row in rungs if row.get("slo_pass")]
    chosen = max(passing, key=lambda row: int(row["n_tokens"])) if passing else None
    limit = None if chosen is None else int(chosen["n_tokens"])
    decode = None
    if chosen is not None:
        decode = (chosen.get("validity") or {}).get("npu", {}).get("decode_tok_s")
    if limit is not None and limit >= int(high):
        return {
            "binding": "TOOLCHAIN_CAP",
            "ttft_limit_n": limit,
            "deciding_rung": None,
            "decode_tok_s_at_limit": decode,
        }
    above = sorted(
        (
            row
            for row in rungs
            if not row.get("slo_pass") and (limit is None or row["n_tokens"] > limit)
        ),
        key=lambda row: int(row["n_tokens"]),
    )
    first = above[0] if above else None
    binding = None
    if first is not None:
        binding = "LATENCY" if first.get("valid") else "VALIDITY"
    return {
        "binding": binding,
        "ttft_limit_n": limit,
        "deciding_rung": None if first is None else int(first["n_tokens"]),
        "decode_tok_s_at_limit": decode,
    }


def content_passes(gen: dict[str, Any] | None, reference: dict[str, Any] | None) -> bool:
    if not envelope_valid(gen, reference)["valid"]:
        return False
    assert gen is not None
    return CONTENT_KEYWORD in strip_think(gen.get("text")).lower()


def content_outcome(npu: dict[str, Any] | None, gpu: dict[str, Any] | None) -> str:
    if not content_passes(gpu, gpu):
        return "CONTENT_REFERENCE_UNUSABLE"
    return "CONTENT_OK" if content_passes(npu, gpu) else "CONTENT_FAIL"


def content_prompt(tokenizer: Any, target: int, *, unit: str, salt: str) -> str:
    """Filler prompt of ``target`` rendered tokens ending with the chat1 question.

    Padding goes between the salt and the filler units, never before the
    suffix: on Qwen3 the filler's final "." and the "\n\n" separator merge
    into one token, so padding there splits it and overshoots by one (task X,
    1e79daa3: "overshot while padding to 960: reached 961"). Returns the exact
    length when reachable, else the longest prompt below it; the caller
    records any shortfall.
    """
    suffix = CONTENT_SEPARATOR + CONTENT_QUESTION

    def text(pad: int, k: int) -> str:
        return salt + CONTENT_PAD * pad + " " + unit * k + suffix

    def total(pad: int, k: int) -> int:
        return id_count(tokenizer, render_user(tokenizer, text(pad, k)))

    if total(0, 0) > target:
        raise SystemExit(f"REFUSED -- content prompt is above {target} tokens with no filler")
    low, high = 0, target + 2
    while low < high:
        mid = (low + high + 1) // 2
        if total(0, mid) <= target:
            low = mid
        else:
            high = mid - 1
    best_pad, best_n = 0, total(0, low)
    pad = 0
    for _ in range(64):
        current = total(pad, low)
        if current > target:
            break
        if current > best_n:
            best_pad, best_n = pad, current
        if current == target:
            break
        pad += target - current
    rendered = render_user(tokenizer, text(best_pad, low))
    if id_count(tokenizer, rendered) > target:
        raise SystemExit(f"REFUSED -- content prompt is above {target} tokens")
    return rendered


def run_content_check(
    *,
    limit: int | None,
    build: Callable[[int], str],
    npu_generate: Callable[[str], dict[str, Any]],
    gpu_generate: Callable[[str], dict[str, Any]],
    npu_stops: list[int],
    gpu_stops: list[int],
    decode: Callable[[int], str],
    count: Callable[[str], int] | None = None,
) -> dict[str, Any]:
    """Item 7: untimed, after the closing canary, at the limit rung.

    ``count`` gives the realized token count of the built prompt; a prompt
    shorter than the limit is recorded as a shortfall (item 7 asks for
    exactly L tokens, so the limit is then not citable).
    """
    if limit is None:
        return {"outcome": "NO_LIMIT", "n_tokens": None, "timed": False}
    try:
        prompt = build(int(limit))
    except (Exception, SystemExit) as exc:
        return {
            "outcome": "CONTENT_PROMPT_ERROR",
            "n_tokens": int(limit),
            "error": f"{type(exc).__name__}: {exc}",
            "timed": False,
        }
    realized = int(limit) if count is None else int(count(prompt))
    npu = envelope_generation(
        npu_generate(prompt), realized=realized, stop_ids=npu_stops, decode=decode
    )
    gpu = envelope_generation(
        gpu_generate(prompt), realized=realized, stop_ids=gpu_stops, decode=decode
    )
    return {
        "outcome": content_outcome(npu, gpu),
        "n_tokens": realized,
        "target_tokens": int(limit),
        "shortfall_tokens": int(limit) - realized,
        "question": CONTENT_QUESTION,
        "keyword": CONTENT_KEYWORD,
        "npu": npu,
        "gpu": gpu,
        "npu_valid": envelope_valid(npu, gpu),
        "gpu_valid": envelope_valid(gpu, gpu),
        "timed": False,
    }


def envelope_ir_refusal(record: dict[str, Any]) -> str | None:
    if record.get("error") and not record.get("xml_present"):
        return f"IR unreadable: {record['error']}"
    if not record.get("xml_present"):
        return "openvino_model.xml absent"
    if record.get("xml_matches_pin") is not True:
        return "openvino_model.xml does not match the spec pin"
    mode = str((record.get("summary") or {}).get("mode") or "")
    if not mode.startswith("INT8"):
        return f"IR mode {mode or 'unknown'} is not INT8"
    return None


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


def _arm_canary(
    out: Path, model_spec: Path, planned: int, *, before_probes: bool = False
) -> dict[str, Any]:
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
            arm_before_probes=before_probes,
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
    envelope = bool(getattr(args, "envelope", False))
    if envelope and args.cell != "npu1-setting":
        raise SystemExit("REFUSED -- --envelope applies to npu1-setting only")
    weight = "int8" if args.cell == "npu2-load" or envelope else "int4"
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
        "max_prompt_len_property": MAX_PROMPT_LEN_PROPERTY,
        "min_response_len": MIN_RESPONSE_LEN,
        "apply_chat_template": False,
        "generate_call_form": "list",
        "amendment": "NPU 2026-10-13b int8 envelope" if envelope else "NPU 2026-10-07",
        "requested_max_prompt_len": args.max_prompt_len,
        "ir_quantization": ir_quantization(spec) if weight == "int4" else None,
    }
    ir_read: dict[str, Any] | None = None
    if envelope:
        pin = (spec.get("ir_files") or {}).get("openvino_model.xml")
        ir_read = read_ir_quantization(ir, pin)
        plan["ir_quantization"] = ir_read
        plan["envelope"] = {
            "max_new_tokens": ENVELOPE_MAX_NEW_TOKENS,
            "timing_max_new_tokens": ENVELOPE_TIMING_MAX_NEW_TOKENS,
            "high": None if args.max_prompt_len is None else envelope_high(args.max_prompt_len),
            "valid_min_real_tokens": VALID_MIN_REAL_TOKENS,
            "valid_repeat_max": VALID_REPEAT_MAX,
            "content_question": CONTENT_QUESTION,
            "content_keyword": CONTENT_KEYWORD,
        }
    _write(out / "plan.json", plan)
    if ir_read is not None:
        refusal = envelope_ir_refusal(ir_read)
        if refusal:
            _write(
                out / "summary.json",
                {
                    "session_id": session_id,
                    "cell": args.cell,
                    "status": "REFUSED_IR",
                    "detail": refusal,
                    "ir_quantization": ir_read,
                    "generated": False,
                    "timed": False,
                },
            )
            print(f"REFUSED -- {refusal}")
            return 1

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

    def arm(planned: int, *, before_probes: bool = False) -> bool:
        if args.no_canary:
            plan["canary"] = {"armed": False, "smoke_skip": True}
            plan.update(canary_marker(plan["canary"]))
            _write(out / "plan.json", plan)
            return True
        try:
            armed = _arm_canary(out, args.model_spec, planned, before_probes=before_probes)
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
        if before_probes and not armed["armed"]:
            # Amendment 2026-10-08 item 1: no probe runs on an unarmed gate.
            summary = {
                "session_id": session_id,
                "cell": args.cell,
                "status": "REFUSED_UNARMED_CANARY",
                "abort_reason": "REFUSED_UNARMED_CANARY",
                "canary_unarmed_detail": "gate not armed after the calibration canaries",
                "generated": False,
                "timed": False,
            }
            write_summary(summary)
            print("REFUSED -- gate not armed after the calibration canaries; no probe ran")
            return False
        return True

    if args.cell == "npu2-load" and not arm(4):
        return 1

    core = ov.Core()
    props: dict[str, Any] = {}
    if args.cell == "npu1-setting":
        if args.max_prompt_len is None:
            raise SystemExit("REFUSED -- MAX_PROMPT_LEN is required")
        props = npu_load_props(int(args.max_prompt_len), int(args.prefill_chunk_size))
    plan["load_props"] = dict(props)
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
    if pipe is not None and args.cell == "npu1-setting":
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
        "max_prompt_len_readback_note": (
            "device default via core fallback; informational, gates nothing (amendment 2026-10-07)"
        ),
    }

    if args.cell == "npu2-load":
        summary = npu2_load_record(load_error)
        summary.update(
            {"session_id": session_id, "status": "infeasible", "cell": args.cell, **load_fields}
        )
        write_summary(summary)
        print(json.dumps({"ok": True, "status": "infeasible", "generated": False}))
        return 0

    quant = ir_read if envelope else ir_quantization(spec)
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

    cap = int(args.max_prompt_len)
    tokenizer = ov_genai.Tokenizer(str(ir))
    filler = _filler()

    def build_prompt(n_tokens: int) -> str:
        return rendered_exact_prompt(tokenizer, n_tokens, unit=filler, salt="npu")

    capacity = capacity_probe(
        cap=cap,
        build_prompt=build_prompt,
        count_tokens=lambda text: id_count(tokenizer, text),
        generate=lambda prompt: generate_once(ov_genai, pipe, prompt),
    )
    if envelope:
        # Amendment 2026-10-13b item 1: P1 validity is recorded, not a gate.
        p1, p2 = capacity["P1"], capacity["P2"]
        capacity["envelope_passed"] = bool(
            p1.get("ok")
            and isinstance(p1.get("realized_tokens"), int)
            and p1.get("pipeline_input_tokens") == p1.get("realized_tokens")
            and p2.get("pass")
        )
    capacity_ok = capacity["envelope_passed"] if envelope else capacity["passed"]
    plan["capacity_check"] = capacity
    _write(out / "plan.json", plan)
    if not capacity_ok:
        summary = {
            "session_id": session_id,
            "cell": args.cell,
            "status": "REFUSED_CAPACITY",
            "binding": None,
            "generated": False,
            "timed": False,
            "ir_quantization": quant,
            "capacity_check": capacity,
            "detail": "realized-capacity check failed (amendment 2026-10-07)",
            **load_fields,
        }
        write_summary(summary)
        print(json.dumps({"ok": False, "status": "REFUSED_CAPACITY", "max_prompt_len": cap}))
        return 1

    plan["max_prompt_len"] = cap
    _write(out / "plan.json", plan)
    if args.load_only:
        if not arm(4):
            return 1
        if envelope:
            bound = envelope_estimate_s(cap, low=int(args.low), resolution=int(args.resolution))
        else:
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
            "capacity_check": capacity,
            "ir_quantization": quant,
            "measurement": True,
            **load_fields,
        }
        write_summary(summary)
        print(json.dumps({"ok": True, "status": "loaded_bisect_deferred", "max_prompt_len": cap}))
        return 0

    from tools.ttft_slo_canary import estimate_bisect_planned_probes

    high = envelope_high(cap) if envelope else cap
    planned = estimate_bisect_planned_probes(
        n_arms=1,
        low=int(args.low),
        high=high,
        resolution=int(args.resolution),
        repeats=REPEATS,
    )

    def one_generate(device_pipe: object, n_tokens: int) -> dict[str, Any]:
        return generate_once(ov_genai, device_pipe, build_prompt(n_tokens))

    # Amendment 2026-10-08b: calibrate in measurement state. The paired GPU
    # pipeline exists and has run one untimed warm-up generate first.
    gpu = ov_genai.LLMPipeline(str(ir), "GPU")
    warm = one_generate(gpu, int(args.low))
    plan["gpu_warmup"] = {
        "n_tokens": int(args.low),
        "prompt": "rendered_exact_prompt(target=low, salt=npu), the low-rung prompt",
        "ok": bool(warm.get("ok", True)),
        "error": warm.get("error"),
        "prompt_tokens": warm.get("prompt_tokens"),
        "streamer_tokens": warm.get("streamer_tokens"),
        "timed": False,
        "is_probe": False,
    }
    _write(out / "plan.json", plan)
    if not plan["gpu_warmup"]["ok"]:
        summary = {
            "session_id": session_id,
            "cell": args.cell,
            "status": "REFUSED_GPU_WARMUP",
            "detail": warm.get("error"),
            "generated": False,
            "timed": False,
            "capacity_check": capacity,
            **load_fields,
        }
        write_summary(summary)
        print(json.dumps({"ok": False, "status": "REFUSED_GPU_WARMUP"}))
        return 1

    plan["guard_schedule"] = (
        "gpu pipeline + warm-up, then arm_before_probes (amendments 2026-10-08, 2026-10-08b)"
    )
    if not arm(planned, before_probes=True):
        return 1

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
        if npu_row.get("prompt_tokens") is None:
            return {
                "n_tokens": n_tokens,
                "timed": False,
                "generated": True,
                "status": "REFUSED",
                "error_class": None,
                "prefill_s": None,
                "decode_tok_s": None,
                "exact_match_vs_gpu": None,
                "prompt_tokens": None,
                "reason": "prompt_length_not_reported",
                "metric_error": npu_row.get("metric_error"),
                "slo_pass": False,
            }
        row = rung_record(
            n_tokens=n_tokens,
            max_prompt_len=cap,
            npu_text=str(npu_row.get("text") or ""),
            gpu_text=str(gpu_row.get("text") or ""),
            prefill_s=npu_row.get("prefill_s"),
            decode_tok_s=npu_row.get("decode_tok_s"),
            prompt_tokens=npu_row.get("prompt_tokens"),
        )
        row["slo_pass"] = slo_pass([row])
        row["gpu_error_class"] = gpu_row.get("error_class")
        row["metric_error"] = npu_row.get("metric_error")
        row["gpu_prompt_tokens"] = gpu_row.get("prompt_tokens")
        row["npu_completion_tokens"] = npu_row.get("completion_tokens")
        row["npu_streamer_tokens"] = npu_row.get("streamer_tokens")
        row["decode_reason"] = npu_row.get("decode_reason")
        return row

    cfg64 = generation_config(ov_genai, max_new_tokens=ENVELOPE_MAX_NEW_TOKENS, min_new_tokens=None)
    cfg_timing = generation_config(
        ov_genai, max_new_tokens=ENVELOPE_TIMING_MAX_NEW_TOKENS, min_new_tokens=None
    )
    npu_stops = stop_set_of(pipe) if envelope else {"ids": [], "error": None}
    gpu_stops = stop_set_of(gpu) if envelope else {"ids": [], "error": None}

    def decode(token: int) -> str:
        try:
            return str(tokenizer.decode([int(token)]))
        except Exception:
            return ""

    if envelope:
        plan["envelope"]["stop_ids"] = {"NPU": npu_stops, "GPU": gpu_stops}
        _write(out / "plan.json", plan)
    rung_state: dict[int, dict[str, Any]] = {}

    def envelope_paired(n_tokens: int) -> dict[str, Any]:
        """Repeat 1: paired 64-token validity generate. Repeats 2-3: NPU TTFT only."""
        state = rung_state.setdefault(n_tokens, {"repeat": 0, "valid": False})
        state["repeat"] += 1
        row: dict[str, Any] = {"n_tokens": n_tokens, "repeat": state["repeat"], "generated": True}
        prompt = build_prompt(n_tokens)
        if state["repeat"] == 1:
            npu_gen = envelope_generation(
                generate_once(ov_genai, pipe, prompt, cfg64),
                realized=n_tokens,
                stop_ids=npu_stops["ids"],
                decode=decode,
            )
            gpu_gen = envelope_generation(
                generate_once(ov_genai, gpu, prompt, cfg64),
                realized=n_tokens,
                stop_ids=gpu_stops["ids"],
                decode=decode,
            )
            verdict = envelope_valid(npu_gen, gpu_gen)
            gpu_verdict = envelope_valid(gpu_gen, gpu_gen)
            state["valid"] = bool(verdict["valid"])
            state["validity"] = {
                "npu": npu_gen,
                "gpu": gpu_gen,
                **verdict,
                "gpu_valid": gpu_verdict["valid"],
                "exact_match_vs_gpu": npu_gen["generated_ids"] == gpu_gen["generated_ids"],
            }
            row["kind"] = "validity"
            measured = npu_gen
            row["decode_tok_s"] = npu_gen.get("decode_tok_s")
            row["decode_reason"] = npu_gen.get("decode_reason")
            row["exact_match_vs_gpu"] = state["validity"]["exact_match_vs_gpu"]
        else:
            row["kind"] = "timing"
            row["decode_tok_s"] = None
            row["exact_match_vs_gpu"] = None
            if not state["valid"]:
                row.update(timed=False, prefill_s=None, prompt_length=None, reason="rung_not_valid")
                row["slo_pass"] = False
                return row
            raw = generate_once(ov_genai, pipe, prompt, cfg_timing)
            measured = {
                "generate_returned": bool(raw.get("ok", True)),
                "pipeline_input_tokens": raw.get("prompt_tokens"),
                "prefill_s": raw.get("prefill_s"),
                "error": raw.get("error"),
                "metric_error": raw.get("metric_error"),
            }
        count = measured.get("pipeline_input_tokens")
        timed = bool(
            state["valid"]
            and measured.get("generate_returned")
            and count == n_tokens
            and isinstance(measured.get("prefill_s"), (int, float))
        )
        reason = None
        if not state["valid"]:
            reason = (state.get("validity") or {}).get("reason") or "rung_not_valid"
        elif not timed:
            reason = "not_timed"
        row.update(
            timed=timed,
            prefill_s=measured.get("prefill_s") if timed else None,
            prompt_length=count,
            reason=reason,
            error=measured.get("error"),
            metric_error=measured.get("metric_error"),
        )
        row["slo_pass"] = slo_pass([row])
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
            one_repeat=envelope_paired if envelope else paired,
            guard=guard,
            probes_log=probes_log,
            on_interval=None if guard is None else on_interval,
        )
        if guard is not None:
            series["n_derivation"] = guard.n_derivation
        if envelope:
            state = rung_state.get(n_tokens) or {}
            rung["valid"] = bool(state.get("valid"))
            rung["validity"] = state.get("validity")
        return rung

    from tools.ttft_slo_canary import CanaryDriftAbort, CanaryUnarmedSealRefuse

    try:
        rungs = slo_bisect(int(args.low), high, int(args.resolution), probe)
        if guard is not None:
            guard.closing(probes_log)
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
    content: dict[str, Any] | None = None
    if envelope:
        bound = envelope_binding(rungs=rungs, high=high)
        content = run_content_check(
            limit=bound["ttft_limit_n"],
            build=lambda n: content_prompt(tokenizer, n, unit=filler, salt="npu"),
            count=lambda prompt: id_count(tokenizer, prompt),
            npu_generate=lambda prompt: generate_once(ov_genai, pipe, prompt, cfg64),
            gpu_generate=lambda prompt: generate_once(ov_genai, gpu, prompt, cfg64),
            npu_stops=npu_stops["ids"],
            gpu_stops=gpu_stops["ids"],
            decode=decode,
        )
    else:
        bound = bind_setting(load_ok=True, cap=high, rungs=rungs)
    over = over_max_record(cap, weight_precision=weight)
    summary = {
        "session_id": session_id,
        "cell": args.cell,
        "status": "complete",
        "max_prompt_len": high,
        "low": int(args.low),
        "resolution": int(args.resolution),
        "rungs": rungs,
        "capacity_check": capacity,
        "over_max": over,
        "envelope": envelope,
        "content_check": content,
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
    if envelope:
        armed = False if guard is None else canary_marker(guard.plan_fragment())["armed"]
        summary["limit_citable"] = bool(
            armed
            and summary["status"] == "complete"
            and isinstance(content, dict)
            and content.get("outcome") == "CONTENT_OK"
            and content.get("shortfall_tokens") == 0
        )
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
    parser.add_argument(
        "--envelope",
        action="store_true",
        help="NPU-INT8 envelope (amendment 2026-10-13b); npu1-setting on an int8 IR",
    )
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
    if args.envelope and args.cell != "npu1-setting":
        raise SystemExit("REFUSED -- --envelope applies to npu1-setting only")
    return run_hardware(args)


if __name__ == "__main__":
    raise SystemExit(main())
