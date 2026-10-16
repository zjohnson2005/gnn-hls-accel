"""DECODE-MATCH measurement: decode tok/s at identical n for int4 and int8.

Every repeat decodes exactly acceptance.max_new_tokens tokens. The reported
rate is 63 / (t_last - t_first). --smoke loads one pipeline, runs one
generate at a tiny n, prints timing, and writes nothing under derived/.

--pilot {p9,p2} (DEMO-2 pilots, docs/amendments/DEMO2_PILOTS_2026-10-16.md
section 5) allows exactly that pilot's registered n list and nothing else,
one model spec, and writes under derived/demo2_pilots/<pilot>_<session_id>.
P9 drift: 12 x n=3500 in time order. P2: 3500,12000,20000. Without --pilot
the behaviour is unchanged (n must be DECODE_N, both model specs).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.boot4_session import (  # noqa: E402
    DECODE_N,
    new_session_id,
    run_decode,
    run_decode_smoke,
)

PILOT_N: dict[str, tuple[int, ...]] = {
    "p9": (3500,) * 12,
    "p2": (3500, 12000, 20000),
}
PILOT_ROOT = ROOT / "derived" / "demo2_pilots"


def _fmt(values: tuple[int, ...]) -> str:
    return ",".join(str(n) for n in values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--model-spec", action="append", type=Path, required=True)
    parser.add_argument("--n", default=None)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--pilot", choices=sorted(PILOT_N), default=None)
    args = parser.parse_args(argv)
    specs = list(args.model_spec)
    if args.smoke:
        return run_decode_smoke(arm=str(args.arm), model_spec=specs[0])
    allowed = PILOT_N[args.pilot] if args.pilot else DECODE_N
    requested = (
        allowed
        if args.n is None
        else tuple(int(part) for part in str(args.n).split(",") if part.strip())
    )
    if requested != allowed:
        what = f"pilot {args.pilot}" if args.pilot else "decode"
        raise SystemExit(f"REFUSED -- {what} n must be {_fmt(allowed)}")
    session_id = str(args.session_id) or new_session_id()
    if args.pilot:
        if args.out is not None:
            raise SystemExit("REFUSED -- --pilot writes under derived/demo2_pilots/; no --out")
        if len(specs) != 1:
            raise SystemExit("REFUSED -- --pilot takes exactly one --model-spec")
        out = PILOT_ROOT / f"{args.pilot}_{session_id}"
        return run_decode(
            arm=str(args.arm),
            model_specs=specs,
            session_id=session_id,
            out_dir=out,
            n_list=requested,
            pilot=str(args.pilot),
        )
    out = args.out or (ROOT / "derived" / "c2_ttft" / session_id)
    return run_decode(
        arm=str(args.arm),
        model_specs=specs,
        session_id=session_id,
        out_dir=out,
    )


if __name__ == "__main__":
    raise SystemExit(main())
