"""DECODE-MATCH measurement: decode tok/s at identical n for int4 and int8.

Every repeat decodes exactly acceptance.max_new_tokens tokens. The reported
rate is 63 / (t_last - t_first). --smoke loads one pipeline, runs one
generate at a tiny n, prints timing, and writes nothing under derived/.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--model-spec", action="append", type=Path, required=True)
    parser.add_argument("--n", default=",".join(str(n) for n in DECODE_N))
    parser.add_argument("--session-id", default="")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    specs = list(args.model_spec)
    if args.smoke:
        return run_decode_smoke(arm=str(args.arm), model_spec=specs[0])
    requested = tuple(int(part) for part in str(args.n).split(",") if part.strip())
    if requested != DECODE_N:
        raise SystemExit(f"REFUSED -- decode n must be {','.join(str(n) for n in DECODE_N)}")
    session_id = str(args.session_id) or new_session_id()
    out = args.out or (ROOT / "derived" / "c2_ttft" / session_id)
    return run_decode(
        arm=str(args.arm),
        model_specs=specs,
        session_id=session_id,
        out_dir=out,
    )


if __name__ == "__main__":
    raise SystemExit(main())
