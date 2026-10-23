"""Largest n_cached a RESIDENT session holds, one attempt per rung.

Turn 1 must complete and turn 2 must run. Passing rungs record turn-2 TTFT.
--smoke loads the pipeline, runs one turn 1 and one turn 2 at a tiny n,
prints timing, and writes nothing under derived/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.boot4_session import (  # noqa: E402
    RESIDENT_HIGH,
    _resident_high,
    _resident_low,
    _resident_resolution,
    new_session_id,
    run_cc_series,
    run_resident_limit,
    run_resident_limit_smoke,
    set_cc_overrides,
    set_pilot_overrides,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--model-spec", required=True, type=Path)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    # DEMO-2 pilots P2/P3 (Task AS); defaults unchanged (plain LLMPipeline).
    parser.add_argument(
        "--sched-max-batched-tokens",
        type=int,
        default=None,
        help="Explicit SchedulerConfig(enable_prefix_caching=True, max_num_batched_tokens=N); "
        "it replaces GenAI's latency defaults.",
    )
    parser.add_argument(
        "--sched-cache-size", type=int, default=None, help="SchedulerConfig cache_size, whole GB."
    )
    parser.add_argument(
        "--high", type=int, default=None, help=f"Ladder top (default {RESIDENT_HIGH})."
    )
    # CC cells (Task BJ, docs/registrations/CC_CONTEXT_CEILING_2026-10-23.md); all off by default.
    parser.add_argument("--cc-cell", default=None, help="CC cell id, recorded in the plan.")
    parser.add_argument("--low", type=int, default=None, help="Ladder bottom (default 12000).")
    parser.add_argument("--resolution", type=int, default=None, help="Grid (default 500).")
    parser.add_argument(
        "--points", default=None, help="Comma list of n: attempt each once, no bisection."
    )
    parser.add_argument("--turn2-new-tokens", type=int, default=None, help="Default 1.")
    parser.add_argument("--turn2-repeats", type=int, default=None, help="Default 1.")
    parser.add_argument(
        "--gpu-mem-stats",
        action="store_true",
        help="Child records GPU_MEMORY_STATISTICS, the GPU process counters and system memory "
        "after load, turn 1 and each turn 2.",
    )
    parser.add_argument(
        "--compiled-readback",
        action="store_true",
        help="Child captures GenAI's load log and records the compiled KV type and backend.",
    )
    # Task BL amendments (docs/registrations/CC_AMEND_2026-10-23b.md); all off by default.
    parser.add_argument("--probe-timeout-s", type=float, default=None, help="Child timeout (A4).")
    parser.add_argument("--mem-trace-hz", type=float, default=None, help="In-child trace (A6).")
    parser.add_argument(
        "--sched-no-prefix-caching",
        action="store_true",
        help="With --sched-max-batched-tokens: enable_prefix_caching=False (A13).",
    )
    parser.add_argument("--grow-step", type=int, default=None, help="CC-GROW turn tokens (A9).")
    parser.add_argument("--grow-max", type=int, default=None, help="CC-GROW stop at this context.")
    parser.add_argument("--grow-new-tokens", type=int, default=1)
    parser.add_argument("--conc-sessions", default=None, help="CC-CONC N list, ascending (A13).")
    parser.add_argument("--conc-tokens", type=int, default=None, help="Tokens per session.")
    parser.add_argument("--conc-new-tokens", type=int, default=16)
    # Task BM amendments (docs/registrations/CC_AMEND_2026-10-23c.md); all off by default.
    parser.add_argument(
        "--dxgi-trace", action="store_true", help="A19: DXGI budget/usage in the 10 Hz trace."
    )
    parser.add_argument(
        "--reject-kv-mismatch",
        action="store_true",
        help="A31: fail a probe whose compiled KV type is unknown or differs from the request "
        "(needs --compiled-readback).",
    )
    args = parser.parse_args(argv)
    points = (
        tuple(int(x) for x in str(args.points).split(",") if x.strip()) if args.points else None
    )
    grow = None
    if args.grow_step is not None or args.grow_max is not None:
        if not (args.grow_step and args.grow_max and args.grow_step > 0 < args.grow_max):
            raise SystemExit("REFUSED -- CC-GROW needs --grow-step and --grow-max > 0")
        grow = {
            "step_tokens": int(args.grow_step),
            "max_tokens": int(args.grow_max),
            "new_tokens": int(args.grow_new_tokens),
        }
    conc = None
    if args.conc_sessions is not None or args.conc_tokens is not None:
        sessions = [int(x) for x in str(args.conc_sessions or "").split(",") if x.strip()]
        if not sessions or not args.conc_tokens or sessions != sorted(set(sessions)):
            raise SystemExit("REFUSED -- CC-CONC needs ascending --conc-sessions and --conc-tokens")
        conc = {
            "sessions": sessions,
            "tokens": int(args.conc_tokens),
            "new_tokens": int(args.conc_new_tokens),
        }
    if grow and conc:
        raise SystemExit("REFUSED -- CC-GROW and CC-CONC are separate cells")
    if (grow or conc) and points:
        raise SystemExit("REFUSED -- --points does not combine with CC-GROW / CC-CONC")
    if args.reject_kv_mismatch and not args.compiled_readback:
        raise SystemExit("REFUSED -- --reject-kv-mismatch needs --compiled-readback")
    if args.dxgi_trace and not args.mem_trace_hz:
        raise SystemExit("REFUSED -- --dxgi-trace needs --mem-trace-hz")
    if args.sched_no_prefix_caching and args.sched_max_batched_tokens is None:
        raise SystemExit("REFUSED -- --sched-no-prefix-caching needs --sched-max-batched-tokens")
    cc_used = any(
        v is not None
        for v in (
            args.low,
            args.resolution,
            points,
            args.turn2_new_tokens,
            args.turn2_repeats,
            args.probe_timeout_s,
            args.mem_trace_hz,
            grow,
            conc,
        )
    ) or bool(
        args.gpu_mem_stats
        or args.compiled_readback
        or args.sched_no_prefix_caching
        or args.dxgi_trace
        or args.reject_kv_mismatch
    )
    if cc_used and not args.cc_cell:
        raise SystemExit("REFUSED -- CC options need --cc-cell")
    if points and any(n < 1 for n in points):
        raise SystemExit("REFUSED -- --points must be positive")
    if args.turn2_new_tokens is not None and args.turn2_new_tokens < 1:
        raise SystemExit("REFUSED -- --turn2-new-tokens must be >= 1")
    if args.turn2_repeats is not None and args.turn2_repeats < 1:
        raise SystemExit("REFUSED -- --turn2-repeats must be >= 1")
    sched = None
    if args.sched_max_batched_tokens is not None or args.sched_cache_size is not None:
        if args.sched_max_batched_tokens is None:
            raise SystemExit("REFUSED -- --sched-cache-size needs --sched-max-batched-tokens")
        sched = {
            "enable_prefix_caching": not args.sched_no_prefix_caching,
            "max_num_batched_tokens": int(args.sched_max_batched_tokens),
        }
        if args.sched_cache_size is not None:
            sched["cache_size"] = int(args.sched_cache_size)
    set_pilot_overrides(scheduler=sched, resident_high=args.high)
    set_cc_overrides(
        cell=args.cc_cell,
        low=args.low,
        resolution=args.resolution,
        points=points,
        turn2_new_tokens=args.turn2_new_tokens,
        turn2_repeats=args.turn2_repeats,
        gpu_mem_stats=bool(args.gpu_mem_stats),
        compiled_readback=bool(args.compiled_readback),
        probe_timeout_s=args.probe_timeout_s,
        mem_trace_hz=args.mem_trace_hz,
        grow=grow,
        conc=conc,
        dxgi_trace=bool(args.dxgi_trace),
        reject_kv_mismatch=bool(args.reject_kv_mismatch),
    )
    if not points and (_resident_high() - _resident_low()) % _resident_resolution() != 0:
        raise SystemExit("REFUSED -- high - low must be a multiple of the resolution")

    if args.smoke:
        return run_resident_limit_smoke(arm=str(args.arm), model_spec=args.model_spec)
    session_id = str(args.session_id) or new_session_id()
    out = args.out or (ROOT / "derived" / "delta_prefill" / session_id)
    print(
        "resident_limit "
        f"arm={args.arm} low={_resident_low()} high={_resident_high()} "
        f"resolution={_resident_resolution()} session={session_id}"
        + (f" cc_cell={args.cc_cell} points={list(points or [])}" if cc_used else ""),
        flush=True,
    )
    if grow or conc:
        return run_cc_series(
            arm=str(args.arm), model_spec=args.model_spec, session_id=session_id, out_dir=out
        )
    return run_resident_limit(
        arm=str(args.arm),
        model_spec=args.model_spec,
        session_id=session_id,
        out_dir=out,
    )


if __name__ == "__main__":
    raise SystemExit(main())
