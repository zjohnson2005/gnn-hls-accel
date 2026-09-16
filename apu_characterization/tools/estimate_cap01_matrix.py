"""Record the CAP-01 v2 serial-hours estimate from measured P2 constants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apu_characterization.cap01.contracts import load_protocol
from apu_characterization.cap01.schedule import estimate_matrix_hours


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-ms", type=float, required=True)
    parser.add_argument("--cooldown-ms", type=float, required=True)
    parser.add_argument(
        "--drop-off-tier-domain",
        action="append",
        default=[],
        choices=["CODE", "MATH"],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    estimate = estimate_matrix_hours(
        load_protocol(),
        setup_ms=args.setup_ms,
        cooldown_ms=args.cooldown_ms,
        drop_off_tier_domains=args.drop_off_tier_domain,
    )
    payload = {"protocol_version": "cap01_v2", "matrix_hours_estimate": estimate}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"serial_hours_total={estimate['serial_hours_total']:.3f}")
    print(args.output)


if __name__ == "__main__":
    main()
