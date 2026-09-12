"""Phase 0 inventory: discover agent-trace artifacts and report schemas/stats."""
from __future__ import annotations

import json
import statistics
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "apu_characterization" / "out"
REPORT = Path(__file__).resolve().parent / "_phase0_inventory_report.md"


def median(xs: list[float]) -> float | None:
    if not xs:
        return None
    return float(statistics.median(xs))


def schema_of(obj: Any, prefix: str = "", depth: int = 0, max_depth: int = 4) -> dict[str, str]:
    keys: dict[str, str] = {}
    if depth > max_depth:
        return keys
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, list):
                keys[p] = f"list[{type(v[0]).__name__ if v else 'empty'}] len={len(v)}"
                if v and isinstance(v[0], (dict, list)):
                    keys.update(schema_of(v[0], p + "[]", depth + 1, max_depth))
            elif isinstance(v, dict):
                keys[p] = "dict"
                keys.update(schema_of(v, p, depth + 1, max_depth))
            else:
                keys[p] = type(v).__name__
    elif isinstance(obj, list) and obj:
        keys[prefix or "root"] = f"list[{type(obj[0]).__name__}] len={len(obj)}"
        if isinstance(obj[0], dict):
            keys.update(schema_of(obj[0], (prefix or "root") + "[]", depth + 1, max_depth))
    return keys


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dump_samples(rows: list[Any], n: int = 3) -> str:
    chunks = []
    for i, row in enumerate(rows[:n]):
        chunks.append(f"### sample[{i}]\n```json\n{json.dumps(row, indent=2, default=str)[:4000]}\n```")
    return "\n\n".join(chunks)


def section(title: str) -> str:
    return f"\n\n## {title}\n"


