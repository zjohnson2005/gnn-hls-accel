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
    args = parser.parse_args(argv)
    points = (
        tuple(int(x) for x in str(args.points).split(",") if x.strip()) if args.points else None
    )
    cc_used = any(
        v is not None
        for v in (args.low, args.resolution, points, args.turn2_new_tokens, args.turn2_repeats)
    ) or bool(args.gpu_mem_stats or args.compiled_readback)
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
            "enable_prefix_caching": True,
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
    return run_resident_limit(
        arm=str(args.arm),
        model_spec=args.model_spec,
        session_id=session_id,
        out_dir=out,
    )


if __name__ == "__main__":
    raise SystemExit(main())
