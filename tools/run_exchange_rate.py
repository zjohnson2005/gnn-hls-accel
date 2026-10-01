"""P0 exchange rate: what a 10 s time-to-action budget can buy.

GPU and CPU, 4B-int4, u8, RESIDENT. --smoke loads the GPU pipeline once at
the configured smoke length and writes nothing under derived/.
This file does not open a preregistration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.exchange_rate_session import (  # noqa: E402
    load_exchange_config,
    main_ids,
    run_exchange_rate,
    run_exchange_rate_smoke,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-spec", required=True, type=Path)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_exchange_rate_smoke(model_spec=args.model_spec)
    cfg = load_exchange_config()
    session_id = str(args.session_id) or main_ids()
    out = args.out or (ROOT / "derived" / "exchange_rate" / session_id)
    print(
        "exchange_rate "
        f"contexts={','.join(str(n) for n in cfg['context_tokens'])} "
        f"devices={','.join(item['id'] for item in cfg['devices'])} "
        f"session={session_id}",
        flush=True,
    )
    return run_exchange_rate(model_spec=args.model_spec, session_id=session_id, out_dir=out)


if __name__ == "__main__":
    raise SystemExit(main())
