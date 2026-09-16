"""Permanent gate: every corpus gold must pass its pinned verifier; garbage must fail.

Known corpus defects are allowlisted with ledger references — they are not silent
skips. New gold failures outside the allowlist fail the gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apu_characterization.cap01.contracts import TaskRecord
from apu_characterization.tools.audit_cap01_verifier_ground_truth import (
    _load_humaneval,
    audit_task,
)

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "apu_characterization/out/cap01/corpus.json"
HUMANEVAL = (
    REPO / "apu_characterization/out/cap01/live_sources/humanevalplus-hf/test.jsonl"
)

# Ledgered corpus defects (gold fails verifier by construction / host timeout).
# Do not expand casually — each entry needs a died-ledger citation.
GOLD_FAIL_ALLOWLIST: dict[str, str] = {
    "MATH-019": "truncated boxed answer in corpus extract (corpus defect)",
    "SQL-041": "gold SQL OperationalError interrupted (sqlite timeout)",
    "EXT-017": "inferred schema requires menu[].sub but gold omits it",
    "EXT-027": "inferred schema requires menu[].price but gold omits it",
    "EXT-030": "inferred schema forbids menu[].sub but gold includes it",
    "EXT-032": "inferred schema forbids menu[].discountprice but gold includes it",
    "EXT-034": "inferred schema forbids menu[].discountprice but gold includes it",
}


@pytest.mark.skipif(not CORPUS.is_file(), reason="licensed corpus not built")
def test_verifier_ground_truth_gold_pass_garbage_fail() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    tasks = [TaskRecord.from_dict(item) for item in corpus["tasks"]]
    assert len(tasks) == 250
    humaneval = _load_humaneval(HUMANEVAL)
    unexpected_gold_fails: list[str] = []
    garbage_accepts: list[str] = []
    allowlisted_seen: set[str] = set()
    for task in tasks:
        row = audit_task(task, humaneval_by_id=humaneval)
        if not row["garbage_fail"]:
            garbage_accepts.append(task.task_id)
        if row["gold_pass"]:
            continue
        if task.task_id in GOLD_FAIL_ALLOWLIST:
            allowlisted_seen.add(task.task_id)
            continue
        unexpected_gold_fails.append(
            f"{task.task_id}:{row['gold_status']}:{row['gold_error'] or row['gold_build_error']}"
        )
    assert not garbage_accepts, f"garbage accepted: {garbage_accepts}"
    assert not unexpected_gold_fails, (
        "unexpected gold failures (not in allowlist):\n"
        + "\n".join(unexpected_gold_fails[:20])
    )
    missing_allow = sorted(set(GOLD_FAIL_ALLOWLIST) - allowlisted_seen)
    assert not missing_allow, (
        "allowlisted tasks unexpectedly passed gold — update allowlist: "
        f"{missing_allow}"
    )


@pytest.mark.skipif(not CORPUS.is_file(), reason="licensed corpus not built")
def test_verifier_canonicalization_invariance_perturbed_gold() -> None:
    """Meaning-preserving gold perturbations must still pass (no raw-string compare)."""
    from apu_characterization.tools.audit_cap01_perturbed_gold import (
        PERTURBERS,
        SAMPLES,
    )
    from apu_characterization.tools.audit_cap01_verifier_ground_truth import (
        gold_content,
    )
    from apu_characterization.cap01.contracts import CandidateRecord
    from apu_characterization.cap01.verifier import verify_candidate

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    by_id = {t["task_id"]: TaskRecord.from_dict(t) for t in corpus["tasks"]}
    humaneval = _load_humaneval(HUMANEVAL)
    failures: list[str] = []
    for domain, task_ids in SAMPLES.items():
        perturber = PERTURBERS[domain]
        for task_id in task_ids:
            task = by_id[task_id]
            gold = gold_content(task, humaneval_by_id=humaneval)
            perturbed = perturber(gold, seed=hash(task_id) & 0xFFFF)
            if perturbed.strip() == gold.strip():
                perturbed = f" {gold} \n"
            verdict = verify_candidate(
                task,
                CandidateRecord(
                    candidate_id=f"pert-gate-{task_id}",
                    task_id=task_id,
                    ordinal=0,
                    content=perturbed,
                    prompt_tokens=0,
                    completion_tokens=0,
                ),
            )
            if not verdict.solved:
                failures.append(f"{task_id}:{verdict.status}")
    assert not failures, f"canonicalization failures: {failures}"
