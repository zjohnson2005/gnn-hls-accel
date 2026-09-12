"""CLI: build corpus (if needed) and run Phase-2 censor analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from censor.build_corpus import build as build_corpus
from censor.corpus import DEFAULT_CORPUS_DIR, load_corpus
from censor.phase2_constants import CostModelParams
from censor.report import run_phase2

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "analysis" / "censor" / "phase2"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Phase-2 censor engine: cost frictions + Manski quality bounds"
    )
    p.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help="Read-only normalized corpus directory",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-boot", type=int, default=500)
    p.add_argument(
        "--build-corpus",
        action="store_true",
        help="Rebuild corpus/normalized from OA-01 + TurnTrace before running",
    )
    p.add_argument(
        "--oa01-only",
        action="store_true",
        help="With --build-corpus, skip TurnTrace sources",
    )
    p.add_argument(
        "--router-type",
        choices=["rule", "embedding", "classifier", "llm"],
        default="embedding",
    )
    args = p.parse_args(argv)

    if args.build_corpus or not Path(args.corpus).is_dir():
        print("Building normalized corpus…", flush=True)
        build_corpus(
            out_dir=Path(args.corpus),
            include_turntrace=not args.oa01_only,
        )

    trajectories = load_corpus(args.corpus)
    # Prefer combined file if present — load_corpus already loads all jsonl;
    # drop duplicates by trajectory_id (per-scaffold files + combined).
    seen: set[str] = set()
    unique = []
    for tr in trajectories:
        if tr.trajectory_id in seen:
            continue
        seen.add(tr.trajectory_id)
        unique.append(tr)
    trajectories = unique

    params = CostModelParams()
    params.f1.router_type = args.router_type

    print(
        f"Running Phase-2 on {len(trajectories)} trajectories -> {args.out}",
        flush=True,
    )
    # F4 label on stdout for every F4-dependent run
    print("F4 UNMEASURED", flush=True)
    print("invariance bias UNMEASURED", flush=True)

    paths = run_phase2(
        trajectories,
        Path(args.out),
        params=params,
        seed=args.seed,
        n_boot=args.n_boot,
    )
    for name, path in paths.items():
        print(f"  wrote {name}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
