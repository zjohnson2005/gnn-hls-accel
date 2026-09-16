"""EXT near-miss audit: sample triage candidates vs exact-match gold criterion."""

from __future__ import annotations

import json
from pathlib import Path

from apu_characterization.cap01.contracts import CandidateRecord, TaskRecord
from apu_characterization.cap01.domain_verifiers import verify_structured_extraction

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "out/cap01/corpus.json"
STAGING = REPO / "out/cap01/pools_triage/staging"
OUT = REPO / "out/cap01/ext_near_miss_audit.json"

# Five gold-PASS tasks (exclude schema-defective EXT-017/027/030/032/034).
SAMPLE_TASKS = ["EXT-001", "EXT-002", "EXT-003", "EXT-004", "EXT-005"]


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    by_id = {t["task_id"]: TaskRecord.from_dict(t) for t in corpus["tasks"]}
    rows = []
    for task_id in SAMPLE_TASKS:
        task = by_id[task_id]
        path = STAGING / f"triage-{task_id}.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()[:4]
        samples = []
        for index, line in enumerate(lines):
            payload = json.loads(line)
            content = str(payload.get("content") or "")
            verdict = verify_structured_extraction(content, task.verifier)
            # Structural near-miss heuristics.
            looks_json = content.strip().startswith("{")
            has_menu = '"menu"' in content or "'menu'" in content
            samples.append(
                {
                    "ordinal": index,
                    "solved": verdict.solved,
                    "status": verdict.status,
                    "error": (verdict.error or "")[:240],
                    "looks_json_object": looks_json,
                    "mentions_menu": has_menu,
                    "content_preview": content[:400],
                }
            )
        rows.append(
            {
                "task_id": task_id,
                "gold_exact_match_ok": True,
                "candidates_scored": len(samples),
                "any_exact_pass": any(s["solved"] for s in samples),
                "jsonish_count": sum(1 for s in samples if s["looks_json_object"]),
                "menu_mention_count": sum(1 for s in samples if s["mentions_menu"]),
                "samples": samples,
            }
        )
    report = {
        "criterion": "exact normalized gt_parse match after schema validate",
        "sample": rows,
        "options": {
            "a_keep_exact_match": (
                "Disclose D5 as exact-structured-reproduction; keep pin."
            ),
            "b_field_level_f1": (
                "Ledgered verifier amendment to per-field F1 + re-lock before pools."
            ),
        },
        "recommendation": "a_keep_exact_match",
        "recommendation_rationale": (
            "Golds pass on 45/50 (5 are schema-inference corpus defects). "
            "Triage all-DEAD with a working verifier indicates the pass criterion "
            "is brutally strict for gpt-4o-mini, not a wiring bug. Relaxing after "
            "seeing failures is a scoring change that must be explicit; prefer "
            "disclosing narrow exact-match capability unless Zach chooses (b)."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "sample"}, indent=2))
    for row in rows:
        print(
            row["task_id"],
            "exact_any",
            row["any_exact_pass"],
            "jsonish",
            row["jsonish_count"],
            "menu",
            row["menu_mention_count"],
        )
    print("wrote", OUT)


if __name__ == "__main__":
    main()
