"""Freeze CAP-01 P0 manifests into the measurement protocol."""

from __future__ import annotations

import argparse
from pathlib import Path

from apu_characterization.cap01.protocol_lock import (
    build_locked_protocol,
    build_pre_generation_locked_protocol,
    write_locked_protocol,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--generation-config", type=Path, required=True)
    parser.add_argument("--verifier-pin-manifest", type=Path, required=True)
    parser.add_argument(
        "--pre-generation",
        action="store_true",
        help="Lock corpus + generation config before live pool generation.",
    )
    parser.add_argument("--pool-manifest", type=Path)
    parser.add_argument("--classification-manifest", type=Path)
    parser.add_argument(
        "--expectations",
        type=Path,
        default=Path("apu_characterization/PREDICTIONS_CAP01.md"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "apu_characterization/out/cap01/protocol_cap01_v2.locked.json"
        ),
    )
    args = parser.parse_args()
    if args.pre_generation:
        protocol = build_pre_generation_locked_protocol(
            corpus_manifest=args.corpus_manifest,
            generation_config=args.generation_config,
            verifier_pin_manifest=args.verifier_pin_manifest,
            expectations=args.expectations,
        )
    else:
        if not args.pool_manifest or not args.classification_manifest:
            raise SystemExit(
                "post-generation lock requires --pool-manifest and "
                "--classification-manifest (or use --pre-generation)"
            )
        protocol = build_locked_protocol(
            corpus_manifest=args.corpus_manifest,
            pool_manifest=args.pool_manifest,
            classification_manifest=args.classification_manifest,
            generation_config=args.generation_config,
            verifier_pin_manifest=args.verifier_pin_manifest,
            expectations=args.expectations,
        )
    digest = write_locked_protocol(args.output, protocol)
    print(f"locked_protocol={args.output}")
    print(f"sha256={digest}")
    print(
        "all_task_cell_runs="
        f"{protocol['locked_schedule']['all_task_cell_runs']}"
    )
    print(
        "serial_budget_upper_bound_seconds="
        f"{protocol['locked_schedule']['serial_budget_upper_bound_seconds']:.0f}"
    )


if __name__ == "__main__":
    main()
