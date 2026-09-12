"""Phase 0 supplemental inventory: bundles, BFCL JSONL, aggregates."""
from __future__ import annotations

import json
import struct
import tarfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "apu_characterization" / "out"
REPORT = Path(__file__).resolve().parent / "_phase0_inventory2_report.md"


def load_jsonl(path: Path) -> list:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    m = n // 2
    return xs[m] if n % 2 else 0.5 * (xs[m - 1] + xs[m])


def main() -> None:
    lines: list[str] = ["# Phase 0 Inventory Supplement\n"]

    # ---- ttbundle magic / format ----
    lines.append("## TurnTrace .ttbundle format probe\n")
    bundles = sorted((OUT / "turntrace_v2").rglob("*.ttbundle"))
    for b in bundles[:3] + [bundles[-1]] if bundles else []:
        raw = b.read_bytes()[:64]
        lines.append(f"### `{b.relative_to(ROOT)}` size={b.stat().st_size}")
        lines.append(f"- magic hex: {raw[:16].hex()}")
        lines.append(f"- magic ascii-ish: {raw[:16]!r}")
        for opener, name in [
            (lambda p: zipfile.ZipFile(p), "zip"),
            (lambda p: tarfile.open(p), "tar"),
        ]:
            try:
                with opener(b) as arch:
                    names = arch.getnames() if hasattr(arch, "getnames") else arch.namelist()
                    lines.append(f"- opens as {name}: members={names[:20]}")
            except Exception as e:
                lines.append(f"- not {name}: {type(e).__name__}: {e}")
        # try msgpack / zlib / gzip / zstd / lz4
        import gzip, zlib

        for label, fn in [
            ("gzip", lambda x: gzip.decompress(x)),
            ("zlib", lambda x: zlib.decompress(x)),
        ]:
            try:
                dec = fn(raw if False else b.read_bytes())
                lines.append(f"- {label} decompress ok, first32={dec[:32]!r}")
                try:
                    obj = json.loads(dec)
                    lines.append(f"  json type={type(obj).__name__}")
                except Exception:
                    pass
            except Exception as e:
                lines.append(f"- not {label}: {type(e).__name__}")
        # try msgpack
        try:
            import msgpack

            obj = msgpack.unpackb(b.read_bytes(), raw=False, strict_map_key=False)
            lines.append(f"- msgpack ok type={type(obj).__name__}")
            if isinstance(obj, dict):
                lines.append(f"  keys={list(obj.keys())[:40]}")
                lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:2500]}\n```")
            elif isinstance(obj, list):
                lines.append(f"  list len={len(obj)}")
                if obj:
                    lines.append(f"```json\n{json.dumps(obj[0], indent=2, default=str)[:2500]}\n```")
        except Exception as e:
            lines.append(f"- not msgpack / no msgpack: {type(e).__name__}: {e}")

        # custom header?
        data = b.read_bytes()
        if len(data) >= 8:
            lines.append(f"- u32le[0]={struct.unpack_from('<I', data, 0)[0]} u32le[1]={struct.unpack_from('<I', data, 4)[0]}")
            lines.append(f"- u32be[0]={struct.unpack_from('>I', data, 0)[0]}")

    # Search code for ttbundle writer
    lines.append("\n## Code references to ttbundle writer\n")
    hits = []
    for p in (ROOT / "apu_characterization").rglob("*.py"):
        if ".venv" in str(p):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "ttbundle" in txt.lower():
            hits.append(str(p.relative_to(ROOT)))
    for h in hits[:40]:
        lines.append(f"- `{h}`")

    # ---- TurnTrace events aggregate ----
    lines.append("\n## TurnTrace events.json aggregate\n")
    event_files = sorted((OUT / "turntrace_v2").rglob("*.events.json"))
    by_area: dict[str, list[Path]] = defaultdict(list)
    for f in event_files:
        area = f.relative_to(OUT / "turntrace_v2").parts[0]
        by_area[area].append(f)
    lines.append(f"Total event files: {len(event_files)}")
    for area, files in sorted(by_area.items()):
        traj_ids = set()
        turns = []
        tool_alphabet = Counter()
        multi_tool_turns = 0
        empty_tool_turns = 0
        total_turns = 0
        for f in files:
            try:
                obj = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(obj, list):
                continue
            turns.append(len(obj))
            total_turns += len(obj)
            for row in obj:
                if not isinstance(row, dict):
                    continue
                traj_ids.add(row.get("trajectory_id") or f.stem)
                tools = row.get("tool_names") or []
                if not tools:
                    empty_tool_turns += 1
                    tool_alphabet["__NO_TOOL__"] += 1
                else:
                    if len(tools) > 1:
                        multi_tool_turns += 1
                    for t in tools:
                        tool_alphabet[str(t)] += 1
        lines.append(f"\n### area `{area}` files={len(files)}")
        lines.append(f"- distinct trajectories (file/field): {len(traj_ids)}")
        if turns:
            lines.append(f"- turns/file min/med/max: {min(turns)}/{median(turns)}/{max(turns)}")
        lines.append(f"- total_turns: {total_turns}")
        lines.append(f"- empty_tool_turns: {empty_tool_turns}")
        lines.append(f"- multi_tool_turns: {multi_tool_turns}")
        lines.append(f"- tool alphabet size: {len(tool_alphabet)}")
        lines.append(f"- top tools: {tool_alphabet.most_common(15)}")

    # ---- OA-01 tool alphabet ----
    lines.append("\n## OA-01 tool alphabet / decision points\n")
    turn_files = sorted((OUT / "oa01").rglob("turn_records.jsonl"))
    tool_alphabet = Counter()
    status_c = Counter()
    is_tool = Counter()
    step_sem = Counter()
    per_traj_turns = []
    for tf in turn_files:
        rows = load_jsonl(tf)
        per_traj_turns.append(len(rows))
        for r in rows:
            status_c[r.get("status")] += 1
            is_tool[r.get("is_tool_call")] += 1
            step_sem[r.get("step_type_semantic")] += 1
            tools = r.get("tool_names") or []
            if not tools:
                tool_alphabet["__NO_TOOL__/ANSWER"] += 1
            else:
                # for inventory: count each tool occurrence and also turn-level primary
                tool_alphabet[str(tools[0]) + ("+..." if len(tools) > 1 else "")] += 1
                for t in tools:
                    tool_alphabet[f"occ:{t}"] += 1
    lines.append(f"- trajectories with turn_records: {len(turn_files)}")
    lines.append(f"- turns/traj min/med/max: {min(per_traj_turns)}/{median(per_traj_turns)}/{max(per_traj_turns)}")
    lines.append(f"- is_tool_call: {dict(is_tool)}")
    lines.append(f"- status: {dict(status_c)}")
    lines.append(f"- step_type_semantic top: {step_sem.most_common(20)}")
    lines.append(f"- tool summary counters: {tool_alphabet.most_common(30)}")

    # ---- OA-01 exec_events sample schema ----
    lines.append("\n## OA-01 exec_events.jsonl schema\n")
    ex = next((OUT / "oa01").rglob("exec_events.jsonl"), None)
    if ex:
        rows = load_jsonl(ex)
        lines.append(f"### `{ex.relative_to(ROOT)}` records={len(rows)}")
        if rows:
            # flatten keys
            keys = sorted(rows[0].keys())
            lines.append(f"- keys: {keys}")
            lines.append(f"```json\n{json.dumps(rows[0], indent=2, default=str)[:3000]}\n```")
            if len(rows) > 1:
                lines.append(f"```json\n{json.dumps(rows[1], indent=2, default=str)[:2000]}\n```")
            if len(rows) > 2:
                lines.append(f"```json\n{json.dumps(rows[2], indent=2, default=str)[:2000]}\n```")

    # ---- BFCL as JSONL ----
    lines.append("\n## CAP-01 BFCL multi_turn (JSONL-masquerading-as-.json)\n")
    bfcl = sorted((OUT / "cap01").rglob("BFCL*multi_turn*.json"))
    for p in bfcl:
        rows = load_jsonl(p)
        lines.append(f"\n### `{p.relative_to(ROOT)}`")
        lines.append(f"- format: JSONL (despite .json extension)")
        lines.append(f"- record_count: {len(rows)}")
        if not rows:
            continue
        # session id field
        ids = []
        turn_lens = []
        for r in rows:
            if isinstance(r, dict):
                ids.append(r.get("id") or r.get("question_id"))
                for k in ("question", "ground_truth", "turns", "conversation"):
                    if k in r and isinstance(r[k], list):
                        turn_lens.append(len(r[k]))
                        break
        lines.append(f"- distinct ids: {len(set(map(str, ids)))}")
        if turn_lens:
            lines.append(f"- turns/list-field min/med/max: {min(turn_lens)}/{median(turn_lens)}/{max(turn_lens)}")
        lines.append(f"- top-level keys: {sorted(rows[0].keys())}")
        for i, r in enumerate(rows[:3]):
            # truncate large nested fields
            preview = json.loads(json.dumps(r, default=str))
            for k, v in list(preview.items()):
                s = json.dumps(v, default=str)
                if len(s) > 800:
                    preview[k] = s[:800] + "...<truncated>"
            lines.append(f"#### sample[{i}]\n```json\n{json.dumps(preview, indent=2)[:3500]}\n```")

    # ---- CAP-01: are there live multi-turn agent runs? ----
    lines.append("\n## CAP-01 live agent run search\n")
    # look for directories named runs/results/trajectories
    for sub in ["runs", "results", "trajectories", "live_runs", "matrix", "stage"]:
        d = OUT / "cap01" / sub
        lines.append(f"- `cap01/{sub}` exists={d.exists()}")
    # pools triage is generation triage not agent turns
    triage = list((OUT / "cap01" / "pools_triage").rglob("*.jsonl")) if (OUT / "cap01" / "pools_triage").exists() else []
    lines.append(f"- pools_triage jsonl files: {len(triage)}")
    if triage:
        rows = load_jsonl(triage[0])
        lines.append(f"- example `{triage[0].relative_to(ROOT)}` records={len(rows)} keys={list(rows[0].keys()) if rows else []}")
        if rows:
            lines.append(f"```json\n{json.dumps(rows[0], indent=2, default=str)[:1500]}\n```")

    # ---- TLP-01 ----
    lines.append("\n## TLP-01 structure\n")
    tlp = OUT / "tlp01"
    if tlp.exists():
        # top level
        for p in sorted(tlp.iterdir()):
            lines.append(f"- {p.name}/" if p.is_dir() else f"- {p.name}")
        # dependence graph sample
        g = next(tlp.rglob("Tier_0.json"), None)
        if g:
            obj = json.loads(g.read_text(encoding="utf-8"))
            lines.append(f"\n### `{g.relative_to(ROOT)}`")
            if isinstance(obj, dict):
                lines.append(f"- keys: {list(obj.keys())[:40]}")
                lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:3000]}\n```")
            else:
                lines.append(f"- type={type(obj).__name__} len={len(obj) if hasattr(obj,'__len__') else '?'}")
        agg = tlp / "t2" / "aggregate.json"
        if agg.exists():
            obj = json.loads(agg.read_text(encoding="utf-8"))
            lines.append(f"\n### `{agg.relative_to(ROOT)}`")
            lines.append(f"- keys: {list(obj.keys())[:50] if isinstance(obj, dict) else type(obj)}")
            lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:3000]}\n```")
        # look for tool sequences in extracts
        for p in sorted(tlp.rglob("*.json"))[:]:
            if p.name in {"quotable_extracts.json", "partition.json", "phase_diagram.json"}:
                obj = json.loads(p.read_text(encoding="utf-8"))
                lines.append(f"\n### `{p.relative_to(ROOT)}`")
                if isinstance(obj, dict):
                    lines.append(f"- keys: {list(obj.keys())[:40]}")
                lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:2000]}\n```")

    # ---- MCP ----
    lines.append("\n## MCP-01 / mcp_tax nature check\n")
    mcp = OUT / "mcp_tax"
    if mcp.exists():
        completes = list(mcp.rglob("COMPLETE.json"))
        lines.append(f"- COMPLETE.json count: {len(completes)}")
        if completes:
            obj = json.loads(completes[0].read_text(encoding="utf-8"))
            lines.append(f"- example `{completes[0].relative_to(ROOT)}`")
            lines.append(f"- keys: {list(obj.keys()) if isinstance(obj, dict) else type(obj)}")
            lines.append(f"```json\n{json.dumps(obj, indent=2, default=str)[:2500]}\n```")
        # authenticity audit md
        for md in mcp.glob("mcp01*.md"):
            lines.append(f"- doc `{md.relative_to(ROOT)}` size={md.stat().st_size}")

    # ---- Other aggregates: does replication have tool sequences? ----
    lines.append("\n## Other aggregates: tool-sequence presence\n")
    for name in [
        "real_agent_breakdown.json",
        "real_agent_breakdown_remote_search.json",
        "replication_remote_search_v3.json",
        "tool_locality_ablation.json",
    ]:
        p = OUT / name
        if not p.exists():
            continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        blob = json.dumps(obj, default=str)
        has_tools = any(k in blob for k in ["tool_names", "tool_call", "tools_used", "tool_sequence"])
        lines.append(f"- `{name}` size={p.stat().st_size} has_toolish_fields={has_tools} top_keys={list(obj.keys())[:30] if isinstance(obj, dict) else type(obj)}")
        # dig one level
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    lines.append(f"  - `{k}` list len={len(v)} item_keys={list(v[0].keys())[:30]}")
                    break
                if isinstance(v, dict) and v:
                    first = next(iter(v.values()))
                    if isinstance(first, dict):
                        lines.append(f"  - `{k}` dict n={len(v)} value_keys={list(first.keys())[:30]}")
                        break

    # ---- Parquet/sqlite ----
    lines.append("\n## Parquet/SQLite\n")
    for ext in ("*.parquet", "*.sqlite", "*.db"):
        hits = [
            p
            for p in (ROOT / "apu_characterization").rglob(ext)
            if ".venv" not in str(p) and "site-packages" not in str(p) and "live_sources" not in str(p)
        ]
        lines.append(f"- {ext}: {len(hits)}")
        for p in hits[:15]:
            lines.append(f"  - `{p.relative_to(ROOT)}` ({p.stat().st_size})")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", REPORT)


if __name__ == "__main__":
    main()
