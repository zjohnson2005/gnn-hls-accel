#!/usr/bin/env python3
"""Stage D: frontier-model probe on uniform-zero domains (post prompt-fix).

Pre-registered interpretation (frozen before reading results):
  - frontier ≈ 0 AND mini ≈ 0 → still broken; do not accept DEAD
  - frontier scores well AND mini ≈ 0 → DEAD is model-relative (legitimate)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from apu_characterization.cap01.contracts import CandidateRecord, TaskRecord
from apu_characterization.cap01.generation import (
    GenerationConfig,
    build_generation_prompt,
    generate_task_pool,
)
from apu_characterization.cap01.pool import PoolWriter
from apu_characterization.cap01.verifier import verify_candidate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/cap01/frontier_probe_sql_ext.json"

# Fixed samples (not chosen by looking at mini scores after the prompt fix).
SQL_TASKS = ["SQL-001", "SQL-010", "SQL-020", "SQL-030", "SQL-040"]
EXT_TASKS = ["EXT-001", "EXT-010", "EXT-020", "EXT-030", "EXT-040"]
N_CANDIDATES = 4


def _config(model: str, gen_path: Path) -> GenerationConfig:
    payload = json.loads(gen_path.read_text(encoding="utf-8"))
    return GenerationConfig(
        model=model,
        temperature=float(payload["temperature"]),
        max_completion_tokens=int(payload["max_completion_tokens"]),
        target_candidates=N_CANDIDATES,
        prompt_template=str(payload.get("prompt_template", "")),
        prompt_templates=payload.get("prompt_templates") or {},
    )


def _probe_task(task: TaskRecord, config: GenerationConfig, staging_root: Path) -> dict[str, Any]:
    staging = staging_root / f"frontier-{task.task_id}.jsonl"
    if staging.exists():
        staging.unlink()
    writer = PoolWriter(staging, task.task_id, resume=False)
    prompt = build_generation_prompt(task, config)
    generate_task_pool(task, writer, config)
    rows = [
        CandidateRecord.from_dict(json.loads(line))
        for line in staging.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    n_correct = 0
    statuses = []
    for cand in rows:
        verdict = verify_candidate(task, cand)
        statuses.append(verdict.status)
        if verdict.solved:
            n_correct += 1
    return {
        "task_id": task.task_id,
        "domain": task.domain,
        "model": config.model,
        "n": len(rows),
        "n_correct": n_correct,
        "phat": n_correct / max(1, len(rows)),
        "status_counts": {s: statuses.count(s) for s in sorted(set(statuses))},
        "rendered_prompt_sha16": __import__(
            "hashlib"
        ).sha256(prompt.encode()).hexdigest()[:16],
        "prompt_has_schema": (
            "CREATE TABLE" in prompt.upper()
            if task.domain == "TEXT_TO_SQL"
            else ("Target schema:" in prompt and '"properties"' in prompt)
        ),
    }


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
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument(
        "--staging",
        type=Path,
        default=Path("apu_characterization/out/cap01/pools_triage/frontier_staging"),
    )
    args = parser.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    by_id = {t["task_id"]: TaskRecord.from_dict(t) for t in corpus["tasks"]}
    config = _config(args.model, args.generation_config)
    args.staging.mkdir(parents=True, exist_ok=True)

    interpretation_table = {
        "frontier_near_zero_and_mini_near_zero": (
            "task-as-prompted still broken; do NOT accept DEAD; continue diagnosis"
        ),
        "frontier_scores_well_and_mini_near_zero": (
            "DEAD is REAL and model-relative for gpt-4o-mini; accept with evidence"
        ),
    }

    rows = []
    started = time.perf_counter()
    for task_id in SQL_TASKS + EXT_TASKS:
        row = _probe_task(by_id[task_id], config, args.staging)
        rows.append(row)
        print(
            f"{row['task_id']} phat={row['phat']} n_correct={row['n_correct']}/{row['n']}",
            flush=True,
        )

    by_domain: dict[str, list] = {}
    for row in rows:
        by_domain.setdefault(row["domain"], []).append(row)
    summary = {}
    for domain, items in by_domain.items():
        mean_phat = sum(r["phat"] for r in items) / len(items)
        summary[domain] = {
            "tasks": len(items),
            "mean_phat": mean_phat,
            "any_solve": any(r["n_correct"] > 0 for r in items),
            "total_correct": sum(r["n_correct"] for r in items),
            "total_candidates": sum(r["n"] for r in items),
        }

    report = {
        "model": args.model,
        "n_candidates": N_CANDIDATES,
        "interpretation_table_preregistered": interpretation_table,
        "elapsed_s": time.perf_counter() - started,
        "summary": summary,
        "rows": rows,
        "note": (
            "Compare to gpt-4o-mini post-fix triage on the same tasks. "
            "Interpretation applied in decision packet after both are known."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
