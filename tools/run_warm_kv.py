"""WARM-KV measurement: resident turn-2 delta-prefill TTFT at two fixed points.

Per arm, one turn 1 fills n_cached, then three turn-2 repeats use distinct
delta text of 183 tokens. --smoke loads the pipeline, runs one turn 1 and one
turn 2 at a tiny n, prints timing, and writes nothing under derived/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.boot4_session import (  # noqa: E402
    N_CACHED,
    new_session_id,
    run_warm,
    run_warm_smoke,
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
        return run_warm_smoke(arm=str(args.arm), model_spec=args.model_spec)
    session_id = str(args.session_id) or new_session_id()
    out = args.out or (ROOT / "derived" / "delta_prefill" / session_id)
    print(
        f"warm_kv arm={args.arm} n_cached={','.join(str(n) for n in N_CACHED)} session={session_id}",
        flush=True,
    )
    return run_warm(
        arm=str(args.arm), model_spec=args.model_spec, session_id=session_id, out_dir=out
    )


if __name__ == "__main__":
    raise SystemExit(main())
