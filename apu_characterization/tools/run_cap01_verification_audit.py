"""Run the CAP-01 full behavioral verification audit on local hardware."""

from __future__ import annotations

import argparse
from pathlib import Path

from apu_characterization.cap01.verification_audit import write_verification_audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("apu_characterization/cap01/cap01_verification_audit.md"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("apu_characterization/out/cap01/verification_audit.json"),
    )
    parser.add_argument("--axis1-repeats", type=int, default=200)
    args = parser.parse_args()
    aggregate = write_verification_audit(
        args.output_md,
        args.output_json,
        axis1_repeats=args.axis1_repeats,
    )
    summary = aggregate["summary"]
    print(f"PASS={summary['PASS']} FAIL={summary['FAIL']} FLAGGED={summary['FLAGGED']}")
    print(f"p3_eligible={aggregate['p3_eligible']}")
    print(args.output_md)
    print(args.output_json)


if __name__ == "__main__":
    main()
