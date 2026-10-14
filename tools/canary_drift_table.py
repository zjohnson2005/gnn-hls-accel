"""Canary series across sessions since 2026-10-12 (task AA; analysis only).

Reads committed canary records, summaries and host manifests. Changes no
threshold and runs nothing. For each session: every canary (t1, t2, drift,
threshold, trip), elapsed seconds since canary 0, host uptime, memory and
power fields, and the workload between consecutive canaries (NPU rungs or
P1 entries/steps). Thermal fields: none are recorded by the canary.

  python tools/canary_drift_table.py --out analysis/canary/CANARY_DRIFT_20261014.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "derived"

# (label, host, kind, canary dir, run dir or None, manifest or None)
SESSIONS: tuple[tuple[str, str, str, str, str | None, str | None], ...] = (
    (
        "P1 A5 e31a0a89",
        "XPS",
        "p1",
        "p1_quality/e31a0a89-862e-444a-b197-0c8d61cbb0e1/work",
        "p1_quality/e31a0a89-862e-444a-b197-0c8d61cbb0e1",
        "p1_quality/P1_SOURCE_MANIFEST_20261012.txt",
    ),
    (
        "P1 A5 824cad12",
        "XPS",
        "p1",
        "p1_quality/824cad12-662f-485d-a832-0f7f25ee4dcd/work",
        "p1_quality/824cad12-662f-485d-a832-0f7f25ee4dcd",
        "p1_quality/P1_SOURCE_MANIFEST_20261012.txt",
    ),
    (
        "P1 A0 B=10 [0:100] bdc32a87",
        "XPS",
        "p1",
        "p1_quality/bdc32a87-8f91-4cd5-9cb0-2daafe659fc8/work",
        "p1_quality/bdc32a87-8f91-4cd5-9cb0-2daafe659fc8",
        "p1_quality/P1_SOURCE_MANIFEST_20261013.txt",
    ),
    (
        "H1 V1 T2S b026f3fd",
        "T2S",
        "h1",
        "h1_hybrid/_launches/b026f3fd-004e-4419-91bd-80c79f94e0f1/canary_opening",
        None,
        None,
    ),
    (
        "H1 V1 XPS f7343708",
        "XPS",
        "h1",
        "h1_hybrid/_launches/f7343708-a4a5-4984-93e5-ce5412a6c981/canary_opening",
        None,
        None,
    ),
    (
        "H1 V4 T2S f7de976b",
        "T2S",
        "h1",
        "h1_hybrid/_launches/f7de976b-4cad-471f-abd3-c2ff7a0b439b/canary_opening",
        None,
        None,
    ),
    (
        "H1 V3 T2S b323f0e5",
        "T2S",
        "h1",
        "h1_hybrid/_launches/b323f0e5-ce3f-46ac-9748-8549fbcf1cb9/canary_opening",
        None,
        None,
    ),
    (
        "NPU-INT8 1024 1e79daa3",
        "T2S",
        "npu",
        "npu/1e79daa3-0853-4825-a5b3-7cc4e3023213/work",
        "npu/1e79daa3-0853-4825-a5b3-7cc4e3023213",
        None,
    ),
    (
        "H1 V4 XPS a678926e",
        "XPS",
        "h1",
        "h1_hybrid/_launches/a678926e-2681-4851-a386-8b7c83e971a3/canary_opening",
        None,
        None,
    ),
    (
        "H1 V3 T2S a4284ab0",
        "T2S",
        "h1",
        "h1_hybrid/_launches/a4284ab0-7bb4-497a-8ff7-cc4d54817dd8/canary_opening",
        None,
        None,
    ),
    (
        "V5-CAL u8 a178e9c5",
        "XPS",
        "v5cal",
        "delta_prefill/a178e9c5-193e-4221-8f22-d4ffe0803749/work",
        None,
        None,
    ),
    (
        "V5-CAL u4 e1ed06b4",
        "XPS",
        "v5cal",
        "delta_prefill/e1ed06b4-a2c2-4de2-b27b-b7b5e3190122/work",
        None,
        None,
    ),
    (
        "V5-CAL u8 V5-path 15993163",
        "XPS",
        "v5cal",
        "delta_prefill/15993163-d636-4008-beb7-869221a59a85/work",
        None,
        None,
    ),
    (
        "NPU-INT8 2048a 0fd9cd8c",
        "T2S",
        "npu",
        "npu/0fd9cd8c-9270-4d6f-ac8d-da3cada3e5a4/work",
        "npu/0fd9cd8c-9270-4d6f-ac8d-da3cada3e5a4",
        None,
    ),
    (
        "P1 A4 B=10 [0:53] a766bd0b",
        "XPS",
        "p1",
        "p1_quality/a766bd0b-0f49-46af-be1f-af75f164e0ae/work",
        "p1_quality/a766bd0b-0f49-46af-be1f-af75f164e0ae",
        "p1_quality/P1_SOURCE_MANIFEST_a766bd0b.txt",
    ),
    (
        "NPU-INT8 4096 63d35555",
        "T2S",
        "npu",
        "npu/63d35555-2504-45a4-b0f5-74639e4d2278/work",
        "npu/63d35555-2504-45a4-b0f5-74639e4d2278",
        None,
    ),
    (
        "P1 A4 B=10 [53:100] eb6cd6ce",
        "XPS",
        "p1",
        "p1_quality/eb6cd6ce-ad9f-4b61-898d-bde9585a56cb/work",
        "p1_quality/eb6cd6ce-ad9f-4b61-898d-bde9585a56cb",
        "p1_quality/P1_SOURCE_MANIFEST_eb6cd6ce.txt",
    ),
    (
        "NPU-INT8 2048b e8a27848 (VOID)",
        "T2S",
        "npu",
        "VOIDS/e8a27848/part2_recreated/work",
        None,
        None,
    ),
    (
        "H1 V4 T2S rerun 30caa847",
        "T2S",
        "h1",
        "h1_hybrid/_launches/30caa847-d97a-4e4b-aa22-f152b95d08e9/canary_opening",
        None,
        None,
    ),
    (
        "NPU-INT8 2048c 4f6a9102",
        "T2S",
        "npu",
        "npu/4f6a9102-92fc-42d5-bc57-4a99e56c2490/work",
        "npu/4f6a9102-92fc-42d5-bc57-4a99e56c2490",
        None,
    ),
)
NO_CANARY = (
    "NPU-FORMAT-F1 natstop_f1_b172b287 (T2S): no canary recorded (diagnostic, unguarded by design)",
)
REPEATS_PER_RUNG = 3


def _utc(s: str) -> datetime:
    s = s.replace("Z", "")
    if "+" in s[19:]:
        s = s[: 19 + s[19:].index("+")]
    if "." in s:
        head, frac = s.split(".")
        s = head + "." + frac[:6]
    return datetime.fromisoformat(s)


def _canaries(cdir: Path) -> list[dict[str, Any]]:
    rows = []
    for f in sorted(
        (cdir / "canaries").glob("canary.*.json"), key=lambda p: int(p.stem.split(".")[1])
    ):
        doc = json.loads(f.read_text(encoding="utf-8"))
        r = doc.get("record") or {}
        cell = doc.get("cell") or {}
        env = cell.get("environment_start") or {}
        power = r.get("power") or {}
        rows.append(
            {
                "index": r.get("canary_index"),
                "utc": r.get("utc"),
                "after_probe_count": r.get("after_probe_count"),
                "t1_s": r.get("turn1_prefill_s"),
                "t2_s": r.get("turn2_prefill_s"),
                "rel_drift_t1": r.get("rel_drift_t1"),
                "rel_drift_t2": r.get("rel_drift_t2"),
                "threshold_t1": r.get("threshold_t1"),
                "threshold_t2": r.get("threshold_t2"),
                "gate_armed": r.get("gate_armed"),
                "drift_tripped": r.get("drift_tripped"),
                "discarded_from_calibration": r.get("discarded_from_calibration"),
                "trip_detail": r.get("trip_detail"),
                "uptime_s": env.get("uptime_s"),
                "available_mb": env.get("available_mb"),
                "committed_mb": env.get("committed_mb"),
                "process_count": env.get("process_count"),
                "on_ac": power.get("on_ac"),
                "charge_pct": power.get("estimated_charge_remaining_pct"),
                "canary_model": cell.get("model_id"),
                "canary_arm": cell.get("arm_id"),
            }
        )
    if rows:
        t0 = _utc(rows[0]["utc"])
        for row in rows:
            row["elapsed_s"] = round((_utc(row["utc"]) - t0).total_seconds(), 1)
    return rows


def _npu_workload(
    run: Path | None, rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rungs whose repeats ran before each canary (probe k is repeat k % 3 of rung k // 3)."""
    summary = {}
    if run is not None and (run / "summary.json").is_file():
        summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    rungs = [int(r["n_tokens"]) for r in summary.get("rungs") or []]
    known = bool(rungs)
    if not rungs:
        # Refused sessions keep no rung records; bisection visits low, then high
        # (summary max_prompt_len is the high rung, S - 64).
        high = summary.get("max_prompt_len")
        rungs = [64] + ([int(high)] if high else [])
    out = []
    prev = -1
    for row in rows:
        a = row["after_probe_count"]
        if a is None or a < 0:
            continue
        probes = list(range(prev + 1, a + 1))
        out.append(
            {
                "before_canary": row["index"],
                "probes": len(probes),
                "rungs_tokens": sorted(
                    {
                        rungs[p // REPEATS_PER_RUNG]
                        for p in probes
                        if p // REPEATS_PER_RUNG < len(rungs)
                    }
                ),
                "validity_repeats": sum(1 for p in probes if p % REPEATS_PER_RUNG == 0),
                "rung_list_source": "summary.rungs"
                if known
                else "bisection order (low, high); refused summary keeps no rungs",
            }
        )
        prev = a
    series = (summary.get("npu_canary_series") or {}).get("samples") or []
    return out, [
        {"after_probe_count": s.get("after_probe_count"), "npu_prefill_s": s.get("prefill_s")}
        for s in series
    ]


def _manifest_mtimes(manifest: Path, run_id: str) -> dict[str, datetime]:
    out = {}
    for line in manifest.read_text(encoding="utf-8").replace("\r", "").splitlines():
        parts = line.split("|")
        if len(parts) == 5 and parts[0] == run_id and parts[1].startswith("points/"):
            out[parts[1]] = _utc(parts[4])
    return out


def _p1_workload(run: Path, manifest: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mt = _manifest_mtimes(manifest, run.name)
    pts = []
    for rel, when in mt.items():
        doc = json.loads((run / rel).read_text(encoding="utf-8"))
        pts.append((when, len(doc.get("steps") or []), float(doc.get("wall_s") or 0.0)))
    out = []
    for prev, row in itertools.pairwise(rows):
        lo, hi = _utc(prev["utc"]), _utc(row["utc"])
        inside = [p for p in pts if lo < p[0] <= hi]
        out.append(
            {
                "before_canary": row["index"],
                "entries": len(inside),
                "steps": sum(p[1] for p in inside),
                "entry_wall_s": round(sum(p[2] for p in inside), 1),
            }
        )
    return out


def table() -> dict[str, Any]:
    sessions = []
    for label, host, kind, cdir, run, manifest in SESSIONS:
        rows = _canaries(D / cdir)
        entry: dict[str, Any] = {"session": label, "host": host, "kind": kind, "canaries": rows}
        if kind == "npu":
            entry["workload"], entry["npu_canary_series"] = _npu_workload(
                None if run is None else D / run, rows
            )
        elif kind == "p1" and run and manifest:
            entry["workload"] = _p1_workload(D / run, D / manifest, rows)
        armed = [r for r in rows if r["gate_armed"]]
        # Calibration: kept (not warm-up) canaries up to the one that armed the
        # gate; checked: canaries carrying a drift value.
        last = armed[0]["index"] if armed else -1
        calib = [
            r
            for r in rows
            if r["index"] <= last
            and not r["discarded_from_calibration"]
            and r["rel_drift_t1"] is None
        ]
        checked = [r for r in rows if r["rel_drift_t1"] is not None]
        entry["calibration_indices"] = [r["index"] for r in calib]
        if calib:
            ref1 = statistics.median(r["t1_s"] for r in calib)
            ref2 = statistics.median(r["t2_s"] for r in calib)
            entry["ref_t1"], entry["ref_t2"] = ref1, ref2
            entry["calib_spread_t1"] = round(max(abs(r["t1_s"] - ref1) / ref1 for r in calib), 6)
            entry["calib_spread_t2"] = round(max(abs(r["t2_s"] - ref2) / ref2 for r in calib), 6)
            for r in checked:
                r["t1_signed"] = round(r["t1_s"] / ref1 - 1, 6)
                r["t2_signed"] = round(r["t2_s"] / ref2 - 1, 6)
        entry["first_checked"] = (
            None
            if not checked or not calib
            else {
                k: checked[0][k]
                for k in ("index", "t1_signed", "t2_signed", "threshold_t1", "threshold_t2")
            }
        )
        trip = next((r for r in rows if r["drift_tripped"]), None)
        entry["trip"] = (
            None
            if trip is None
            else {
                "index": trip["index"],
                "elapsed_s": trip["elapsed_s"],
                "uptime_s": trip["uptime_s"],
                "detail": trip["trip_detail"],
            }
        )
        entry["armed"] = bool(armed)
        sessions.append(entry)
    return {
        "kind": "canary_drift_table",
        "since": "2026-10-12",
        "thermal_fields": "none recorded",
        "no_canary": list(NO_CANARY),
        "sessions": sessions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = table()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    for s in doc["sessions"]:
        f = s["first_checked"] or {}
        print(
            f"{s['session']:34s} n={len(s['canaries'])} spread_t1={s.get('calib_spread_t1')} "
            f"post1 t1={f.get('t1_signed')} t2={f.get('t2_signed')} thr={f.get('threshold_t1')}/{f.get('threshold_t2')} "
            f"trip={s['trip']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