def main() -> None:
    lines: list[str] = ["# Phase 0 Inventory — Agent Trace Artifacts\n"]
    lines.append(f"Repo root: `{ROOT}`\n")
    lines.append(f"Primary out dir: `{OUT}`\n")

    # ------------------------------------------------------------------
    # 1. TurnTrace trajectory_records.jsonl
    # ------------------------------------------------------------------
    lines.append(section("1. TurnTrace — trajectory_records.jsonl"))
    tt_files = sorted((OUT / "turntrace_v2").rglob("trajectory_records.jsonl"))
    lines.append(f"Found **{len(tt_files)}** trajectory_records.jsonl files.\n")
    for fp in tt_files:
        rows = load_jsonl(fp)
        turns = [r.get("n_turns") for r in rows if isinstance(r.get("n_turns"), (int, float))]
        tid = {r.get("trajectory_id") for r in rows}
        lines.append(f"### `{fp.relative_to(ROOT)}`")
        lines.append(f"- format: JSONL")
        lines.append(f"- record_count: {len(rows)}")
        lines.append(f"- distinct_sessions/trajectories: {len(tid)}")
        if turns:
            lines.append(
                f"- turns_per_trajectory (n_turns field): "
                f"min={min(turns)} median={median(turns)} max={max(turns)}"
            )
        if rows:
            lines.append("- schema:")
            for k, t in sorted(schema_of(rows[0]).items()):
                lines.append(f"  - `{k}`: {t}")
            lines.append(dump_samples(rows, 3))
        lines.append("")

    # ------------------------------------------------------------------
    # 1b. TurnTrace ttbundles
    # ------------------------------------------------------------------
    lines.append(section("1b. TurnTrace — .ttbundle archives"))
    bundles = sorted((OUT / "turntrace_v2").rglob("*.ttbundle"))
    lines.append(f"Found **{len(bundles)}** `.ttbundle` files.\n")
    # group by parent area
    by_area: Counter[str] = Counter()
    for b in bundles:
        parts = b.relative_to(OUT / "turntrace_v2").parts
        area = parts[0] if parts else "?"
        by_area[area] += 1
    lines.append("Counts by top-level area:")
    for k, v in sorted(by_area.items()):
        lines.append(f"- `{k}`: {v}")

    # Inspect a few representative bundles
    candidates = []
    for needle in [
        "rev_c_cp2/class_i/bundles",
        "cloud_full/cell_C1/bundles_all",
        "cloud_full/cell_C2/bundles_all",
        "_gate_smoke/replay/bundles",
    ]:
        hits = [b for b in bundles if needle.replace("/", "\\") in str(b) or needle in str(b).replace("\\", "/")]
        if hits:
            candidates.append(hits[0])

    for bundle in candidates[:4]:
        lines.append(f"\n### Bundle inspect: `{bundle.relative_to(ROOT)}` (size={bundle.stat().st_size})")
        try:
            with zipfile.ZipFile(bundle) as z:
                names = z.namelist()
                lines.append(f"- format: ZIP (.ttbundle)")
                lines.append(f"- members ({len(names)}): {names[:40]}")
                # try to find turn/tool related
                for name in names:
                    if any(x in name.lower() for x in ["turn", "tool", "traj", "event", "record", "manifest"]):
                        raw = z.read(name)
                        lines.append(f"- member `{name}` size={len(raw)}")
                        try:
                            txt = raw.decode("utf-8")
                            if txt.lstrip()[:1] in "{[":
                                obj = json.loads(txt)
                                if isinstance(obj, list):
                                    lines.append(f"  - JSON list len={len(obj)}")
                                    if obj:
                                        lines.append("  - schema[0]:")
                                        for k, t in sorted(schema_of(obj[0]).items())[:80]:
                                            lines.append(f"    - `{k}`: {t}")
                                        lines.append(dump_samples(obj, 3))
                                else:
                                    lines.append("  - schema:")
                                    for k, t in sorted(schema_of(obj).items())[:80]:
                                        lines.append(f"    - `{k}`: {t}")
                                    lines.append(
                                        f"```json\n{json.dumps(obj, indent=2, default=str)[:3000]}\n```"
                                    )
                            elif name.endswith(".jsonl"):
                                rows = [json.loads(l) for l in txt.splitlines() if l.strip()]
                                lines.append(f"  - JSONL rows={len(rows)}")
                                if rows:
                                    for k, t in sorted(schema_of(rows[0]).items())[:80]:
                                        lines.append(f"    - `{k}`: {t}")
                                    lines.append(dump_samples(rows, 3))
                        except Exception as e:
                            lines.append(f"  - parse error: {e}")
        except zipfile.BadZipFile:
            # maybe raw json/jsonl
            try:
                txt = bundle.read_text(encoding="utf-8")
                lines.append("- format: text (not zip)")
                lines.append(f"```\n{txt[:2000]}\n```")
            except Exception as e:
                lines.append(f"- unreadable: {e}")

    # ------------------------------------------------------------------
    # 1c. TurnTrace events.json
    # ------------------------------------------------------------------
    lines.append(section("1c. TurnTrace — *.events.json"))
    event_files = sorted((OUT / "turntrace_v2").rglob("*.events.json"))
    lines.append(f"Found **{len(event_files)}** events.json files.\n")
    if event_files:
        # summarize sizes
        sizes = [f.stat().st_size for f in event_files]
        lines.append(f"- size bytes: min={min(sizes)} median={median(sizes)} max={max(sizes)}")
        ev = event_files[0]
        obj = json.loads(ev.read_text(encoding="utf-8"))
        lines.append(f"\n### `{ev.relative_to(ROOT)}`")
        if isinstance(obj, list):
            lines.append(f"- format: JSON list")
            lines.append(f"- record_count: {len(obj)}")
            if obj:
                lines.append("- schema[0]:")
                for k, t in sorted(schema_of(obj[0]).items())[:100]:
                    lines.append(f"  - `{k}`: {t}")
                lines.append(dump_samples(obj, 3))
        else:
            lines.append("- format: JSON object")
            lines.append("- schema:")
            for k, t in sorted(schema_of(obj).items())[:120]:
                lines.append(f"  - `{k}`: {t}")
            # if has turns/tools extract counts
            for key in ("turns", "events", "records", "tool_calls"):
                if isinstance(obj, dict) and key in obj and isinstance(obj[key], list):
                    lines.append(f"- `{key}` length: {len(obj[key])}")
            lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:4000]}\n```")

    # ------------------------------------------------------------------
    # 2. OA-01
    # ------------------------------------------------------------------
    lines.append(section("2. OA-01 — turn_records.jsonl / trajectory_record.json"))
    oa_runs = sorted((OUT / "oa01" / "runs").glob("OA01-*")) if (OUT / "oa01" / "runs").exists() else []
    lines.append(f"Found **{len(oa_runs)}** OA01 run directories under `out/oa01/runs/`.\n")
    turn_files = sorted((OUT / "oa01").rglob("turn_records.jsonl"))
    traj_files = sorted((OUT / "oa01").rglob("trajectory_record.json"))
    lines.append(f"- turn_records.jsonl files: {len(turn_files)}")
    lines.append(f"- trajectory_record.json files: {len(traj_files)}")

    # Aggregate turn stats across all turn_records
    all_turn_counts: list[int] = []
    all_traj_ids: set[str] = set()
    total_turn_rows = 0
    sample_rows: list[dict] = []
    schema_sample: dict | None = None
    for tf in turn_files:
        rows = load_jsonl(tf)
        total_turn_rows += len(rows)
        all_turn_counts.append(len(rows))
        for r in rows:
            tid = r.get("trajectory_id") or r.get("run_id") or tf.parent.parent.name
            all_traj_ids.add(str(tid))
        if schema_sample is None and rows:
            schema_sample = rows[0]
            sample_rows = rows[:3]

    lines.append(f"\n### Aggregate over all OA-01 turn_records.jsonl")
    lines.append(f"- format: JSONL (one turn per line)")
    lines.append(f"- total_turn_records: {total_turn_rows}")
    lines.append(f"- distinct_trajectories (from field or dirname): {len(all_traj_ids)}")
    if all_turn_counts:
        lines.append(
            f"- turns_per_trajectory: min={min(all_turn_counts)} "
            f"median={median(all_turn_counts)} max={max(all_turn_counts)}"
        )
    if schema_sample is not None:
        lines.append("- schema:")
        for k, t in sorted(schema_of(schema_sample).items()):
            lines.append(f"  - `{k}`: {t}")
        lines.append(dump_samples(sample_rows, 3))

    # Also inspect one trajectory_record.json and raw boundary records if present
    if traj_files:
        tr = traj_files[0]
        obj = json.loads(tr.read_text(encoding="utf-8"))
        lines.append(f"\n### Example trajectory_record.json: `{tr.relative_to(ROOT)}`")
        lines.append("- schema:")
        for k, t in sorted(schema_of(obj).items())[:100]:
            lines.append(f"  - `{k}`: {t}")
        lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:3000]}\n```")

    # Look for raw API / exec event archives
    for pat in ["**/api_boundary*.jsonl", "**/exec_event*.jsonl", "**/raw/**/*.jsonl", "**/archive/**/*.jsonl"]:
        hits = list((OUT / "oa01").glob(pat)) if False else list((OUT / "oa01").rglob(pat.split("/")[-1]))
        # rglob with simple name
    rawish = []
    for name in [
        "api_boundary.jsonl",
        "oa01_api_boundary.jsonl",
        "exec_events.jsonl",
        "oa01_exec_event.jsonl",
        "boundary_records.jsonl",
    ]:
        rawish.extend((OUT / "oa01").rglob(name))
    # also any jsonl under runs/*/raw or archive
    for p in (OUT / "oa01").rglob("*.jsonl"):
        if any(x in str(p).lower() for x in ["boundary", "exec", "raw", "archive", "proxy"]):
            rawish.append(p)
    rawish = sorted(set(rawish))
    lines.append(f"\n### OA-01 raw/boundary/exec jsonl candidates: {len(rawish)}")
    for p in rawish[:30]:
        try:
            n = sum(1 for _ in p.open("r", encoding="utf-8"))
        except Exception:
            n = -1
        lines.append(f"- `{p.relative_to(ROOT)}` lines≈{n} size={p.stat().st_size}")
        if n > 0:
            rows = load_jsonl(p)
            if rows:
                lines.append("  schema:")
                for k, t in sorted(schema_of(rows[0]).items())[:60]:
                    lines.append(f"  - `{k}`: {t}")
                lines.append(dump_samples(rows, min(3, len(rows))))

    # ------------------------------------------------------------------
    # 3. CAP-01
    # ------------------------------------------------------------------
    lines.append(section("3. CAP-01"))
    cap = OUT / "cap01"
    lines.append(f"Exists: {cap.exists()}")
    if cap.exists():
        # look for multi-turn / tool / trajectory artifacts
        interesting = []
        for p in cap.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".json", ".jsonl", ".parquet", ".sqlite", ".db", ".csv"}:
                continue
            name = p.name.lower()
            if any(
                x in name
                for x in [
                    "trajectory",
                    "turn",
                    "session",
                    "tool",
                    "trace",
                    "run",
                    "result",
                    "pool",
                    "frontier",
                    "decision",
                ]
            ):
                interesting.append(p)
            # also top-level jsons
            if p.parent == cap and p.suffix in {".json", ".jsonl"}:
                interesting.append(p)
        interesting = sorted(set(interesting), key=lambda x: str(x))
        lines.append(f"Candidate files (filtered): {len(interesting)}")
        # Prefer non-BFCL-source dumps; still report BFCL multi_turn
        for p in interesting[:80]:
            rel = p.relative_to(ROOT)
            # skip huge unpacked wheel dumps except multi_turn
            if "live_sources" in str(rel) and "multi_turn" not in p.name.lower():
                continue
            lines.append(f"\n### `{rel}` size={p.stat().st_size}")
            if p.suffix == ".jsonl":
                rows = load_jsonl(p)
                lines.append(f"- format: JSONL records={len(rows)}")
                if rows:
                    # try detect session/turn structure
                    keys = set().union(*(r.keys() for r in rows[:20] if isinstance(r, dict)))
                    lines.append(f"- top-level keys (first 20 rows union): {sorted(keys)[:40]}")
                    lines.append("- schema[0]:")
                    for k, t in sorted(schema_of(rows[0]).items())[:80]:
                        lines.append(f"  - `{k}`: {t}")
                    lines.append(dump_samples(rows, 3))
            elif p.suffix == ".json":
                try:
                    obj = json.loads(p.read_text(encoding="utf-8"))
                except Exception as e:
                    lines.append(f"- parse error: {e}")
                    continue
                lines.append("- format: JSON")
                if isinstance(obj, list):
                    lines.append(f"- record_count: {len(obj)}")
                    if obj and isinstance(obj[0], dict):
                        lines.append("- schema[0]:")
                        for k, t in sorted(schema_of(obj[0]).items())[:80]:
                            lines.append(f"  - `{k}`: {t}")
                        lines.append(dump_samples(obj, 3))
                elif isinstance(obj, dict):
                    lines.append(f"- top keys: {list(obj.keys())[:40]}")
                    lines.append("- schema:")
                    for k, t in sorted(schema_of(obj).items())[:80]:
                        lines.append(f"  - `{k}`: {t}")
                    lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:2500]}\n```")

        # Explicit BFCL multi-turn datasets
        bfcl = list(cap.rglob("BFCL*multi_turn*.json"))
        lines.append(f"\n### BFCL multi_turn datasets under CAP-01: {len(bfcl)}")
        for p in bfcl[:12]:
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                lines.append(f"- `{p.relative_to(ROOT)}` parse error {e}")
                continue
            lines.append(f"\n#### `{p.relative_to(ROOT)}` size={p.stat().st_size}")
            if isinstance(obj, list):
                lines.append(f"- format: JSON list records={len(obj)}")
                # turns heuristic
                turn_lens = []
                for r in obj:
                    if isinstance(r, dict):
                        for k in ("question", "turns", "conversation", "messages"):
                            if k in r and isinstance(r[k], list):
                                turn_lens.append(len(r[k]))
                                break
                if turn_lens:
                    lines.append(
                        f"- list-field lengths min/med/max: "
                        f"{min(turn_lens)}/{median(turn_lens)}/{max(turn_lens)}"
                    )
                if obj:
                    lines.append("- schema[0]:")
                    for k, t in sorted(schema_of(obj[0]).items())[:80]:
                        lines.append(f"  - `{k}`: {t}")
                    lines.append(dump_samples(obj, 3))
            elif isinstance(obj, dict):
                lines.append(f"- format: JSON object keys={list(obj.keys())[:30]}")
                # sometimes keyed by id
                vals = list(obj.values())
                lines.append(f"- n_keys: {len(obj)}")
                if vals and isinstance(vals[0], (dict, list)):
                    lines.append("- schema of first value:")
                    for k, t in sorted(schema_of(vals[0]).items())[:80]:
                        lines.append(f"  - `{k}`: {t}")
                    lines.append(
                        f"```json\n{json.dumps({list(obj.keys())[0]: vals[0]}, indent=2, default=str)[:3000]}\n```"
                    )

    # ------------------------------------------------------------------
    # 4. TLP-01
    # ------------------------------------------------------------------
    lines.append(section("4. TLP-01"))
    tlp = OUT / "tlp01"
    lines.append(f"Exists: {tlp.exists()}")
    if tlp.exists():
        # dependence graphs often have tool nodes / chains
        graphs = list((tlp / "dependence_graphs_v2").glob("*/Tier_0.json")) if (tlp / "dependence_graphs_v2").exists() else []
        lines.append(f"- dependence_graphs_v2 Tier_0.json count: {len(graphs)}")
        # also look for chain dumps / extract jsonl
        cand = []
        for p in tlp.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".json", ".jsonl", ".md"}:
                continue
            if any(
                x in p.name.lower()
                for x in ["chain", "tool", "traj", "turn", "extract", "aggregate", "partition", "graph"]
            ):
                cand.append(p)
        cand = sorted(set(cand))[:60]
        lines.append(f"- candidate files (sample up to 60): {len(cand)}")
        for p in cand[:25]:
            lines.append(f"\n### `{p.relative_to(ROOT)}` size={p.stat().st_size}")
            if p.suffix == ".jsonl":
                rows = load_jsonl(p)
                lines.append(f"- JSONL records={len(rows)}")
                if rows:
                    for k, t in sorted(schema_of(rows[0]).items())[:60]:
                        lines.append(f"  - `{k}`: {t}")
                    lines.append(dump_samples(rows, 3))
            elif p.suffix == ".json":
                try:
                    obj = json.loads(p.read_text(encoding="utf-8"))
                except Exception as e:
                    lines.append(f"- parse error: {e}")
                    continue
                if isinstance(obj, list):
                    lines.append(f"- JSON list len={len(obj)}")
                    if obj:
                        for k, t in sorted(schema_of(obj[0]).items())[:60]:
                            lines.append(f"  - `{k}`: {t}")
                        lines.append(dump_samples(obj, 3))
                else:
                    lines.append(f"- JSON object keys={list(obj.keys())[:40]}")
                    for k, t in sorted(schema_of(obj).items())[:80]:
                        lines.append(f"  - `{k}`: {t}")
                    lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:2500]}\n```")

    # ------------------------------------------------------------------
    # 5. MCP-01 / mcp_tax
    # ------------------------------------------------------------------
    lines.append(section("5. MCP-01 / mcp_tax"))
    mcp = OUT / "mcp_tax"
    lines.append(f"Exists: {mcp.exists()}")
    if mcp.exists():
        # look for client result / COMPLETE with tool sequences
        completes = sorted(mcp.rglob("COMPLETE.json"))[:20]
        clients = sorted(mcp.rglob("client/result.json"))[:10]
        lines.append(f"- COMPLETE.json count (sampled listing): showing {len(completes)} of many")
        lines.append(f"- client/result.json sample: {len(clients)}")
        for p in (completes[:2] + clients[:2]):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                lines.append(f"- `{p.relative_to(ROOT)}` error {e}")
                continue
            lines.append(f"\n### `{p.relative_to(ROOT)}`")
            if isinstance(obj, dict):
                lines.append(f"- keys: {list(obj.keys())[:40]}")
                for k, t in sorted(schema_of(obj).items())[:60]:
                    lines.append(f"  - `{k}`: {t}")
                lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:2500]}\n```")
            else:
                lines.append(f"- type={type(obj).__name__} preview={str(obj)[:500]}")

    # ------------------------------------------------------------------
    # 6. Other multi-turn / agent breakdown artifacts at out/
    # ------------------------------------------------------------------
    lines.append(section("6. Other out/ agent-run aggregates"))
    for name in [
        "real_agent_breakdown.json",
        "real_agent_breakdown_remote_search.json",
        "replication_remote_search_v3.json",
        "replication_remote_search.json",
        "single_agent_breakdown_debug.json",
        "tool_locality_ablation.json",
    ]:
        p = OUT / name
        if not p.exists():
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            lines.append(f"- `{name}` parse error {e}")
            continue
        lines.append(f"\n### `{p.relative_to(ROOT)}` size={p.stat().st_size}")
        if isinstance(obj, dict):
            lines.append(f"- keys: {list(obj.keys())[:50]}")
            for k, t in sorted(schema_of(obj).items())[:80]:
                lines.append(f"  - `{k}`: {t}")
            # detect sessions
            for key in ("sessions", "runs", "results", "tasks", "per_task", "trajectories"):
                if key in obj and isinstance(obj[key], (list, dict)):
                    n = len(obj[key])
                    lines.append(f"- `{key}` count: {n}")
            lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:2500]}\n```")
        elif isinstance(obj, list):
            lines.append(f"- list len={len(obj)}")
            if obj:
                for k, t in sorted(schema_of(obj[0]).items())[:60]:
                    lines.append(f"  - `{k}`: {t}")
                lines.append(dump_samples(obj, 3))

    # ------------------------------------------------------------------
    # 7. Repo-wide parquet/sqlite
    # ------------------------------------------------------------------
    lines.append(section("7. Parquet / SQLite under apu_characterization"))
    for pat in ("**/*.parquet", "**/*.sqlite", "**/*.db"):
        hits = [p for p in (ROOT / "apu_characterization").rglob(pat[3:]) if p.is_file()]
        # filter venv
        hits = [p for p in hits if ".venv" not in str(p) and "site-packages" not in str(p)]
        lines.append(f"- `{pat}`: {len(hits)}")
        for p in hits[:20]:
            lines.append(f"  - `{p.relative_to(ROOT)}` size={p.stat().st_size}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}")
    print(f"Lines: {len(lines)}")


if __name__ == "__main__":
    main()
