"""Stage B: meaning-preserving perturbations of gold must still verify."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from apu_characterization.cap01.contracts import CandidateRecord, TaskRecord
from apu_characterization.cap01.verifier import verify_candidate
from apu_characterization.tools.audit_cap01_verifier_ground_truth import (
    _load_humaneval,
    gold_content,
    materialize_fc_gold,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "out/cap01/corpus.json"
HUMANEVAL = ROOT / "out/cap01/live_sources/humanevalplus-hf/test.jsonl"
OUT = ROOT / "out/cap01/perturbed_gold_audit.json"

SAMPLES = {
    "TEXT_TO_SQL": ["SQL-001", "SQL-002", "SQL-003", "SQL-004", "SQL-005"],
    "STRUCTURED_EXTRACTION": ["EXT-001", "EXT-002", "EXT-003", "EXT-004", "EXT-005"],
    "FUNCTION_CALLING": ["FC-001", "FC-003", "FC-005", "FC-009", "FC-012"],
    "MATH": ["MATH-001", "MATH-002", "MATH-003", "MATH-004", "MATH-005"],
    "CODE": ["CODE-001", "CODE-002", "CODE-003", "CODE-004", "CODE-005"],
}


def _shuffle_json_keys(value: Any, rng: random.Random) -> Any:
    if isinstance(value, dict):
        items = list(value.items())
        rng.shuffle(items)
        return {k: _shuffle_json_keys(v, rng) for k, v in items}
    if isinstance(value, list):
        return [_shuffle_json_keys(item, rng) for item in value]
    return value


def perturb_ext(gold: str, *, seed: int) -> str:
    rng = random.Random(seed)
    obj = json.loads(gold)
    shuffled = _shuffle_json_keys(obj, rng)
    # Non-canonical whitespace / separators.
    return json.dumps(shuffled, indent=3, ensure_ascii=False)


def perturb_fc(gold: str, *, seed: int) -> str:
    rng = random.Random(seed)
    obj = json.loads(gold)
    if isinstance(obj, list):
        calls = []
        for call in obj:
            if not isinstance(call, dict) or len(call) != 1:
                calls.append(call)
                continue
            name, params = next(iter(call.items()))
            if isinstance(params, dict):
                items = list(params.items())
                rng.shuffle(items)
                params = {k: v for k, v in items}
            calls.append({name: params})
        return json.dumps(calls, indent=2, ensure_ascii=False)
    return gold


def perturb_sql(gold: str, *, seed: int) -> str:
    # Whitespace / casing that execution semantics should ignore, plus a
    # harmless column alias so result comparison cannot require name identity.
    text = re.sub(r"\s+", " ", gold.strip())
    text = text.replace(" SELECT ", " select ").replace(" FROM ", " from ")
    text = text.replace(" WHERE ", "\nwhere ")
    if re.search(r"(?i)^select\s+count\s*\(", text) and " as " not in text.lower():
        text = re.sub(
            r"(?i)^(select\s+count\s*\([^)]*\))",
            r"\1 AS cap01_cnt",
            text,
            count=1,
        )
    return f"  {text}  \n"


def perturb_math(gold: str, *, seed: int) -> str:
    return f"  {gold.strip()}  \n"


def perturb_code(gold: str, *, seed: int) -> str:
    # Extra blank line + trailing spaces; semantics unchanged.
    return gold.rstrip() + "  \n\n"


PERTURBERS = {
    "TEXT_TO_SQL": perturb_sql,
    "STRUCTURED_EXTRACTION": perturb_ext,
    "FUNCTION_CALLING": perturb_fc,
    "MATH": perturb_math,
    "CODE": perturb_code,
}


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    by_id = {t["task_id"]: TaskRecord.from_dict(t) for t in corpus["tasks"]}
    humaneval = _load_humaneval(HUMANEVAL)
    rows = []
    for domain, task_ids in SAMPLES.items():
        for task_id in task_ids:
            task = by_id[task_id]
            gold = gold_content(task, humaneval_by_id=humaneval)
            perturber = PERTURBERS[domain]
            perturbed = perturber(gold, seed=hash(task_id) & 0xFFFF)
            assert perturbed != gold or domain == "MATH", (
                f"{task_id}: perturbation did not change surface form"
            )
            # MATH whitespace-only may still equal after strip in rare cases;
            # force a visible variant.
            if perturbed.strip() == gold.strip() and domain == "MATH":
                perturbed = f" {gold} \n"
            verdict = verify_candidate(
                task,
                CandidateRecord(
                    candidate_id=f"pert-{task_id}",
                    task_id=task_id,
                    ordinal=0,
                    content=perturbed,
                    prompt_tokens=0,
                    completion_tokens=0,
                ),
            )
            rows.append(
                {
                    "task_id": task_id,
                    "domain": domain,
                    "pass": bool(verdict.solved),
                    "status": verdict.status,
                    "gold_preview": gold[:160],
                    "perturbed_preview": perturbed[:160],
                }
            )
    by_domain: dict[str, list] = {}
    for row in rows:
        by_domain.setdefault(row["domain"], []).append(row)
    summary = {
        domain: {
            "n": len(items),
            "pass": sum(1 for item in items if item["pass"]),
            "fail": sum(1 for item in items if not item["pass"]),
            "healthy": all(item["pass"] for item in items),
            "failures": [item["task_id"] for item in items if not item["pass"]],
        }
        for domain, items in sorted(by_domain.items())
    }
    report = {"summary": summary, "rows": rows}
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
