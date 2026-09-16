"""T1: dependence-graph construction on the frozen T0 trace store.

Does not modify traces. Does not run T2 (M-models / phase diagram / claims).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from apu_characterization.tlp01.labels import find_rung_labels
from apu_characterization.tlp01.t1_graphs import (
    DEFAULT_MANIFEST,
    DEFAULT_OUT_V2,
    run_t1,
)


def write_t1_report(index: dict, path: Path) -> None:
    gates = index["gates"]
    status = "T1 COMPLETE" if index["t1_pass"] else "T1 BLOCKED"
    lines = [
        "# TLP-01 T1 dependence-graph report",
        "",
        f"**Status:** {status}",
        "",
        "Graph construction + gate inventory only. No claim rungs, no M-model "
        "counterfactuals, no phase-diagram interpretation.",
        "",
        "## Inputs",
        "",
        f"- T0 manifest sha: `{index.get('t0_manifest_sha256')}`",
        f"- Sessions graphed: **{index['sessions']}**",
        f"- By source: {index.get('by_source')}",
        f"- Tier-0 instrumented sessions: **{index.get('tier0_instrumented_sessions')}**",
        f"- Graph index sha: `{index.get('index_sha256')}`",
        "",
        "## Gates",
        "",
        "| Gate | Result | Errors |",
        "|---|---|---:|",
    ]
    for name in ("G_V", "G_D", "G_A", "G_R", "G_J"):
        g = gates[name]
        lines.append(
            f"| {name} | {'PASS' if g['pass'] else 'FAIL'} | {g['error_count']} |"
        )
    repl = index.get("replication") or {}
    s1 = repl.get("S1") or {}
    s2 = repl.get("S2") or {}
    lines.extend(
        [
            "",
            "G-J FAIL without human κ is expected (Tier-J demoted; not load-bearing).",
            "",
            "## Replication (task_id × seed)",
            "",
            f"- S2 (load-bearing for T1): "
            f"{s2.get('tasks_meeting_n')}/{s2.get('tasks_total')} templates "
            f"with n≥{repl.get('required_seeds')} "
            f"({'PASS' if s2.get('pass') else 'FAIL'})",
            f"- S1 (coverage only): "
            f"{s1.get('tasks_meeting_n')}/{s1.get('tasks_total')} task_ids "
            f"with n≥{repl.get('required_seeds')} — sparse cells must not "
            f"receive T2 bands",
            "",
            "## Handoff",
            "",
        ]
    )
    if index["t1_pass"]:
        lines.append(
            f"T1 COMPLETE — dependence graphs frozen at `{index['index_sha256']}`, "
            "T2 eligible"
        )
    else:
        failed = [n for n in ("G_V", "G_D", "G_A", "G_R") if not gates[n]["pass"]]
        lines.append("T1 BLOCKED on " + ", ".join(failed))
    lines.append("")
    lines.append("Do not begin T2 machine-model simulation in this report.")
    text = "\n".join(lines) + "\n"
    if find_rung_labels(text):
        raise SystemExit("T1 report must not contain rung labels")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_V2)
    args = parser.parse_args()

    index = run_t1(manifest_path=args.manifest, out_dir=args.out)
    write_t1_report(index, args.out / "t1_graph_report.md")
    if not index["t1_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
