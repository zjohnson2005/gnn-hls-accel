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
    RESIDENT_LOW,
    RESIDENT_RESOLUTION,
    _resident_high,
    new_session_id,
    run_resident_limit,
    run_resident_limit_smoke,
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
    args = parser.parse_args(argv)
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

    if args.smoke:
        return run_resident_limit_smoke(arm=str(args.arm), model_spec=args.model_spec)
    session_id = str(args.session_id) or new_session_id()
    out = args.out or (ROOT / "derived" / "delta_prefill" / session_id)
    print(
        "resident_limit "
        f"arm={args.arm} low={RESIDENT_LOW} high={_resident_high()} "
        f"resolution={RESIDENT_RESOLUTION} session={session_id}",
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
