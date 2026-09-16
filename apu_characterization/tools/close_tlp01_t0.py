"""T0 close-out: write manifest + collection report; do NOT start T1."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from apu_characterization.tlp01.contracts import sha256_bytes, sha256_json
from apu_characterization.tlp01.labels import find_rung_labels

REPO = Path(__file__).resolve().parents[2]
TRACES = REPO / "apu_characterization/out/tlp01/traces"
MANIFEST_IN = REPO / "apu_characterization/tlp01/s2_task_manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=TRACES)
    args = parser.parse_args()

    s1_files = sorted((args.traces / "S1").glob("*.jsonl")) if (args.traces / "S1").is_dir() else []
    s2_files = sorted((args.traces / "S2").glob("*.jsonl")) if (args.traces / "S2").is_dir() else []

    entries = []
    tier0_by_template: dict[str, list[int]] = defaultdict(list)
    by_source_class_seed: Counter[str] = Counter()

    for source, files in (("S1", s1_files), ("S2", s2_files)):
        for path in files:
            meta_path = path.with_suffix(path.suffix + ".meta.json")
            meta = (
                json.loads(meta_path.read_text(encoding="utf-8"))
                if meta_path.is_file()
                else {}
            )
            digest = sha256_bytes(path.read_bytes())
            task_id = meta.get("task_id") or path.stem
            seed = meta.get("seed")
            task_class = str(task_id).split("-", 1)[0]
            entry = {
                "path": str(path.relative_to(REPO)).replace("\\", "/"),
                "source": source,
                "task_id": task_id,
                "task_class": task_class,
                "seed": seed,
                "trace_sha256": digest,
                "dep_refs_coverage": (
                    "null"
                    if source == "S1"
                    else "instrumented"
                ),
                "tier0_edge_count": meta.get("tier0_edge_count"),
                "negative_control": meta.get("negative_control"),
                "tool_call_count": meta.get("tool_call_count"),
            }
            entries.append(entry)
            by_source_class_seed[f"{source}:{task_class}:s{seed}"] += 1
            if source == "S2" and meta.get("tier0_edge_count") is not None:
                tier0_by_template[str(task_id)].append(int(meta["tier0_edge_count"]))

    s2_manifest = json.loads(MANIFEST_IN.read_text(encoding="utf-8"))
    negatives = [
        t["task_id"]
        for t in s2_manifest["templates"]
        if t.get("negative_control")
    ]

    freeze = {}
    freeze_path = args.traces / "SCHEMA_FREEZE.json"
    if freeze_path.is_file():
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))

    discard_path = args.traces / "S2_discard_log.jsonl"
    discards = []
    if discard_path.is_file():
        for line in discard_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                discards.append(json.loads(line))

    manifest = {
        "phase": "T0",
        "trace_count": len(entries),
        "s1_count": len(s1_files),
        "s2_count": len(s2_files),
        "schema_freeze": freeze,
        "s2_task_manifest_sha256": sha256_bytes(MANIFEST_IN.read_bytes()),
        "negative_control_templates": negatives,
        "traces": entries,
        "dep_refs_coverage_note": (
            "S1 dep_refs are null (legacy). S2 is instrumented. "
            "Absence of a dep_ref is silence, not independence."
        ),
    }
    manifest_sha = sha256_json(manifest)
    manifest["manifest_sha256"] = manifest_sha

    blob = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if find_rung_labels(blob):
        raise SystemExit("T0 manifest must not contain rung labels")
    (args.traces / "manifest.json").write_text(blob, encoding="utf-8")

    s1_ok = len(s1_files) >= 30
    s2_ok = len(s2_files) >= 50
    status = "T0 COMPLETE" if (s1_ok and s2_ok) else "T0 BLOCKED"

    lines = [
        "# TLP-01 T0 collection report",
        "",
        f"**Status:** {status}",
        "",
        "This phase produces a frozen trace inventory only. No claim rungs, "
        "no TLP verdicts, no phase-diagram interpretation.",
        "",
        "## Yield",
        "",
        f"- S1 usable traces: **{len(s1_files)}** (criterion ≥ 30: "
        f"{'PASS' if s1_ok else 'FAIL'})",
        f"- S2 usable traces: **{len(s2_files)}** (criterion 50/50: "
        f"{'PASS' if s2_ok else 'FAIL'})",
        f"- Schema freeze: `{freeze.get('trace_schema_sha256', 'missing')}`",
        f"- Manifest hash: `{manifest_sha}`",
        "",
        "## Negative-control templates (named for T1 calibration)",
        "",
    ]
    for name in negatives:
        lines.append(f"- `{name}`")
    lines.extend(["", "## Tier-0 edge counts per S2 template", ""])
    if not tier0_by_template:
        lines.append("_No S2 Tier-0 stats yet._")
    else:
        lines.extend(
            [
                "| Template | Sessions | Tier-0 edges (sum) | Mean |",
                "|---|---:|---:|---:|",
            ]
        )
        for task_id, counts in sorted(tier0_by_template.items()):
            total = sum(counts)
            mean = total / len(counts)
            lines.append(
                f"| {task_id} | {len(counts)} | {total} | {mean:.2f} |"
            )

    lines.extend(
        [
            "",
            "## Discard log (S2)",
            "",
            f"- Discard entries: **{len(discards)}**",
        ]
    )
    reasons = Counter(d.get("reason") for d in discards)
    for reason, count in sorted(reasons.items()):
        lines.append(f"- `{reason}`: {count}")

    blocked = []
    if not s1_ok:
        blocked.append(f"S1 usable traces {len(s1_files)} < 30")
    if not s2_ok:
        blocked.append(f"S2 usable traces {len(s2_files)} < 50")

    lines.extend(["", "## Handoff", ""])
    if status == "T0 COMPLETE":
        lines.append(
            f"T0 COMPLETE — trace store frozen at `{manifest_sha}`, T1 eligible"
        )
    else:
        lines.append(
            "T0 BLOCKED on " + "; ".join(blocked)
        )
    lines.append("")
    lines.append("Do not begin T1 graph construction in this report.")

    report = "\n".join(lines) + "\n"
    if find_rung_labels(report):
        raise SystemExit("T0 report must not contain rung labels")
    (args.traces / "t0_collection_report.md").write_text(report, encoding="utf-8")
    print(report)
    if status != "T0 COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
