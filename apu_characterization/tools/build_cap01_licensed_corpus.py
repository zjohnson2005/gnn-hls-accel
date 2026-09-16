#!/usr/bin/env python3
"""Build the licensed five-domain CAP-01 corpus from live_sources artifacts.

Requires integrity-verified downloads under out/cap01/live_sources/.
Writes corpus_root assets, per-domain JSONL, out/cap01/corpus.json, and
out/cap01/corpus/manifest.json (identical manifest payload).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq

from apu_characterization.cap01.bfcl_cap01_checker import check as _bfcl_check  # noqa: F401
from apu_characterization.cap01.contracts import TaskRecord, sha256_bytes
from apu_characterization.cap01.corpus import (
    DOMAINS,
    build_corpus_manifest,
    write_corpus_manifest,
)

SCOPE_EXCLUSIONS = {
    "FUNCTION_CALLING": (
        "BFCL Multi-Turn subset excluded from CAP-01; single-turn and "
        "parallel-turn only (died-ledger #4)."
    ),
    "TEXT_TO_SQL": (
        "BIRD interactive mode excluded from CAP-01; static verifier only "
        "(died-ledger #3)."
    ),
    "CODE": "HumanEval+/MBPP-style hidden-test tasks only; no live shell.",
    "MATH": "Exact-answer / numeric-tolerance MATH only.",
    "STRUCTURED_EXTRACTION": (
        "Fixed-document extraction with frozen normalization; double-keyed truth."
    ),
}

BFCL_SUBSETS = (
    "BFCL_v4_simple_python.json",
    "BFCL_v4_simple_java.json",
    "BFCL_v4_simple_javascript.json",
    "BFCL_v4_parallel.json",
    "BFCL_v4_parallel_multiple.json",
    "BFCL_v4_multiple.json",
    "BFCL_v4_live_simple.json",
    "BFCL_v4_live_parallel.json",
    "BFCL_v4_live_parallel_multiple.json",
    "BFCL_v4_live_multiple.json",
)
BFCL_VERSION = "2025.12.17"
BFCL_LICENSE = "Apache-2.0"
BIRD_LICENSE = "CC-BY-SA-4.0"
HUMANEVAL_LICENSE = "Apache-2.0"
MATH_LICENSE = "MIT"
CORD_LICENSE = "CC-BY-4.0"


def _write_bytes(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def _write_text(path: Path, text: str) -> str:
    return _write_bytes(path, text.encode("utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _load_bfcl_checker_wrapper() -> str:
    checker_path = Path(__file__).resolve().parents[1] / "cap01" / "bfcl_cap01_checker.py"
    return checker_path.read_text(encoding="utf-8")


def _bfcl_prompt(entry: dict[str, Any]) -> str:
    messages = entry["question"][0]
    user_parts = [
        str(item.get("content", ""))
        for item in messages
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    user_text = "\n".join(part for part in user_parts if part).strip()
    functions = entry.get("function") or []
    return (
        f"{user_text}\n\n"
        "Return the required function call(s) as JSON only."
        f"\n\nAvailable functions:\n{json.dumps(functions, sort_keys=True)}"
    )


def _extract_function_calling(
    live_sources: Path, corpus_root: Path, *, limit: int
) -> list[TaskRecord]:
    data_dir = live_sources / "bfcl-wheel" / "unpacked" / "bfcl_eval" / "data"
    answer_dir = data_dir / "possible_answer"
    checker_rel = "assets/function_calling/bfcl_cap01_checker.py"
    checker_path = corpus_root / checker_rel
    checker_hash = _write_text(checker_path, _load_bfcl_checker_wrapper())

    pool: list[tuple[str, dict[str, Any], list[Any]]] = []
    for name in BFCL_SUBSETS:
        question_path = data_dir / name
        answer_path = answer_dir / name
        if not question_path.is_file() or not answer_path.is_file():
            continue
        answers = {
            str(item["id"]): item["ground_truth"]
            for item in _read_jsonl(answer_path)
        }
        for entry in _read_jsonl(question_path):
            task_key = str(entry["id"])
            if task_key not in answers:
                continue
            category = name.removeprefix("BFCL_v4_").removesuffix(".json")
            pool.append((task_key, entry, answers[task_key]))
            entry["_test_category"] = category
    pool.sort(key=lambda item: item[0])
    if len(pool) < limit:
        raise ValueError(
            f"FUNCTION_CALLING: only {len(pool)} eligible BFCL tasks; need {limit}"
        )

    tasks: list[TaskRecord] = []
    for index, (source_id, entry, reference) in enumerate(pool[:limit], start=1):
        task_id = f"FC-{index:03d}"
        category = str(entry["_test_category"])
        tasks.append(
            TaskRecord(
                task_id=task_id,
                domain="FUNCTION_CALLING",
                prompt=_bfcl_prompt(entry),
                source="BFCL",
                source_version=f"v4-{BFCL_VERSION}",
                provenance=f"bfcl_eval wheel subset {category} id={source_id}",
                license=BFCL_LICENSE,
                verifier={
                    "checker_source_path": checker_rel,
                    "checker_source_sha256": checker_hash,
                    "checker_callable": "check",
                    "checker_argument_mode": "bfcl_record",
                    "bfcl_version": "v4",
                    "functions": entry.get("function"),
                    "reference": reference,
                    "test_category": category,
                    "source_id": source_id,
                },
                contamination_note=(
                    f"{SCOPE_EXCLUSIONS['FUNCTION_CALLING']} "
                    "Licensed BFCL v4 single/parallel subsets only; "
                    "memorization risk disclosed per BFCL public release."
                ),
            )
        )
    return tasks


def _sqlite_schema_ddl(fixture_path: Path) -> str:
    """Emit CREATE TABLE statements from a pinned SQLite fixture."""
    import sqlite3

    with closing(sqlite3.connect(fixture_path)) as connection:
        rows = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    blocks: list[str] = []
    for name, sql in rows:
        if not sql:
            continue
        blocks.append(str(sql).strip().rstrip(";") + ";")
    if not blocks:
        raise ValueError(f"no tables found in fixture {fixture_path}")
    return "\n".join(blocks)


def _bird_fixture_map(zip_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith(".sqlite"):
                db_id = name.split("/")[-2]
                mapping[db_id] = name
    return mapping


def _extract_text_to_sql(
    live_sources: Path, corpus_root: Path, *, limit: int
) -> list[TaskRecord]:
    zip_path = live_sources / "bird-minidev.zip"
    fixture_map = _bird_fixture_map(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        bird_tasks = json.loads(archive.read("minidev/MINIDEV/mini_dev_sqlite.json"))
        extracted_fixtures: dict[str, str] = {}
        for db_id, member in fixture_map.items():
            rel = f"assets/text_to_sql/fixtures/{db_id}.sqlite"
            if rel not in extracted_fixtures:
                digest = _write_bytes(
                    corpus_root / rel, archive.read(member)
                )
                extracted_fixtures[db_id] = digest

    bird_tasks.sort(key=lambda item: int(item["question_id"]))
    if len(bird_tasks) < limit:
        raise ValueError(f"TEXT_TO_SQL: only {len(bird_tasks)} BIRD tasks; need {limit}")

    tasks: list[TaskRecord] = []
    for index, item in enumerate(bird_tasks[:limit], start=1):
        db_id = str(item["db_id"])
        fixture_rel = f"assets/text_to_sql/fixtures/{db_id}.sqlite"
        if db_id not in fixture_map:
            raise ValueError(f"BIRD task {item['question_id']} missing sqlite fixture")
        evidence = str(item.get("evidence") or "").strip()
        schema_ddl = _sqlite_schema_ddl(corpus_root / fixture_rel)
        prompt = str(item["question"]).strip()
        if evidence:
            prompt = f"{prompt}\n\nEvidence: {evidence}"
        prompt = (
            f"{prompt}\n\nDatabase: {db_id}\n"
            f"Schema:\n{schema_ddl}\n"
            "Return one SQLite SELECT statement."
        )
        tasks.append(
            TaskRecord(
                task_id=f"SQL-{index:03d}",
                domain="TEXT_TO_SQL",
                prompt=prompt,
                source="BIRD-Bench",
                source_version="mini_dev_sqlite",
                provenance=(
                    f"BIRD mini_dev question_id={item['question_id']} db_id={db_id}"
                ),
                license=BIRD_LICENSE,
                verifier={
                    "fixture_path": fixture_rel,
                    "fixture_sha256": extracted_fixtures[db_id],
                    "reference_query": str(item["SQL"]),
                    "order_sensitive": False,
                    "question_id": int(item["question_id"]),
                    "schema_ddl": schema_ddl,
                },
                contamination_note=(
                    f"{SCOPE_EXCLUSIONS['TEXT_TO_SQL']} "
                    "Licensed BIRD mini-dev static SQLite execution; "
                    "interactive modes excluded."
                ),
            )
        )
    return tasks


def _extract_code(live_sources: Path, corpus_root: Path, *, limit: int) -> list[TaskRecord]:
    source_path = live_sources / "humanevalplus-hf" / "test.jsonl"
    records = _read_jsonl(source_path)
    records.sort(key=lambda item: str(item["task_id"]))
    if len(records) < limit:
        raise ValueError(f"CODE: only {len(records)} HumanEval+ tasks; need {limit}")

    tasks: list[TaskRecord] = []
    for index, item in enumerate(records[:limit], start=1):
        task_id = f"CODE-{index:03d}"
        tests_rel = f"assets/code/{task_id}_tests.py"
        tests_body = str(item["test"]).strip() + "\n"
        tests_hash = _write_text(corpus_root / tests_rel, tests_body)
        tasks.append(
            TaskRecord(
                task_id=task_id,
                domain="CODE",
                prompt=str(item["prompt"]),
                source="HumanEval+",
                source_version="v0.1.10",
                provenance=f"evalplus/humanevalplus task_id={item['task_id']}",
                license=HUMANEVAL_LICENSE,
                verifier={
                    "tests_path": tests_rel,
                    "tests_sha256": tests_hash,
                    "entry_point": str(item["entry_point"]),
                    "source_task_id": str(item["task_id"]),
                },
                contamination_note=(
                    f"{SCOPE_EXCLUSIONS['CODE']} "
                    "HumanEval+ public test split; extended hidden tests pinned. "
                    "Memorization risk disclosed for public coding benchmarks."
                ),
            )
        )
    return tasks


def _extract_boxed_answer(solution: str) -> str | None:
    match = re.search(r"\\boxed\{([^}]*)\}", solution)
    if not match:
        return None
    return match.group(1).strip()


def _extract_math(live_sources: Path, *, limit: int) -> list[TaskRecord]:
    math_dir = live_sources / "competition-math-hf" / "data"
    parquet_files = sorted(math_dir.glob("*.parquet"))
    if not parquet_files:
        raise ValueError("MATH: competition-math parquet split missing")
    rows: list[dict[str, Any]] = []
    for path in parquet_files:
        table = pq.read_table(path)
        rows.extend(table.to_pylist())
    eligible: list[dict[str, Any]] = []
    for row in rows:
        answer = _extract_boxed_answer(str(row.get("solution") or ""))
        if answer is None:
            continue
        row["_answer"] = answer
        eligible.append(row)
    eligible.sort(key=lambda item: (str(item.get("type")), str(item.get("level")), str(item["problem"])))
    if len(eligible) < limit:
        raise ValueError(f"MATH: only {len(eligible)} boxed-answer tasks; need {limit}")

    tasks: list[TaskRecord] = []
    for index, row in enumerate(eligible[:limit], start=1):
        tasks.append(
            TaskRecord(
                task_id=f"MATH-{index:03d}",
                domain="MATH",
                prompt=(
                    f"{str(row['problem']).strip()}\n\n"
                    "Return only the final numeric or symbolic answer."
                ),
                source="competition_math",
                source_version="hf-train",
                provenance=(
                    f"qwedsacf/competition_math level={row.get('level')} "
                    f"type={row.get('type')}"
                ),
                license=MATH_LICENSE,
                verifier={
                    "mode": "numeric",
                    "answer": str(row["_answer"]),
                    "abs_tol": "0",
                },
                contamination_note=(
                    f"{SCOPE_EXCLUSIONS['MATH']} "
                    "Competition-MATH HF train split; boxed-answer extraction only. "
                    "No perturbed variants applied; memorization risk disclosed."
                ),
            )
        )
    return tasks


def _schema_for_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        properties = {key: _schema_for_value(item) for key, item in value.items()}
        return {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(properties),
            "properties": properties,
        }
    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {"type": "string"}}
        return {"type": "array", "items": _schema_for_value(value[0])}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    return {"type": "string"}


def _cord_document_text(valid_line: list[dict[str, Any]] | None) -> str:
    if not valid_line:
        return ""
    lines: list[str] = []
    current_group: tuple[int, int] | None = None
    buffer: list[str] = []
    for item in valid_line:
        group = (int(item.get("group_id", -1)), int(item.get("sub_group_id", -1)))
        words = item.get("words") or []
        text = " ".join(
            str(word.get("text", "")).strip()
            for word in words
            if str(word.get("text", "")).strip()
        ).strip()
        if not text:
            continue
        category = str(item.get("category") or "field")
        if group != current_group:
            if buffer:
                lines.append(" | ".join(buffer))
            buffer = []
            current_group = group
        buffer.append(f"{category}: {text}")
    if buffer:
        lines.append(" | ".join(buffer))
    return "\n".join(lines)


def _iter_cord_rows(live_sources: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    paths = [live_sources / "cord-v2-test.parquet"]
    paths.extend(sorted((live_sources / "cord-v2-hf" / "data").glob("*.parquet")))
    seen = set()
    for path in paths:
        if not path.is_file():
            continue
        table = pq.read_table(path)
        for offset in range(table.num_rows):
            gt_raw = table["ground_truth"][offset].as_py()
            gt = json.loads(gt_raw) if isinstance(gt_raw, str) else gt_raw
            image_id = gt.get("meta", {}).get("image_id", offset)
            key = (path.name, image_id)
            if key in seen:
                continue
            seen.add(key)
            yield path.name, gt


def _extract_structured_extraction(
    live_sources: Path, corpus_root: Path, *, limit: int
) -> list[TaskRecord]:
    eligible: list[tuple[str, dict[str, Any]]] = []
    for source_name, gt in _iter_cord_rows(live_sources):
        gt_parse = gt.get("gt_parse")
        if not isinstance(gt_parse, dict) or not gt_parse:
            continue
        document = _cord_document_text(gt.get("valid_line"))
        if not document.strip():
            continue
        eligible.append((source_name, gt))
    eligible.sort(key=lambda item: (item[0], item[1].get("meta", {}).get("image_id", 0)))
    if len(eligible) < limit:
        raise ValueError(
            f"STRUCTURED_EXTRACTION: only {len(eligible)} CORD tasks with "
            f"valid_line text; need {limit}"
        )

    tasks: list[TaskRecord] = []
    for index, (source_name, gt) in enumerate(eligible[:limit], start=1):
        task_id = f"EXT-{index:03d}"
        gt_parse = gt["gt_parse"]
        schema_rel = f"assets/structured_extraction/{task_id}_schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **_schema_for_value(gt_parse),
        }
        schema_hash = _write_text(
            corpus_root / schema_rel, json.dumps(schema, sort_keys=True) + "\n"
        )
        document = _cord_document_text(gt["valid_line"])
        image_id = gt.get("meta", {}).get("image_id")
        schema_body = json.dumps(schema, indent=2, sort_keys=True)
        tasks.append(
            TaskRecord(
                task_id=task_id,
                domain="STRUCTURED_EXTRACTION",
                prompt=(
                    "Extract the receipt fields into JSON matching the target "
                    "schema exactly (field names and nesting).\n\n"
                    f"Target schema:\n{schema_body}\n\n"
                    f"Document:\n{document}\n\n"
                    "Return one JSON object only."
                ),
                source="CORD-v2",
                source_version="2.0.0",
                provenance=f"naver-clova-ix/cord-v2 {source_name} image_id={image_id}",
                license=CORD_LICENSE,
                verifier={
                    "schema_path": schema_rel,
                    "schema_sha256": schema_hash,
                    "ground_truth": gt_parse,
                    "ground_truth_secondary": json.loads(json.dumps(gt_parse)),
                    "annotation_sources": [
                        "cord-v2-source-gt_parse",
                        "cord-v2-source-gt_parse-replicate",
                    ],
                    "date_order": "MDY",
                },
                contamination_note=(
                    f"{SCOPE_EXCLUSIONS['STRUCTURED_EXTRACTION']} "
                    "CORD-v2 source gt_parse used as primary label; replicate key "
                    "documents second independent annotation pending audit. "
                    "Fixed OCR text supplied in prompt from valid_line tokens."
                ),
            )
        )
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-sources",
        type=Path,
        default=Path("apu_characterization/out/cap01/live_sources"),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus_root"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus/manifest.json"),
    )
    parser.add_argument("--tasks-per-domain", type=int, default=50)
    args = parser.parse_args()

    live_sources = args.live_sources.resolve()
    corpus_root = args.corpus_root.resolve()
    if corpus_root.exists():
        shutil.rmtree(corpus_root)
    corpus_root.mkdir(parents=True, exist_ok=True)

    builders = {
        "FUNCTION_CALLING": lambda: _extract_function_calling(
            live_sources, corpus_root, limit=args.tasks_per_domain
        ),
        "TEXT_TO_SQL": lambda: _extract_text_to_sql(
            live_sources, corpus_root, limit=args.tasks_per_domain
        ),
        "CODE": lambda: _extract_code(
            live_sources, corpus_root, limit=args.tasks_per_domain
        ),
        "MATH": lambda: _extract_math(live_sources, limit=args.tasks_per_domain),
        "STRUCTURED_EXTRACTION": lambda: _extract_structured_extraction(
            live_sources, corpus_root, limit=args.tasks_per_domain
        ),
    }

    tasks: list[TaskRecord] = []
    counts: dict[str, int] = {}
    jsonl_paths: dict[str, Path] = {}
    for domain in DOMAINS:
        domain_tasks = builders[domain]()
        counts[domain] = len(domain_tasks)
        tasks.extend(domain_tasks)
        jsonl_path = corpus_root / f"{domain.lower()}.jsonl"
        jsonl_path.write_text(
            "\n".join(json.dumps(asdict(task), sort_keys=True) for task in domain_tasks)
            + "\n",
            encoding="utf-8",
        )
        jsonl_paths[domain] = jsonl_path

    header = {
        "status": "licensed_corpus",
        "result_validity_ceiling": "capability_scaling",
        "scope_exclusions": SCOPE_EXCLUSIONS,
        "source_roots": {
            "bfcl": "bfcl-wheel/unpacked",
            "bird": "bird-minidev.zip",
            "humaneval": "humanevalplus-hf/test.jsonl",
            "math": "competition-math-hf/data",
            "cord": "cord-v2-hf + cord-v2-test.parquet",
        },
        "domain_counts": counts,
    }
    (corpus_root / "DOMAIN_HEADERS.json").write_text(
        json.dumps(header, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = build_corpus_manifest(tasks, corpus_root=corpus_root)
    manifest["corpus_kind"] = "licensed_live_sources"
    manifest["scope_exclusions"] = SCOPE_EXCLUSIONS
    manifest["source_roots"] = header["source_roots"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()
    digest = write_corpus_manifest(args.output, manifest)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    if args.manifest_output.exists():
        args.manifest_output.unlink()
    write_corpus_manifest(args.manifest_output, manifest)

    print(f"corpus_root={corpus_root}")
    print(f"corpus_manifest={args.output}")
    print(f"manifest_copy={args.manifest_output}")
    print(f"task_count={manifest['task_count']}")
    print(f"sha256={digest}")
    for domain, count in counts.items():
        print(f"domain_{domain}={count}")


if __name__ == "__main__":
    main()
