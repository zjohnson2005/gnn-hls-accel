"""Validate CAP-01 task JSONL files and freeze the corpus manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from apu_characterization.cap01.corpus import (
    build_corpus_manifest,
    load_task_jsonl,
    write_corpus_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--function-calling-jsonl", type=Path, required=True)
    parser.add_argument("--text-to-sql-jsonl", type=Path, required=True)
    parser.add_argument("--code-jsonl", type=Path, required=True)
    parser.add_argument("--math-jsonl", type=Path, required=True)
    parser.add_argument("--structured-extraction-jsonl", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    args = parser.parse_args()
    tasks = [
        task
        for path in (
            args.function_calling_jsonl,
            args.text_to_sql_jsonl,
            args.code_jsonl,
            args.math_jsonl,
            args.structured_extraction_jsonl,
        )
        for task in load_task_jsonl(path)
    ]
    manifest = build_corpus_manifest(tasks, corpus_root=args.corpus_root)
    digest = write_corpus_manifest(args.output, manifest)
    print(f"corpus_manifest={args.output}")
    print(f"task_count={manifest['task_count']}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
