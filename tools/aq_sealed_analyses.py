"""Task AQ part 6: $0 analyses from sealed hybrid ledgers (read-only inputs).

Writes new files under analysis/aq_20261015/ and edits nothing else:
  a. SILENT_FAILURE_SHARE.json  local outcome classes (pass / loud / silent)
  b. ORACLE_HEADROOM.json        oracle router on BASE_30 (V1 local, V2 cloud)
  c. SPEND_ATTRIBUTION.json      DEMO-1 cloud $ by escalation cause
  d. LEVER_SIZE.json             configuration vs routing-policy deltas
  e. RANDOM_BASELINE.json        matched-rate random escalation on BASE_30

Inputs are sealed runs only: d482c621 (H1-3POLICY, W-3 200, XPS GPU) and the
DEMO-1 slo_escalate cells. Definitions are in each output's "definitions".

  python tools/aq_sealed_analyses.py
"""

from __future__ import annotations

import json
import statistics
import sys
from math import comb
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
H1 = ROOT / "derived" / "h1_hybrid"
OUT = ROOT / "analysis" / "aq_20261015"

D482 = H1 / "interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da" / "policies"
D482_POLICIES = ("slo_escalate", "emission_escalate", "full_signal_bounceback")
BASE_30_PIN = H1 / "demo1" / "DEMO1_BASE_30.json"

# DEMO-1 cells: label -> (host, cell, entry set, run dirs). V3 XPS is one cell
# in two chunks. f7de976b is excluded (cloud cost not measured; 30caa847 is
# the same cell with a live cloud turn).
DEMO1_CELLS: dict[str, dict[str, Any]] = {
    "XPS_V1": {"pin": "BASE_30", "dirs": ["slo_escalate_f7343708-a4a5-4984-93e5-ce5412a6c981"]},
    "XPS_V2_CPU": {
        "pin": "BASE_30",
        "dirs": ["slo_escalate_1acc8c58-a637-42a9-ac7a-78267b98f9ed"],
    },
    "XPS_V3": {
        "pin": "PAIRED_15",
        "dirs": [
            "slo_escalate_71d33f7a-96dd-4e48-ba04-79810a3d4dc8",
            "slo_escalate_ab88f47f-3067-4d79-bf1e-ce533ed41fd2",
        ],
    },
    "XPS_V4": {
        "pin": "PAIRED_15",
        "dirs": ["sealed_slo_escalate_a678926e-2681-4851-a386-8b7c83e971a3"],
    },
    "T2S_V1": {"pin": "BASE_30", "dirs": ["slo_escalate_b026f3fd-004e-4419-91bd-80c79f94e0f1"]},
    "T2S_V3": {
        "pin": "PAIRED_15",
        "dirs": ["slo_escalate_a4284ab0-7bb4-497a-8ff7-cc4d54817dd8"],
    },
    "T2S_V4": {
        "pin": "PAIRED_15",
        "dirs": ["slo_escalate_30caa847-d97a-4e4b-aa22-f152b95d08e9"],
    },
}


def _run_ids(dirs: list[str]) -> list[str]:
    return [d.split("_")[-1] for d in dirs]


