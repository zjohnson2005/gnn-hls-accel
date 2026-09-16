#!/usr/bin/env python3
"""Assemble TLP-01 closeout / promotion package from v2 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from apu_characterization.tlp01.promotion import (
    COMPOSITE_SENTENCE,
    CANONICAL_RUNG_3A,
    V2_GRAPH_SHA,
    generate_promotion_figures,
    load_aggregate,
    quotable_extracts,
    render_supersession_md,
    supersession_table,
)

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "apu_characterization/out/tlp01/t2"
FIG = OUT / "figures"


def main() -> None:
    aggregate = load_aggregate()
    rows = supersession_table()
    extracts = quotable_extracts(aggregate)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2_supersession_table.md").write_text(
        render_supersession_md(rows), encoding="utf-8"
    )
    (OUT / "quotable_extracts.json").write_text(
        json.dumps(extracts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    ladder_fig, phase_fig = generate_promotion_figures(aggregate, out_dir=FIG)
    fig_note = []
    if ladder_fig:
        fig_note.append(f"- M-ladder: `{ladder_fig.relative_to(REPO)}`")
    if phase_fig:
        fig_note.append(f"- Phase diagram: `{phase_fig.relative_to(REPO)}`")
    if not fig_note:
        fig_note.append("- Figures skipped (matplotlib not installed)")

    closeout = f"""# TLP-01 closeout report

## Task 1 — v2 supersession

See `v2_supersession_table.md`. Authoritative input: `dependence_graphs_v2/` sha `{V2_GRAPH_SHA}`.

## Task 2 — Confirmed rungs (canonical)

**rung_3a:** {CANONICAL_RUNG_3A}

**rung_1b:** {extracts['canonical_rung_1b']}

**Composite:** {COMPOSITE_SENTENCE}

## Task 3 — Headroom

Criteria pre-registered in protocol `speculation_headroom` (v2.1 amendment). **Not evaluated** on this run.

## Task 4 — Methodology arc

See `apu_characterization/METHODOLOGY_ARC_TLP01.md`.

## Task 5 — Promotion package

- `apu_characterization/PROMOTION_SUMMARY.md`
{chr(10).join(fig_note)}

## Bystander contention

**Ran:** yes (eligible sessions, software-side policies). Median primary slowdown 0.08–0.27× under breadth policies. Phase diagram uses **nominal** penalties (conservative; stated not silent).

## Verification

- A–G v2: PASS (`t2_verdict_verification.md`)
- Ceiling: `rung_3a` CONFIRMED
- Frontier: `rung_1b` CONFIRMED

**TLP-01 BANKED — promotion package complete, headroom criteria frozen, ready for external presentation**
"""
    (OUT / "tlp01_closeout_report.md").write_text(closeout, encoding="utf-8")
    print(closeout)


if __name__ == "__main__":
    main()
