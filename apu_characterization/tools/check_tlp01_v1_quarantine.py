#!/usr/bin/env python3
"""G-V1-QUARANTINE: citable TLP-01 artifacts must not cite v1 graph hash as data source."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V1_FULL = "a45e88c2d19349db4988132c18cf5eb00d722ae20389db2b8dea0accdf5c2015"
V1_SHORT = "a45e88c2"
V2_FULL = "29286aaa16b8e85207948db0ac84698466da3a8bdaebc6e80bbfa88f180a24d0"

# Files that may travel outward and must be v2-pinned.
CITABLE_PATHS = [
    REPO / "apu_characterization/out/tlp01/t2/t2_ladder_report.md",
    REPO / "apu_characterization/out/tlp01/t2/t2_verdict_verification.md",
    REPO / "apu_characterization/out/tlp01/t2/edge_taxonomy_migration_report.md",
    REPO / "apu_characterization/out/tlp01/t2/tlp01_closeout_report.md",
    REPO / "apu_characterization/out/tlp01/t2/v2_supersession_table.md",
    REPO / "apu_characterization/out/tlp01/t2/quotable_extracts.json",
    REPO / "apu_characterization/PROMOTION_SUMMARY.md",
    REPO / "apu_characterization/METHODOLOGY_ARC_TLP01.md",
]

# Allowed v1 mentions (history / quarantine documentation).
ALLOWED_CONTEXT = re.compile(
    r"(v1-era|history only|quarantine|retain|supersession|never cite|"
    r"dependence_graphs/|pre-taxonomy|migration)",
    re.I,
)

FORBIDDEN_AS_SOURCE = re.compile(
    r"(t1_index|graph index|frozen input|data source|authoritative|"
    r"quotable|aggregate|dependence_graphs[^_v])",
    re.I,
)


def check_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    if V1_FULL in text or V1_SHORT in text:
        for i, line in enumerate(text.splitlines(), 1):
            if V1_FULL not in line and V1_SHORT not in line:
                continue
            if ALLOWED_CONTEXT.search(line):
                continue
            if FORBIDDEN_AS_SOURCE.search(line):
                errors.append(f"{path}: line {i}: v1 hash cited as source: {line.strip()[:80]}")
    if path.name in {"t2_ladder_report.md", "aggregate.json"}:
        if V2_FULL[:12] not in text and "29286aaa" not in text:
            if "VERIFICATION CLOSED" in text or path.name == "t2_ladder_report.md":
                if "29286aaa" not in text:
                    errors.append(f"{path}: missing v2 graph pin 29286aaa…")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in CITABLE_PATHS:
        errors.extend(check_file(path))
    agg = REPO / "apu_characterization/out/tlp01/t2/aggregate.json"
    if agg.is_file():
        import json

        data = json.loads(agg.read_text(encoding="utf-8"))
        t1 = str(data.get("t1_index_sha256") or "")
        if t1 == V1_FULL:
            errors.append("aggregate.json: t1_index_sha256 is v1 hash")
        if t1 != V2_FULL:
            errors.append(f"aggregate.json: t1_index_sha256 not v2 ({t1[:16]}…)")
    if errors:
        for err in errors:
            print(f"G-V1-QUARANTINE FAIL: {err}", file=sys.stderr)
        return 1
    print("G-V1-QUARANTINE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
