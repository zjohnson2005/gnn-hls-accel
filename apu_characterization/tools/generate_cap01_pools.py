#!/usr/bin/env python3
"""Generate and freeze CAP-01 candidate pools (OpenAI live or synthetic_debug).

Cost-control rule (execution prompt): measure the first domain's spend before
launching the remaining four. Synthetic_debug is ledgered for debug_only
preflight only — not capability_scaling publication.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from apu_characterization.cap01.contracts import (
    TaskRecord,
    sha256_bytes,
    sha256_json,
)
from apu_characterization.cap01.generation import (
    DEFAULT_PROMPT_TEMPLATE,
    GenerationConfig,
    GenerationError,
    generate_task_pool,
)
from apu_characterization.cap01.generation_gate import assert_generation_cleared
from apu_characterization.cap01.pool import PoolWriter, freeze_pool


def _load_tasks(corpus_path: Path) -> list[TaskRecord]:
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    tasks = payload.get("tasks") or []
    return [TaskRecord.from_dict(item) for item in tasks]


def _correct_content(task: TaskRecord) -> str:
    index = int(task.task_id.rsplit("-", 1)[-1])
    if task.domain == "MATH":
        return str(index * 2)
    if task.domain == "CODE":
        return "def add(a, b):\n    return a + b\n"
    if task.domain == "FUNCTION_CALLING":
        return json.dumps(
            {"name": "lookup", "arguments": {"q": index}}, separators=(",", ":")
        )
    if task.domain == "TEXT_TO_SQL":
        return "SELECT value FROM items WHERE id = 1"
    if task.domain == "STRUCTURED_EXTRACTION":
        return json.dumps(
            {"id": index, "label": f"item-{index}", "date": "01/15/2024"},
            separators=(",", ":"),
        )
    raise ValueError(task.domain)


def _wrong_content(task: TaskRecord, salt: int) -> str:
    index = int(task.task_id.rsplit("-", 1)[-1])
    # Unique per ordinal so Axis-2 duplicate_rate stays well under 20%.
    tag = f"v{salt}"
    if task.domain == "MATH":
        return f"{index * 2 + 1 + (salt % 97)} /*{tag}*/"
    if task.domain == "CODE":
        return (
            f"def add(a, b):\n"
            f"    # {tag}\n"
            f"    return a - b - {salt % 13}\n"
        )
    if task.domain == "FUNCTION_CALLING":
        return json.dumps(
            {
                "name": "lookup",
                "arguments": {"q": index + 1 + (salt % 3), "nonce": tag},
            },
            separators=(",", ":"),
        )
    if task.domain == "TEXT_TO_SQL":
        return f"SELECT value FROM items WHERE id = {999 + (salt % 50)} -- {tag}"
    if task.domain == "STRUCTURED_EXTRACTION":
        return json.dumps(
            {
                "id": index + 1,
                "label": f"wrong-{index}-{tag}",
                "date": "02/01/2024",
                "nonce": tag,
            },
            separators=(",", ":"),
        )
    raise ValueError(task.domain)


def _synthetic_request_fn(task: TaskRecord, target: int, solve_rate: float = 0.12):
    """Return a request_fn that emits deterministic correct/wrong candidates.

    Wrong answers are unique per ordinal so Axis-2 duplicate_rate stays <20%.
    Correct-answer mass is capped (default 12%) because identical verifying
    strings would otherwise dominate the duplicate rate.
    """

    rng = random.Random(sha256_json({"task": task.task_id, "backend": "synthetic"})[:16])
    correct = _correct_content(task)
    emitted = {"n": 0}

    def request_fn(_payload: dict[str, Any]) -> dict[str, Any]:
        ordinal = emitted["n"]
        emitted["n"] += 1
        if ordinal >= target:
            raise GenerationError("synthetic generator exhausted")
        if ordinal < 4:
            content = correct if ordinal == 0 else _wrong_content(task, ordinal)
        else:
            content = (
                correct
                if rng.random() < solve_rate
                else _wrong_content(task, ordinal)
            )
        prompt_tokens = 40 + len(task.prompt) // 4
        completion_tokens = max(1, len(content) // 4)
        return {
            "id": f"synthetic-{task.task_id}-{ordinal}",
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }

    return request_fn


def _generate_one(
    task: TaskRecord,
    *,
    pools_root: Path,
    config: GenerationConfig,
    backend: str,
) -> dict[str, Any]:
    staging = pools_root / "staging" / f"{task.task_id}.jsonl"
    frozen = pools_root / "frozen" / f"{task.task_id}.jsonl"
    manifest = pools_root / "frozen" / f"{task.task_id}.manifest.json"
    if frozen.is_file() and manifest.is_file():
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        return {
            "task_id": task.task_id,
            "domain": task.domain,
            "candidate_count": int(payload["candidate_count"]),
            "status": "already_frozen",
            "task_pool_sha256": payload["task_pool_sha256"],
        }
    writer = PoolWriter(staging, task.task_id, resume=True)
    request_fn = (
        None
        if backend == "openai"
        else _synthetic_request_fn(task, config.target_candidates)
    )
    started = time.perf_counter()
    generate_task_pool(task, writer, config, request_fn=request_fn)
    metadata = freeze_pool(
        writer,
        frozen,
        manifest,
        generation_model=config.model,
        temperature=config.temperature,
        prompt_template_sha256=config.prompt_template_sha256,
        minimum_candidates=config.target_candidates,
        generation_backend=backend,
    )
    elapsed = time.perf_counter() - started
    prompt_tokens = sum(c.prompt_tokens for c in metadata.candidates)
    completion_tokens = sum(c.completion_tokens for c in metadata.candidates)
    return {
        "task_id": task.task_id,
        "domain": task.domain,
        "candidate_count": len(metadata.candidates),
        "status": "frozen",
        "task_pool_sha256": metadata.pool_sha256(),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "elapsed_s": elapsed,
    }


def _write_root_manifest(
    pools_root: Path,
    results: list[dict[str, Any]],
    backend: str,
    *,
    locked_protocol_meta: Mapping[str, Any] | None = None,
) -> Path:
    path = pools_root / "manifest.json"
    tasks = [
        {
            "task_id": row["task_id"],
            "candidate_count": row["candidate_count"],
            "task_pool_sha256": row["task_pool_sha256"],
            "domain": row["domain"],
        }
        for row in sorted(results, key=lambda item: item["task_id"])
    ]
    payload = {
        "generation_backend": backend,
        "result_validity": "capability_scaling" if backend == "openai" else "debug_only",
        "task_count": len(tasks),
        "minimum_candidates_per_task": 2048,
        "tasks": tasks,
    }
    if locked_protocol_meta:
        payload["locked_protocol_provenance"] = dict(locked_protocol_meta)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument(
        "--pools-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/pools"),
    )
    parser.add_argument(
        "--backend",
        choices=("openai", "synthetic_debug"),
        default="synthetic_debug",
    )
    parser.add_argument(
        "--locked-protocol",
        type=Path,
        default=Path("apu_characterization/out/cap01/protocol_cap01_v2.locked.json"),
    )
    parser.add_argument(
        "--generation-config",
        type=Path,
        default=Path("apu_characterization/out/cap01/generation_config.json"),
    )
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--target-candidates", type=int, default=2048)
    parser.add_argument("--domain", default="", help="Optional single-domain filter")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--openai-probe-candidates",
        type=int,
        default=0,
        help="If >0 with openai backend, only generate this many candidates on "
        "the first task and print a cost projection, then exit.",
    )
    parser.add_argument(
        "--budget-usd-ceiling",
        type=float,
        default=50.0,
        help="Stop before remaining domains if projected total exceeds this.",
    )
    args = parser.parse_args()

    if args.backend == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")

    locked_protocol_meta: dict[str, Any] = {}
    if args.backend == "openai":
        locked = assert_generation_cleared(
            locked_protocol_path=args.locked_protocol,
            corpus_manifest_path=args.corpus,
            generation_config_path=args.generation_config,
        )
        lock_fields = locked.get("lock_fields") or {}
        locked_protocol_meta = {
            "locked_protocol_path": str(args.locked_protocol),
            "locked_protocol_file_sha256": sha256_bytes(args.locked_protocol.read_bytes()),
            "lock_phase": locked.get("lock_phase"),
            "corpus_manifest_sha256": lock_fields.get("corpus_manifest_sha256"),
            "generation_config_sha256": lock_fields.get("generation_config_sha256"),
        }
        print(json.dumps(locked_protocol_meta, indent=2, sort_keys=True))
        generation_payload = json.loads(
            args.generation_config.read_text(encoding="utf-8")
        )
        config = GenerationConfig(
            model=str(generation_payload["model"]),
            temperature=float(generation_payload["temperature"]),
            max_completion_tokens=int(generation_payload["max_completion_tokens"]),
            target_candidates=int(
                generation_payload.get("target_candidates", args.target_candidates)
            ),
            prompt_template=str(
                generation_payload.get("prompt_template", DEFAULT_PROMPT_TEMPLATE)
            ),
            prompt_templates=generation_payload.get("prompt_templates") or {},
            endpoint=str(generation_payload.get("endpoint", GenerationConfig.endpoint)),
            timeout_seconds=float(
                generation_payload.get("timeout_seconds", GenerationConfig.timeout_seconds)
            ),
        )
        config.validate()
    else:
        config = GenerationConfig(
            model="synthetic_debug_v1",
            temperature=1.0,
            max_completion_tokens=256,
            target_candidates=args.target_candidates,
        )
        config.validate()

    tasks = _load_tasks(args.corpus)
    if args.domain:
        tasks = [task for task in tasks if task.domain == args.domain]
        if not tasks:
            raise SystemExit(f"no tasks for domain {args.domain}")

    model = config.model
    args.pools_root.mkdir(parents=True, exist_ok=True)
    if args.backend != "openai":
        (args.pools_root / "generation_config.json").write_text(
            json.dumps(
                {
                    **config.public_dict(),
                    "generation_backend": args.backend,
                    "digest": config.digest(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.backend == "openai" and args.openai_probe_candidates > 0:
        probe_task = tasks[0]
        probe_config = GenerationConfig(
            model=config.model,
            temperature=config.temperature,
            max_completion_tokens=config.max_completion_tokens,
            target_candidates=args.openai_probe_candidates,
            prompt_template=config.prompt_template,
            prompt_templates=config.prompt_templates,
            endpoint=config.endpoint,
            timeout_seconds=config.timeout_seconds,
        )
        staging = args.pools_root / "staging" / f"probe-{probe_task.task_id}.jsonl"
        if staging.exists():
            staging.unlink()
        writer = PoolWriter(staging, probe_task.task_id, resume=False)
        started = time.perf_counter()
        generate_task_pool(probe_task, writer, probe_config)
        elapsed = time.perf_counter() - started
        prompt_tokens = sum(c.prompt_tokens for c in writer.candidates)
        completion_tokens = sum(c.completion_tokens for c in writer.candidates)
        per_candidate_prompt = prompt_tokens / max(1, len(writer.candidates))
        per_candidate_completion = completion_tokens / max(1, len(writer.candidates))
        total_candidates = len(tasks) * args.target_candidates
        # gpt-4o-mini list prices (USD / 1M tokens) — recorded for projection only.
        input_rate = 0.15
        output_rate = 0.60
        projected_prompt = total_candidates * per_candidate_prompt
        projected_completion = total_candidates * per_candidate_completion
        projected_usd = (
            projected_prompt / 1e6 * input_rate
            + projected_completion / 1e6 * output_rate
        )
        projected_hours = (elapsed / max(1, len(writer.candidates))) * total_candidates / 3600.0
        report = {
            "probe_task_id": probe_task.task_id,
            "probe_domain": probe_task.domain,
            "probe_candidates": len(writer.candidates),
            "probe_elapsed_s": elapsed,
            **locked_protocol_meta,
            "per_candidate_prompt_tokens": per_candidate_prompt,
            "per_candidate_completion_tokens": per_candidate_completion,
            "projected_total_candidates": total_candidates,
            "projected_prompt_tokens": projected_prompt,
            "projected_completion_tokens": projected_completion,
            "projected_usd_gpt4o_mini": projected_usd,
            "projected_serial_hours": projected_hours,
            "budget_usd_ceiling": args.budget_usd_ceiling,
            "within_budget": projected_usd <= args.budget_usd_ceiling,
        }
        out = args.pools_root / "openai_cost_projection.json"
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        if projected_usd > args.budget_usd_ceiling:
            raise SystemExit(
                "COST GATE: projected spend exceeds ceiling; not launching remaining "
                "domains. Options: raise ceiling, amend protocol pool depth with "
                "died-ledger entry, or continue domain-by-domain with explicit approval."
            )
        raise SystemExit(0)

    # Domain-ordered generation: first domain completes before the rest (cost gate).
    by_domain: dict[str, list[TaskRecord]] = {}
    for task in tasks:
        by_domain.setdefault(task.domain, []).append(task)
    domain_order = list(by_domain)
    all_results: list[dict[str, Any]] = []

    for domain_index, domain in enumerate(domain_order):
        domain_tasks = by_domain[domain]
        print(f"=== generating domain {domain} ({len(domain_tasks)} tasks) ===")
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {
                pool.submit(
                    _generate_one,
                    task,
                    pools_root=args.pools_root,
                    config=config,
                    backend=args.backend,
                ): task
                for task in domain_tasks
            }
            for future in as_completed(futures):
                row = future.result()
                results.append(row)
                print(
                    f"{row['status']} {row['task_id']} "
                    f"n={row['candidate_count']} sha={row['task_pool_sha256'][:12]}"
                )
        all_results.extend(results)
        if (
            args.backend == "openai"
            and domain_index == 0
            and len(domain_order) > 1
        ):
            prompt_tokens = sum(int(r.get("prompt_tokens") or 0) for r in results)
            completion_tokens = sum(int(r.get("completion_tokens") or 0) for r in results)
            domain_usd = prompt_tokens / 1e6 * 0.15 + completion_tokens / 1e6 * 0.60
            projected_total = domain_usd * len(domain_order)
            gate = {
                "first_domain": domain,
                "first_domain_usd": domain_usd,
                "projected_total_usd": projected_total,
                "budget_usd_ceiling": args.budget_usd_ceiling,
                "within_budget": projected_total <= args.budget_usd_ceiling,
            }
            (args.pools_root / "first_domain_cost_gate.json").write_text(
                json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(json.dumps(gate, indent=2))
            if projected_total > args.budget_usd_ceiling:
                raise SystemExit(
                    "COST GATE after first domain: projected total exceeds ceiling. "
                    "Remaining domains not launched."
                )

    manifest = _write_root_manifest(
        args.pools_root,
        all_results,
        args.backend,
        locked_protocol_meta=locked_protocol_meta or None,
    )
    print(f"pool_manifest={manifest}")
    print(f"frozen_tasks={len(all_results)}")


if __name__ == "__main__":
    main()
