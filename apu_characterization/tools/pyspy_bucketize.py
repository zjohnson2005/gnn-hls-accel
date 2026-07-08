"""Classify py-spy speedscope samples into attribution buckets."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BUCKET_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("CLIENT_HTTP", re.compile(r"httpx|httpcore|\bssl\b|h11|h2|socket|openai.*transport", re.I)),
    (
        "CLIENT_PARSE",
        re.compile(r"\bjson\b|pydantic|openai|sse|stream|validation", re.I),
    ),
    ("TOKENIZER", re.compile(r"tiktoken", re.I)),
    ("FRAMEWORK", re.compile(r"langgraph|langchain_core|pregel|channel", re.I)),
    ("THREADPOOL", re.compile(r"concurrent\.futures|threading", re.I)),
    ("EVENT_LOOP", re.compile(r"asyncio|selector", re.I)),
    (
        "TOOL_BODY",
        re.compile(
            r"apu_characterization\.tools|tool_search|tool_retrieve|tool_code_exec|tool_calculator",
            re.I,
        ),
    ),
]


def classify_frame(name: str, file_path: str) -> str:
    text = f"{name} {file_path}"
    for bucket, pat in BUCKET_RULES:
        if pat.search(text):
            return bucket
    if "gc" in text.lower():
        return "INTERPRETER_OTHER"
    return "INTERPRETER_OTHER"


def load_speedscope(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bucketize(path: Path) -> dict[str, Any]:
    data = load_speedscope(path)
    shared = data.get("shared", {})
    frames = shared.get("frames", [])
    profiles = data.get("profiles") or [data.get("profile") or {}]

    counts: Counter[str] = Counter()
    total = 0
    for prof in profiles:
        if not prof:
            continue
        stacks = prof.get("samples") or []
        weights = prof.get("weights") or [1] * len(stacks)
        for stack, weight in zip(stacks, weights):
            if not stack:
                continue
            leaf = stack[-1]
            if leaf >= len(frames):
                continue
            fr = frames[leaf]
            bucket = classify_frame(fr.get("name", ""), fr.get("file", ""))
            counts[bucket] += weight
            total += weight

    shares = {k: (100.0 * v / total if total else 0.0) for k, v in sorted(counts.items())}
    return {"path": str(path), "total_samples": total, "bucket_counts": dict(counts), "bucket_pct": shares}


def reconcile_proxy_pct(result: dict[str, Any]) -> float:
    """Leaf samples in native/unclassified + thread-pool frames (v1 reconcile home)."""
    pct = result["bucket_pct"]
    return pct.get("INTERPRETER_OTHER", 0.0) + pct.get("THREADPOOL", 0.0)


def harness_labeled_pct(result: dict[str, Any]) -> float:
    pct = result["bucket_pct"]
    keys = (
        "CLIENT_HTTP",
        "CLIENT_PARSE",
        "FRAMEWORK",
        "TOKENIZER",
        "EVENT_LOOP",
    )
    return sum(pct.get(k, 0.0) for k in keys)


def format_table(result: dict[str, Any]) -> str:
    lines = [
        f"# py-spy bucket table: {result['path']}",
        "",
        f"Total weighted samples: {result['total_samples']}",
        "",
        "| Bucket | Samples | Share % |",
        "|--------|---------|---------|",
    ]
    for bucket, pct in sorted(result["bucket_pct"].items(), key=lambda x: -x[1]):
        lines.append(
            f"| {bucket} | {result['bucket_counts'].get(bucket, 0)} | {pct:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("speedscope", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = bucketize(args.speedscope)
    text = format_table(result)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
