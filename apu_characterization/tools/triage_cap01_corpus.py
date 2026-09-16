#!/usr/bin/env python3
"""CAP-01 Stage-2 full-corpus triage probe (16 candidates/task) + verify.

Must run only AFTER depth_triage amendment is frozen in the locked protocol.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from apu_characterization.cap01.contracts import CandidateRecord, TaskRecord, sha256_json
from apu_characterization.cap01.depth_triage import (
    TRIAGE_CANDIDATES,
    VERIFIER_BLOCKED_DOMAINS,
    generation_depth_for_band,
    triage_band,
)
from apu_characterization.cap01.generation import (
    DEFAULT_PROMPT_TEMPLATE,
    GenerationConfig,
    generate_task_pool,
)
from apu_characterization.cap01.generation_gate import assert_generation_cleared
from apu_characterization.cap01.pool import PoolWriter
from apu_characterization.cap01.verifier import verify_candidate

INPUT_USD_PER_MTOK = 0.15
OUTPUT_USD_PER_MTOK = 0.60


def _load_tasks(corpus_path: Path) -> list[TaskRecord]:
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    return [TaskRecord.from_dict(task) for task in payload["tasks"]]


def _verify_pool(task: TaskRecord, staging: Path) -> dict[str, Any]:
    rows = [
        CandidateRecord.from_dict(json.loads(line))
        for line in staging.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    n_correct = 0
    statuses: list[str] = []
    contents: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    verify_errors = 0
    for cand in rows:
        contents.append(cand.content)
        prompt_tokens += cand.prompt_tokens
        completion_tokens += cand.completion_tokens
        if task.domain in VERIFIER_BLOCKED_DOMAINS:
            statuses.append("verifier_blocked")
            continue
        try:
            verdict = verify_candidate(task, cand)
            statuses.append(verdict.status)
            if verdict.solved:
                n_correct += 1
        except Exception as exc:  # noqa: BLE001 — triage must continue
            statuses.append(f"error:{type(exc).__name__}")
            verify_errors += 1
    n = len(rows)
    if task.domain in VERIFIER_BLOCKED_DOMAINS:
        band = "verifier_blocked_full_depth"
        phat = None
    elif verify_errors == n:
        band = "verifier_error"
        phat = None
    else:
        measurable = n - verify_errors
        phat = n_correct / max(1, measurable)
        band = triage_band(phat, n=measurable)
    depth = generation_depth_for_band(
        "SCALING_band" if band in {"verifier_blocked_full_depth", "verifier_error"} else band,
        domain=task.domain,
    )
    if band in {"verifier_blocked_full_depth", "verifier_error"}:
        depth = 2048
    return {
        "task_id": task.task_id,
        "domain": task.domain,
        "n": n,
        "n_correct": n_correct,
        "phat": phat,
        "unique_strings": len(set(contents)),
        "band": band,
        "generation_depth": depth,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "verify_errors": verify_errors,
        "status_counts": {
            status: statuses.count(status) for status in sorted(set(statuses))
        },
    }


def _process_task(
    task: TaskRecord,
    config: GenerationConfig,
    pools_root: Path,
    *,
    verify_only: bool,
) -> dict[str, Any]:
    staging = pools_root / "staging" / f"triage-{task.task_id}.jsonl"
    staging.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if verify_only:
        if not staging.is_file():
            raise FileNotFoundError(f"verify-only missing staging: {staging}")
    else:
        if staging.exists():
            staging.unlink()
        writer = PoolWriter(staging, task.task_id, resume=False)
        generate_task_pool(task, writer, config)
    elapsed = time.perf_counter() - started
    row = _verify_pool(task, staging)
    row["elapsed_s"] = elapsed
    row["verify_only"] = verify_only
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument(
        "--generation-config",
        type=Path,
        default=Path("apu_characterization/out/cap01/generation_config.json"),
    )
    parser.add_argument(
        "--locked-protocol",
        type=Path,
        default=Path("apu_characterization/out/cap01/protocol_cap01_v2.locked.json"),
    )
    parser.add_argument(
        "--pools-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/pools_triage"),
    )
    parser.add_argument("--triage-candidates", type=int, default=TRIAGE_CANDIDATES)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--domain", default="")
    parser.add_argument("--limit-tasks", type=int, default=0)
    parser.add_argument(
        "--report-name",
        default="triage_report.json",
        help=(
            "Append-only report filename under pools-root. Pass a new name "
            "(e.g. triage_report_v2_post_verifier_fix.json) to preserve prior "
            "triage_report.json history."
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help=(
            "Re-score existing staging JSONLs with the current verifier; do not "
            "call the generation backend. Use after verifier repairs."
        ),
    )
    args = parser.parse_args()

    if not args.verify_only and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")

    locked = assert_generation_cleared(
        locked_protocol_path=args.locked_protocol,
        corpus_manifest_path=args.corpus,
        generation_config_path=args.generation_config,
    )
    gen_payload = json.loads(args.generation_config.read_text(encoding="utf-8"))
    if "depth_triage" not in gen_payload:
        raise SystemExit("generation_config missing frozen depth_triage policy")

    config = GenerationConfig(
        model=str(gen_payload["model"]),
        temperature=float(gen_payload["temperature"]),
        max_completion_tokens=int(gen_payload["max_completion_tokens"]),
        target_candidates=args.triage_candidates,
        prompt_template=str(
            gen_payload.get("prompt_template", DEFAULT_PROMPT_TEMPLATE)
        ),
        prompt_templates=gen_payload.get("prompt_templates") or {},
    )
    config.validate()

    tasks = _load_tasks(args.corpus)
    if args.domain:
        wanted = {item.strip() for item in args.domain.split(",") if item.strip()}
        tasks = [task for task in tasks if task.domain in wanted]
    if args.limit_tasks > 0:
        tasks = tasks[: args.limit_tasks]

    args.pools_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _process_task,
                task,
                config,
                args.pools_root,
                verify_only=args.verify_only,
            ): task
            for task in tasks
        }
        for index, future in enumerate(as_completed(futures), start=1):
            row = future.result()
            rows.append(row)
            print(
                f"[{index}/{len(tasks)}] {row['task_id']} "
                f"phat={row['phat']} band={row['band']} depth={row['generation_depth']}",
                flush=True,
            )

    rows.sort(key=lambda item: item["task_id"])
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_domain.setdefault(row["domain"], []).append(row)

    domain_stats: dict[str, Any] = {}
    for domain, domain_rows in by_domain.items():
        measurable = [row for row in domain_rows if row["phat"] is not None]
        prompt = sum(row["prompt_tokens"] for row in domain_rows)
        completion = sum(row["completion_tokens"] for row in domain_rows)
        n_cands = sum(row["n"] for row in domain_rows)
        domain_stats[domain] = {
            "tasks": len(domain_rows),
            "candidates": n_cands,
            "per_candidate_prompt_tokens": prompt / max(1, n_cands),
            "per_candidate_completion_tokens": completion / max(1, n_cands),
            "band_counts": {
                band: sum(1 for row in domain_rows if row["band"] == band)
                for band in sorted({row["band"] for row in domain_rows})
            },
            "scaling_band_count": sum(
                1 for row in measurable if row["band"] == "SCALING_band"
            ),
            "probable_SATURATED": sum(
                1 for row in measurable if row["band"] == "probable_SATURATED"
            ),
            "probable_DEAD": sum(
                1 for row in measurable if row["band"] == "probable_DEAD"
            ),
            "mean_phat": (
                sum(float(row["phat"]) for row in measurable) / len(measurable)
                if measurable
                else None
            ),
        }

    # Full-generation projection under frozen depth rule.
    projected_prompt = 0.0
    projected_completion = 0.0
    projected_candidates = 0
    for row in rows:
        domain = row["domain"]
        depth = int(row["generation_depth"])
        stats = domain_stats[domain]
        projected_candidates += depth
        projected_prompt += depth * float(stats["per_candidate_prompt_tokens"])
        projected_completion += depth * float(stats["per_candidate_completion_tokens"])
    projected_usd = (
        projected_prompt / 1e6 * INPUT_USD_PER_MTOK
        + projected_completion / 1e6 * OUTPUT_USD_PER_MTOK
    )
    uniform_candidates = len(rows) * 2048
    # Contrast: if every task used this domain's measured tokens at uniform 2048.
    uniform_prompt = 0.0
    uniform_completion = 0.0
    for row in rows:
        stats = domain_stats[row["domain"]]
        uniform_prompt += 2048 * float(stats["per_candidate_prompt_tokens"])
        uniform_completion += 2048 * float(stats["per_candidate_completion_tokens"])
    uniform_usd = (
        uniform_prompt / 1e6 * INPUT_USD_PER_MTOK
        + uniform_completion / 1e6 * OUTPUT_USD_PER_MTOK
    )

    report = {
        "triage_candidates": args.triage_candidates,
        "verify_only": bool(args.verify_only),
        "domains": sorted({row["domain"] for row in rows}),
        "tasks": len(rows),
        "elapsed_s": time.perf_counter() - started,
        "locked_protocol_file_sha256": __import__(
            "apu_characterization.cap01.contracts", fromlist=["sha256_bytes"]
        ).sha256_bytes(args.locked_protocol.read_bytes()),
        "generation_config_sha256": locked["lock_fields"]["generation_config_sha256"],
        "corpus_manifest_sha256": locked["lock_fields"]["corpus_manifest_sha256"],
        "domain_stats": domain_stats,
        "projection": {
            "depth_triage_total_candidates": projected_candidates,
            "depth_triage_projected_usd": projected_usd,
            "uniform_2048_total_candidates": uniform_candidates,
            "uniform_2048_projected_usd": uniform_usd,
            "note": (
                "Projection covers only domains in this report; merge with "
                "prior MATH triage for a five-domain total."
                if args.domain
                else "Projection covers all domains in this report."
            ),
        },
        "rows": rows,
    }
    out = args.pools_root / args.report_name
    if out.exists():
        raise SystemExit(
            f"refusing to overwrite existing triage report: {out} "
            "(choose a new --report-name for append-only history)"
        )
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "rows"}, indent=2, sort_keys=True))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
