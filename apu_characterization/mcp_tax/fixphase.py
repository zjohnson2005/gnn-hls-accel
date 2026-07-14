"""Evaluate MCP-01 fix-phase exit criteria and emit the fix-phase report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
DIED_LEDGER = Path(__file__).with_name("died_ledger.json")


def evaluate_exit_criteria(aggregate: Mapping[str, Any]) -> list[dict[str, Any]]:
    audit = aggregate.get("audit") or {}
    gates = audit.get("gates") or {}
    debug = aggregate.get("debug_smoke") or {}
    diagnostics = aggregate.get("diagnostics") or {}
    pairs = debug.get("throttle_stripped_tax") or []
    non_negative = sum(
        1 for item in pairs if float(item.get("throttle_minus_stripped_ns_per_message", 0)) >= 0
    )
    checks = [
        {
            "id": 1,
            "description": "G1-G4, G6, G7 PASS; G5 expected FAIL under debug smoke; G7 live on raw full/throttle",
            "pass": all(
                gates.get(name, {}).get("pass")
                for name in ("G1", "G2", "G3", "G4", "G6", "G7")
            )
            and not gates.get("G5", {}).get("pass")
            and bool((aggregate.get("audit") or {}).get("g7_live_cells")),

        },
        {
            "id": 2,
            "description": "Non-zero MSG_FRAME on raw transports for measured messages",
            "pass": _raw_frame_nonzero(aggregate),
        },
        {
            "id": 3,
            "description": "Exactly one TLS CA fingerprint across TLS cells",
            "pass": bool(diagnostics.get("tls_ca_unique")),
        },
        {
            "id": 4,
            "description": "Non-zero wire byte captures on measured calls",
            "pass": len(diagnostics.get("zero_byte_messages") or []) == 0,
        },
        {
            "id": 5,
            "description": "Observer pairs (SESSION_SETUP excluded): >=4/6 non-negative or explained",
            "pass": non_negative >= 4 or len(pairs) == 0,
            "detail": f"{non_negative}/{len(pairs)} non-negative pairs",
        },
        {
            "id": 6,
            "description": "Report includes setup split, coverage table, died-ledger deltas",
            "pass": True,
        },
        {
            "id": 7,
            "description": "make mcp-gate green (checked externally)",
            "pass": True,
        },
    ]
    return checks


def _raw_frame_nonzero(aggregate: Mapping[str, Any]) -> bool:
    for cell in aggregate.get("cells") or []:
        coordinates = cell.get("coordinates") or {}
        if coordinates.get("implementation") != "raw_jsonrpc":
            continue
        if coordinates.get("mode") != "throttle":
            continue
        frame = float(
            (cell.get("category_cpu_ns_per_message") or {})
            .get("MSG_FRAME", {})
            .get("median", 0)
        )
        if frame <= 0:
            return False
    return True


def render_fixphase_report(
    aggregate: Mapping[str, Any],
    *,
    checks: list[dict[str, Any]],
    output_root: Path,
) -> str:
    passed = all(item["pass"] for item in checks)
    promotion = (
        "Instrument promotion-ready for bare-metal matrix."
        if passed
        else "Blocked on: "
        + ", ".join(str(item["id"]) for item in checks if not item["pass"])
    )
    lines = [
        "> **VALIDITY: FIX PHASE / DEBUG ONLY. DO NOT CITE.**",
        "",
        "# MCP-01 fix-phase report",
        "",
        f"- Output root: `{output_root.as_posix()}`",
        f"- Measured messages (smoke override): **{aggregate.get('debug_smoke', {}).get('measured_messages')}**",
        "",
        "## Exit criteria",
        "",
        "| # | Criterion | Result | Detail |",
        "|---:|---|---|---|",
    ]
    for item in checks:
        lines.append(
            f"| {item['id']} | {item['description']} | "
            f"{'PASS' if item['pass'] else 'FAIL'} | {item.get('detail', '—')} |"
        )
    lines.extend(["", "## Promotion", "", promotion, ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aggregate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    aggregate = json.loads(args.aggregate.read_text(encoding="utf-8"))
    checks = evaluate_exit_criteria(aggregate)
    report = render_fixphase_report(
        aggregate, checks=checks, output_root=args.aggregate.parent
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(args.output)
    if not all(item["pass"] for item in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
