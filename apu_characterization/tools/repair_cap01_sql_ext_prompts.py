#!/usr/bin/env python3
"""Repair SQL/EXT task prompts only — wiring completion, not re-selection.

Same task_ids / question_ids / image_ids. Adds schema DDL (SQL) and target
JSON schema body (EXT) into task.prompt so generation sees what solving
requires. Other domains untouched. Died-ledger #12.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from apu_characterization.cap01.contracts import TaskRecord
from apu_characterization.cap01.corpus import (
    _resolve_corpus_asset,
    build_corpus_manifest,
    write_corpus_manifest,
)
from apu_characterization.tools.build_cap01_licensed_corpus import _sqlite_schema_ddl


def _repair_sql_prompt(task: dict[str, Any], corpus_root: Path) -> dict[str, Any]:
    verifier = dict(task["verifier"])
    fixture = _resolve_corpus_asset(corpus_root, str(verifier["fixture_path"]))
    schema_ddl = _sqlite_schema_ddl(fixture)
    verifier["schema_ddl"] = schema_ddl
    prompt = str(task["prompt"])
    if "Schema:\n" in prompt and "CREATE TABLE" in prompt.upper():
        task = dict(task)
        task["verifier"] = verifier
        return task
    if "\nReturn one SQLite SELECT statement." in prompt:
        prompt = prompt.replace(
            "\nReturn one SQLite SELECT statement.",
            f"\nSchema:\n{schema_ddl}\nReturn one SQLite SELECT statement.",
        )
    else:
        prompt = f"{prompt.rstrip()}\n\nSchema:\n{schema_ddl}\n"
    task = dict(task)
    task["prompt"] = prompt
    task["verifier"] = verifier
    return task


def _repair_ext_prompt(task: dict[str, Any], corpus_root: Path) -> dict[str, Any]:
    verifier = task["verifier"]
    schema_path = _resolve_corpus_asset(corpus_root, str(verifier["schema_path"]))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_body = json.dumps(schema, indent=2, sort_keys=True)
    prompt = str(task["prompt"])
    if "Target schema:" in prompt and '"properties"' in prompt:
        return task
    match = re.search(
        r"Document:\n(.*)\n\nReturn one JSON object only\.\s*$", prompt, re.S
    )
    if match:
        document = match.group(1).strip()
    else:
        document = prompt
    prompt = (
        "Extract the receipt fields into JSON matching the target "
        "schema exactly (field names and nesting).\n\n"
        f"Target schema:\n{schema_body}\n\n"
        f"Document:\n{document}\n\n"
        "Return one JSON object only."
    )
    task = dict(task)
    task["prompt"] = prompt
    return task


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus/manifest.json"),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus_root"),
    )
    args = parser.parse_args()

    payload = json.loads(args.corpus.read_text(encoding="utf-8"))
    repaired: list[dict[str, Any]] = []
    sql_n = ext_n = 0
    for item in payload["tasks"]:
        domain = item["domain"]
        if domain == "TEXT_TO_SQL":
            item = _repair_sql_prompt(item, args.corpus_root)
            sql_n += 1
        elif domain == "STRUCTURED_EXTRACTION":
            item = _repair_ext_prompt(item, args.corpus_root)
            ext_n += 1
        repaired.append(item)

    records = [TaskRecord.from_dict(item) for item in repaired]
    header_keys = (
        "corpus_kind",
        "scope_exclusions",
        "source_roots",
        "result_validity_ceiling",
        "status",
    )
    prior = {k: payload[k] for k in header_keys if k in payload}
    manifest = build_corpus_manifest(records, corpus_root=args.corpus_root)
    manifest.update(prior)
    if args.corpus.exists():
        args.corpus.unlink()
    digest = write_corpus_manifest(args.corpus, manifest)
    if args.manifest.exists():
        args.manifest.unlink()
    write_corpus_manifest(args.manifest, manifest)

    sample_sql = next(t for t in manifest["tasks"] if t["task_id"] == "SQL-001")
    sample_ext = next(t for t in manifest["tasks"] if t["task_id"] == "EXT-001")
    assert "CREATE TABLE" in sample_sql["prompt"].upper()
    assert "Target schema:" in sample_ext["prompt"]
    assert '"properties"' in sample_ext["prompt"]
    print(f"repaired_sql={sql_n}")
    print(f"repaired_ext={ext_n}")
    print(f"corpus_sha256={digest}")
    print("PROMPT WIRING COMPLETE")


if __name__ == "__main__":
    main()