def load_entries(dirs: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in dirs:
        out.extend(json.loads((d / "turn_ledger.json").read_text(encoding="utf-8"))["entries"])
    return out


def escalated(entry: dict[str, Any]) -> bool:
    turns = entry.get("turns") or []
    return bool(entry.get("bounces")) or any(
        t.get("escalated") or t.get("placement") == "cloud" for t in turns
    )


def loud_signals(entry: dict[str, Any], local_only: bool = True) -> list[str]:
    """Signals a router could observe on the local turns of an entry."""
    sig: list[str] = []
    for t in entry.get("turns") or []:
        if local_only and t.get("placement") != "local":
            continue
        if t.get("emitted_parseable_tool_call") is False:
            sig.append("no_parseable")
        if t.get("tool_exec_error"):
            sig.append("tool_error")
    if entry.get("stop_reason") == "max_steps":
        sig.append("step_budget")
    return sorted(set(sig))


def classify_local(entry: dict[str, Any]) -> str:
    """pass / loud / silent for a never-escalated entry; escalated otherwise."""
    if escalated(entry):
        return "escalated"
    if entry.get("local_pass") or entry.get("hybrid_pass"):
        return "pass"
    return "loud" if loud_signals(entry) else "silent"


def first_escalation_reason(entry: dict[str, Any]) -> str | None:
    for t in entry.get("turns") or []:
        if t.get("bounce_trigger"):
            return "quality:" + str(t["bounce_trigger"])
        reason = t.get("escalate_reason")
        if reason and reason != "stay_cloud":
            return str(reason)
    if entry.get("bounces"):
        return "quality:bounce"
    return None


def cause_bucket(reason: str | None) -> str:
    if reason is None:
        return "none"
    if reason.startswith("ttft"):
        return "step0_ttft"
    if reason.startswith("decode"):
        return "decode"
    if reason.startswith("quality:") or reason in ("no_parseable_tool_call", "step_budget"):
        return "quality"
    return "other"


def per_entry(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["entry_id"]: e for e in entries}


def _summary_counts(classes: list[str]) -> dict[str, int]:
    keys = ("pass", "loud", "silent", "escalated")
    return {k: sum(1 for c in classes if c == k) for k in keys}


def analysis_a() -> dict[str, Any]:
    res: dict[str, Any] = {
        "definitions": {
            "escalated": "any turn on the cloud or any bounce",
            "pass": "never escalated and local_pass (== hybrid_pass when local)",
            "loud": "never escalated, failed, and a local turn has no parseable tool "
            "call or a tool execution error, or the entry hit the step budget",
            "silent": "never escalated, failed, every local turn emitted a parseable "
            "call, no tool error, no step budget: well-formed and wrong",
            "note": "loud means observable by a router; slo_escalate does not act on "
            "it. Escalated entries' local outcome is not observed.",
        },
        "d482c621": {},
        "demo1": {},
    }
    for pol in D482_POLICIES:
        entries = load_entries([D482 / pol])
        classes = [classify_local(e) for e in entries]
        counts = _summary_counts(classes)
        counts["n"] = len(entries)
        counts["silent_share_of_all"] = round(counts["silent"] / len(entries), 4)
        non_esc = len(entries) - counts["escalated"]
        counts["silent_share_of_non_escalated"] = (
            round(counts["silent"] / non_esc, 4) if non_esc else None
        )
        counts["per_entry"] = {e["entry_id"]: c for e, c in zip(entries, classes, strict=True)}
        res["d482c621"][pol] = counts
    for label, cell in DEMO1_CELLS.items():
        entries = load_entries([H1 / d for d in cell["dirs"]])
        classes = [classify_local(e) for e in entries]
        counts = _summary_counts(classes)
        local_turns = [t for e in entries for t in e["turns"] if t.get("placement") == "local"]
        counts.update(
            {
                "n": len(entries),
                "run_ids": _run_ids(cell["dirs"]),
                "local_turns": len(local_turns),
                "local_turns_no_parseable": sum(
                    1 for t in local_turns if t.get("emitted_parseable_tool_call") is False
                ),
                "local_turns_tool_error": sum(1 for t in local_turns if t.get("tool_exec_error")),
                "escalated_entries_with_loud_local_turn_before": sum(
                    1 for e, c in zip(entries, classes, strict=True) if c == "escalated" and loud_signals(e)
                ),
            }
        )
        res["demo1"][label] = counts
    return res


def _pin_ids(path: Path) -> list[str]:
    return [str(x["id"]) for x in json.loads(path.read_text(encoding="utf-8"))]


def analysis_b() -> dict[str, Any]:
    v1 = per_entry(load_entries([H1 / DEMO1_CELLS["XPS_V1"]["dirs"][0]]))
    v2 = per_entry(load_entries([H1 / DEMO1_CELLS["XPS_V2_CPU"]["dirs"][0]]))
    ids = _pin_ids(BASE_30_PIN)
    rows = []
    for i in ids:
        a, b = v1[i], v2[i]
        rows.append(
            {
                "entry": i,
                "local_pass": bool(a.get("local_pass")),
                "local_escalated": escalated(a),
                "cloud_pass": bool(b.get("hybrid_pass")),
                "cloud_usd": float(b.get("cloud_usd_entry") or 0.0),
                "cloud_escalated_turn0": bool(b["turns"] and b["turns"][0].get("escalated")),
            }
        )
    n = len(rows)
    lp = sum(r["local_pass"] for r in rows)
    cp = sum(r["cloud_pass"] for r in rows)
    cloud_usd = sum(r["cloud_usd"] for r in rows)
    keep_local_correct = [r for r in rows if not r["local_pass"]]
    oracle_min = [r for r in rows if not r["local_pass"] and r["cloud_pass"]]
    return {
        "definitions": {
            "local": "XPS V1 GPU f7343708 (0 escalations: every entry ran fully local)",
            "cloud": "XPS V2 CPU 1acc8c58 (every entry escalated at turn 0: cloud for "
            "the whole entry, so it stands in for cloud-only)",
            "oracle_escalate_local_failures": "entries the local run passed stay "
            "local ($0); every other entry goes to the cloud",
            "oracle_min_cost": "as above, but only entries the cloud passes are sent",
        },
        "entry_set": "DEMO1_BASE_30",
        "run_ids": ["f7343708", "1acc8c58"],
        "n": n,
        "all_local": {"passes": lp, "usd": 0.0},
        "all_cloud": {"passes": cp, "usd": round(cloud_usd, 4), "usd_per_task": round(cloud_usd / n, 4)},
        "both_pass": sum(r["local_pass"] and r["cloud_pass"] for r in rows),
        "local_only_pass": sum(r["local_pass"] and not r["cloud_pass"] for r in rows),
        "cloud_only_pass": sum(r["cloud_pass"] and not r["local_pass"] for r in rows),
        "oracle_escalate_local_failures": {
            "passes": lp + sum(r["cloud_pass"] for r in keep_local_correct),
            "usd": round(sum(r["cloud_usd"] for r in keep_local_correct), 4),
            "usd_per_task": round(sum(r["cloud_usd"] for r in keep_local_correct) / n, 4),
            "cloud_entries": len(keep_local_correct),
        },
        "oracle_min_cost": {
            "passes": lp + len(oracle_min),
            "usd": round(sum(r["cloud_usd"] for r in oracle_min), 4),
            "usd_per_task": round(sum(r["cloud_usd"] for r in oracle_min) / n, 4),
            "cloud_entries": len(oracle_min),
        },
        "paired_15": {
            "computable": False,
            "reason": "no DEMO-1 cell runs DEMO1_PAIRED_15 fully local or fully cloud: "
            "V3/V4 cells escalate mid-entry, so per-entry outcomes are hybrid, not "
            "local-vs-cloud pairs. Needs an all-local and an all-cloud cell on the pin.",
        },
        "caveats": [
            "V1 ran on GPU and V2 on CPU; V2 never produced a local token, so its "
            "outcome is the cloud model's from turn 0.",
            "Single runs; run-to-run variance not measured.",
        ],
        "per_entry": rows,
    }


def analysis_c() -> dict[str, Any]:
    res: dict[str, Any] = {
        "definitions": {
            "cause": "the escalate_reason of the first escalating turn of each "
            "entry; slo_escalate is sticky, so every later cloud turn of that entry "
            "is charged to the same cause",
            "step0_ttft": "TTFT > 10 s at step 0 of a user turn",
            "decode": "decode < 6 tok/s",
            "other": "anything else (none expected under slo_escalate)",
        },
        "cells": {},
    }
    for label, cell in DEMO1_CELLS.items():
        entries = load_entries([H1 / d for d in cell["dirs"]])
        buckets: dict[str, float] = {"step0_ttft": 0.0, "decode": 0.0, "other": 0.0}
        n_entries: dict[str, int] = {"step0_ttft": 0, "decode": 0, "other": 0}
        unattributed = 0.0
        first_turns: list[int] = []
        for e in entries:
            usd = float(e.get("cloud_usd_entry") or 0.0)
            reason = first_escalation_reason(e)
            b = cause_bucket(reason)
            if b == "none":
                unattributed += usd
                continue
            if b == "quality":
                b = "other"
            buckets[b] += usd
            n_entries[b] += 1
            for t in e["turns"]:
                if t.get("escalated"):
                    first_turns.append(int(t["turn"]))
                    break
        total = sum(buckets.values()) + unattributed
        res["cells"][label] = {
            "run_ids": _run_ids(cell["dirs"]),
            "entry_set": cell["pin"],
            "total_usd": round(total, 4),
            "usd_by_cause": {k: round(v, 4) for k, v in buckets.items()},
            "share_by_cause": {k: (round(v / total, 4) if total else None) for k, v in buckets.items()},
            "entries_by_cause": n_entries,
            "usd_without_escalation": round(unattributed, 4),
            "escalations_at_turn0": sum(1 for x in first_turns if x == 0),
            "escalations_later": sum(1 for x in first_turns if x > 0),
        }
    return res


def _cell_stats(entries: list[dict[str, Any]], ids: list[str] | None = None) -> dict[str, Any]:
    if ids is not None:
        idx = per_entry(entries)
        entries = [idx[i] for i in ids]
    n = len(entries)
    turns = [t for e in entries for t in e["turns"]]
    local = [t for t in turns if t.get("placement") == "local"]
    ttft = [float(t["ttft_s"]) for t in local if t.get("ttft_s") is not None]
    usd = sum(float(e.get("cloud_usd_entry") or 0.0) for e in entries)
    return {
        "n": n,
        "passes": sum(1 for e in entries if e.get("hybrid_pass")),
        "usd_per_task": round(usd / n, 4) if n else None,
        "local_share": round(len(local) / len(turns), 4) if turns else None,
        "median_local_ttft_s": round(statistics.median(ttft), 3) if ttft else None,
        "escalated_entries": sum(1 for e in entries if escalated(e)),
    }


def analysis_d() -> dict[str, Any]:
    cells = {k: load_entries([H1 / d for d in v["dirs"]]) for k, v in DEMO1_CELLS.items()}
    pols = {p: load_entries([D482 / p]) for p in D482_POLICIES}
    base = _pin_ids(BASE_30_PIN)

    def delta(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k in ("passes", "usd_per_task", "local_share", "median_local_ttft_s"):
            out["d_" + k] = (
                round(b[k] - a[k], 4) if a[k] is not None and b[k] is not None else None
            )
        return out

    rows: list[dict[str, Any]] = []

    def add(kind: str, name: str, a: dict[str, Any], b: dict[str, Any], ids: str, same: bool, runs: str) -> None:
        rows.append(
            {"kind": kind, "change": name, "entry_set": ids, "same_entry_set_as_other_rows": same,
             "runs": runs, "from": a, "to": b, **delta(a, b)}
        )

    s = {k: _cell_stats(v) for k, v in cells.items()}
    add("configuration", "placement GPU -> CPU (XPS)", s["XPS_V1"], s["XPS_V2_CPU"], "BASE_30", True, "f7343708 -> 1acc8c58")
    add("configuration", "retention FULL -> OBS_MASK K=1024 (XPS)", s["XPS_V3"], s["XPS_V4"], "PAIRED_15", False, "71d33f7a+ab88f47f -> a678926e")
    add("configuration", "retention FULL -> OBS_MASK K=1024 (T2S)", s["T2S_V3"], s["T2S_V4"], "PAIRED_15", False, "a4284ab0 -> 30caa847")
    add("yardstick", "hardware XPS -> T2S, V1 (GPU 4B u8)", s["XPS_V1"], s["T2S_V1"], "BASE_30", True, "f7343708 -> b026f3fd")
    add("yardstick", "hardware XPS -> T2S, V4", s["XPS_V4"], s["T2S_V4"], "PAIRED_15", False, "a678926e -> 30caa847")
    p200 = {p: _cell_stats(v) for p, v in pols.items()}
    p30 = {p: _cell_stats(v, base) for p, v in pols.items()}
    for a, b in (("slo_escalate", "emission_escalate"), ("slo_escalate", "full_signal_bounceback"),
                 ("emission_escalate", "full_signal_bounceback")):
        add("routing", f"{a} -> {b} (W-3 200)", p200[a], p200[b], "W-3 200", False, "d482c621")
        add("routing", f"{a} -> {b} (BASE_30 subset)", p30[a], p30[b], "BASE_30", True, "d482c621 restricted to DEMO1_BASE_30")
    return {
        "definitions": {
            "passes": "hybrid passes (count, not rate; n differs by entry set)",
            "usd_per_task": "cloud $ / entries",
            "median_local_ttft_s": "median TTFT over local turns only; cloud latency "
            "is not a timing measurement in these ledgers and is excluded",
            "same_entry_set_as_other_rows": "true for rows on DEMO1_BASE_30, which "
            "can be compared with each other; other rows cannot",
        },
        "caveats": [
            "d482c621 ran RESIDENT on GPU in 2026-09; the DEMO-1 cells ran NON_RESIDENT "
            "in 2026-10 (PREFIX-CACHE-AUDIT). Same entries, different sessions and "
            "scheduler settings.",
            "Single runs; no variance estimate. Descriptive only, not a test of H-B.",
        ],
        "rows": rows,
    }


def _random_baseline(rows: list[tuple[bool, bool, float]], k: int) -> dict[str, Any]:
    """Exact pass distribution when k of n entries are escalated uniformly at random."""
    n = len(rows)
    n11 = sum(1 for lp, cp, _ in rows if lp and cp)
    n10 = sum(1 for lp, cp, _ in rows if lp and not cp)
    n01 = sum(1 for lp, cp, _ in rows if cp and not lp)
    n00 = n - n11 - n10 - n01
    total = comb(n, k)
    dist: dict[int, float] = {}
    for a in range(min(k, n10) + 1):  # escalated local-only-pass entries (lost)
        for b in range(min(k - a, n01) + 1):  # escalated cloud-only-pass entries (gained)
            rest = k - a - b
            if rest > n11 + n00:
                continue
            ways = comb(n10, a) * comb(n01, b) * comb(n11 + n00, rest)
            passes = n11 + (n10 - a) + b
            dist[passes] = dist.get(passes, 0.0) + ways / total
    mean = sum(p * w for p, w in dist.items())
    cdf = 0.0
    lo = hi = None
    for p in sorted(dist):
        cdf += dist[p]
        if lo is None and cdf >= 0.025:
            lo = p
        if hi is None and cdf >= 0.975:
            hi = p
    mean_usd = sum(c for _, _, c in rows) / n
    return {
        "k_escalated": k,
        "expected_passes": round(mean, 3),
        "passes_95pct_interval": [lo, hi],
        "expected_usd_per_task": round(mean_usd * k / n, 4),
    }


def analysis_e() -> dict[str, Any]:
    v1 = per_entry(load_entries([H1 / DEMO1_CELLS["XPS_V1"]["dirs"][0]]))
    v2 = per_entry(load_entries([H1 / DEMO1_CELLS["XPS_V2_CPU"]["dirs"][0]]))
    base = _pin_ids(BASE_30_PIN)
    rows = [
        (bool(v1[i].get("local_pass")), bool(v2[i].get("hybrid_pass")), float(v2[i].get("cloud_usd_entry") or 0.0))
        for i in base
    ]
    pols = {p: per_entry(load_entries([D482 / p])) for p in D482_POLICIES}
    comps = []
    for p, idx in pols.items():
        sub = [idx[i] for i in base]
        k = sum(1 for e in sub if escalated(e))
        comps.append(
            {
                "router": f"d482c621 {p} on BASE_30",
                "observed_passes": sum(1 for e in sub if e.get("hybrid_pass")),
                "observed_usd_per_task": round(sum(float(e.get("cloud_usd_entry") or 0.0) for e in sub) / len(sub), 4),
                "random_at_matched_rate": _random_baseline(rows, k),
            }
        )
    for label in ("XPS_V1", "XPS_V2_CPU", "T2S_V1"):
        idx = per_entry(load_entries([H1 / DEMO1_CELLS[label]["dirs"][0]]))
        sub = [idx[i] for i in base]
        k = sum(1 for e in sub if escalated(e))
        comps.append(
            {
                "router": f"DEMO-1 {label} slo_escalate",
                "observed_passes": sum(1 for e in sub if e.get("hybrid_pass")),
                "observed_usd_per_task": round(sum(float(e.get("cloud_usd_entry") or 0.0) for e in sub) / len(sub), 4),
                "random_at_matched_rate": _random_baseline(rows, k),
            }
        )
    return {
        "definitions": {
            "baseline": "escalate k of the 30 entries uniformly at random at turn 0, "
            "k = the router's number of escalated entries on the same entries; an "
            "escalated entry takes its cloud outcome (V2 1acc8c58), the rest their "
            "local outcome (V1 f7343708). Exact distribution, no simulation.",
        },
        "entry_set": "DEMO1_BASE_30",
        "outcome_sources": ["f7343708 (local)", "1acc8c58 (cloud)"],
        "caveats": [
            "Routers escalate mid-entry; the baseline escalates at turn 0, so it "
            "gives the cloud the whole entry.",
            "d482c621 local outcomes come from a different session (RESIDENT, "
            "2026-09) than V1's; local pass counts differ between them.",
            "W-3 200: not computable (no all-cloud run on the 200; R0 not run).",
            "PAIRED_15: not computable (no all-local or all-cloud cell).",
        ],
        "comparisons": comps,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "SILENT_FAILURE_SHARE.json": analysis_a(),
        "ORACLE_HEADROOM.json": analysis_b(),
        "SPEND_ATTRIBUTION.json": analysis_c(),
        "LEVER_SIZE.json": analysis_d(),
        "RANDOM_BASELINE.json": analysis_e(),
    }
    for name, doc in files.items():
        path = OUT / name
        if path.exists():
            print(f"REFUSED: {path} exists (analysis files are never overwritten)")
            return 1
        doc = {"generated_by": "tools/aq_sealed_analyses.py", **doc}
        path.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
