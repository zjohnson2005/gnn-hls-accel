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
    new_session_id,
    run_resident_limit,
    run_resident_limit_smoke,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--model-spec", required=True, type=Path)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_resident_limit_smoke(arm=str(args.arm), model_spec=args.model_spec)
    session_id = str(args.session_id) or new_session_id()
    out = args.out or (ROOT / "derived" / "delta_prefill" / session_id)
    print(
        "resident_limit "
        f"arm={args.arm} low={RESIDENT_LOW} high={RESIDENT_HIGH} "
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
