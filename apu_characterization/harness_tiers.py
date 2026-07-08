"""Harness tier definitions (single source of truth for v1 and v2 reports."""

from __future__ import annotations

from .taxonomy import Category

HARNESS_STRICT_CATEGORIES: tuple[Category, ...] = (
    Category.ORCH_SETUP,
    Category.ORCH_DISPATCH,
    Category.TOKENIZATION,
    Category.SERIALIZATION,
)

HARNESS_BROAD_CATEGORIES: tuple[Category, ...] = (
    Category.ORCH_SETUP,
    Category.ORCH_DISPATCH,
    Category.TOKENIZATION,
    Category.SERIALIZATION,
    Category.CLIENT_HTTP,
    Category.CLIENT_PARSE,
    Category.FRAMEWORK,
    Category.THREADPOOL,
    Category.EVENT_LOOP,
    Category.PROMPT_ASSEMBLY,
    Category.CONTEXT_MGMT,
    Category.LOGGING,
)

HARNESS_STRICT_LABEL = "harness strict (ORCH+TOKEN+SER)"
HARNESS_BROAD_LABEL = (
    "harness broad (strict + CLIENT_HTTP + CLIENT_PARSE + FRAMEWORK + "
    "THREADPOOL + EVENT_LOOP + PROMPT + CONTEXT + LOGGING)"
)


def sum_category_cpu_ns(
    per_category: dict[str, dict[str, int]], categories: tuple[Category, ...]
) -> int:
    total = 0
    for cat in categories:
        row = per_category.get(cat.value, {})
        total += int(row.get("cpu_ns", 0))
    return total


def pooled_pct(cpu_ns: int, host_ns: int) -> float:
    if host_ns <= 0:
        return 0.0
    return 100.0 * cpu_ns / host_ns
