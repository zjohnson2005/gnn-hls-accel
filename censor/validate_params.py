"""Schema check for censor/study_params.yaml.

Enforces the study guardrail that no number exists without provenance:

* every parameter node carries a non-empty ``source`` string
* every parameter node carries ``confidence`` in
  {measured, published, estimated, guess}
* no numeric leaf hides outside a sourced parameter node

Exit 0 only when the file is clean. Every violation is printed with its full
key path so the offending line can be found directly.

Usage::

    py -3 censor/validate_params.py [path/to/study_params.yaml]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

VALID_CONFIDENCE = {"measured", "published", "estimated", "guess"}

# A dict is a parameter node if it declares any of these.
VALUE_KEYS = {"value", "values", "lo", "hi", "avg", "p50", "p90", "p99"}

# Subtrees that are prose or decision records rather than sourced parameters.
# Exemptions are printed on every run so they cannot rot silently.
EXEMPT_ROOTS = {
    "meta": "provenance//scope prose, not parameters",
    "decisions": "resolved modeling choices; carry rationale+consequence, not source+confidence",
}

# Scalar keys that are legitimately bare inside a parameter node.
METADATA_KEYS = {
    "source",
    "confidence",
    "unit",
    "note",
    "notes",
    "description",
    "rationale",
    "consequence",
    "decided",
    "why_it_matters",
    "token_weighted",
    "CAVEAT",
    "MUST_MEASURE",
    "MUST_DECIDE",
    "SWEEP_AS_FIRST_CLASS_PARAMETER",
    "EXTRACTION_STATUS",
    "extraction_note",
    "EXTERNAL_VALIDITY_FLAG",
    "DATA_QUALITY_WARNING",
    "trajectory_definition_warning",
    "asymmetry_note",
    "label",
    "model",
    "swept",
    "caveat",
    "PRIMARY",
    "PRIORITY",
    "superseded_note",
    "NEVER_COLLAPSE",
    "downstream_requirement",
    "hard_constraint",
    "fallback_if_fit_is_unstable",
    "method",
    "distribution_source",
    "tail_qualification",
}


class Violations:
    def __init__(self) -> None:
        self.missing_source: list[str] = []
        self.bad_confidence: list[tuple[str, Any]] = []
        self.unsourced_numeric: list[tuple[str, Any]] = []

    @property
    def total(self) -> int:
        return (
            len(self.missing_source)
            + len(self.bad_confidence)
            + len(self.unsourced_numeric)
        )


def _is_param_node(node: dict[str, Any]) -> bool:
    """A node that asserts a quantity, and therefore owes provenance.

    ``confidence`` counts as a trigger too: a node claiming a confidence level
    while omitting ``source`` is exactly the shape this check exists to catch.
    """
    return bool(VALUE_KEYS & node.keys()) or "source" in node or "confidence" in node


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _has_number(x: Any) -> bool:
    if _is_number(x):
        return True
    if isinstance(x, list):
        return any(_has_number(i) for i in x)
    return False


def _walk(node: Any, path: str, covered: bool, v: Violations) -> None:
    """Recurse, tracking whether an ancestor parameter node supplies a source."""
    if isinstance(node, dict):
        here_covered = covered
        if _is_param_node(node):
            src = node.get("source")
            if not isinstance(src, str) or not src.strip():
                v.missing_source.append(path)
            else:
                here_covered = True

            conf = node.get("confidence")
            if conf not in VALID_CONFIDENCE:
                v.bad_confidence.append((path, conf))

        for key, child in node.items():
            child_path = f"{path}.{key}" if path else key
            if key in METADATA_KEYS and not isinstance(child, (dict, list)):
                continue
            _walk(child, child_path, here_covered, v)

    elif isinstance(node, list):
        if _has_number(node) and not covered:
            v.unsourced_numeric.append((path, node))

    else:
        if _is_number(node) and not covered:
            v.unsourced_numeric.append((path, node))


def validate(path: Path) -> int:
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    if not isinstance(doc, dict):
        print(f"FAIL: {path} did not parse to a mapping (got {type(doc).__name__})")
        return 1

    print(f"Parsed {path} -> {len(doc)} top-level sections")
    print()
    print("Exempt subtrees (not parameter-bearing):")
    for root, why in sorted(EXEMPT_ROOTS.items()):
        present = "present" if root in doc else "ABSENT"
        print(f"  - {root:<12} [{present}] {why}")
    print()

    v = Violations()
    for key, child in doc.items():
        if key in EXEMPT_ROOTS:
            continue
        _walk(child, key, covered=False, v=v)

    if v.missing_source:
        print(f"MISSING_SOURCE ({len(v.missing_source)}) "
              "- parameter node asserts a quantity with no source:")
        for p in v.missing_source:
            print(f"  - {p}")
        print()

    if v.bad_confidence:
        print(f"MISSING_OR_INVALID_CONFIDENCE ({len(v.bad_confidence)}) "
              f"- must be one of {sorted(VALID_CONFIDENCE)}:")
        for p, got in v.bad_confidence:
            print(f"  - {p}  (got: {got!r})")
        print()

    if v.unsourced_numeric:
        print(f"UNSOURCED_NUMERIC_LEAF ({len(v.unsourced_numeric)}) "
              "- a number with no sourced ancestor:")
        for p, got in v.unsourced_numeric:
            print(f"  - {p} = {got!r}")
        print()

    if v.total == 0:
        print("PASS: every parameter node carries a source and a valid confidence;")
        print("      no unsourced numeric leaves found.")
        return 0

    print(f"FAIL: {v.total} violation(s).")
    return 1


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("study_params.yaml")
    if not target.exists():
        print(f"FAIL: {target} does not exist")
        return 2
    return validate(target)


if __name__ == "__main__":
    raise SystemExit(main())
