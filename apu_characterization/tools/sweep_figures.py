"""B4 figures for the c-ladder concurrency sweep.

Reads ONLY ``out/concurrency_sweep.json`` (levels mode) and writes PNG files
to ``out/figures/``. Every plotted number comes from the artifact; nothing is
recomputed from raw runs.

Figures:
  F1  stacked category share of host CPU vs c, plus companion absolute
      category CPU ms per host wall second vs c
  F2  us per ORCH_DISPATCH decision vs c (overlays legacy trace-based points
      from out/legacy_dispatch_points.json when present; silently skipped
      when absent)
  F3  throughput (sessions/min) vs c, with N_max and capacity uplift k
      annotated
  F4  p99 turn-transition latency vs c
  F5  GC and residual per session vs c

Usage (run as a plain script; the tools package __init__ has heavy imports):
  python apu_characterization/tools/sweep_figures.py \\
      [--artifact apu_characterization/out/concurrency_sweep.json] \\
      [--out-dir apu_characterization/out/figures]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DEFAULT_ARTIFACT = Path("apu_characterization/out/concurrency_sweep.json")
DEFAULT_OUT_DIR = Path("apu_characterization/out/figures")
LEGACY_DISPATCH_POINTS = Path("apu_characterization/out/legacy_dispatch_points.json")

# Stacked share buckets for F1 (category -> bucket). Anything else, plus the
# gap to 100%, lands in "other/untagged".
F1_BUCKETS: dict[str, tuple[str, ...]] = {
    "TOOL_COMPUTE": ("TOOL_COMPUTE",),
    "ORCH (setup+dispatch)": ("ORCH_SETUP", "ORCH_DISPATCH"),
    "TOKEN+SERIAL": ("TOKENIZATION", "SERIALIZATION"),
    "CLIENT/HTTP": ("HTTP_CLIENT", "CLIENT_HTTP", "CLIENT_PARSE"),
    "FRAMEWORK+POOL": ("FRAMEWORK", "THREADPOOL", "EVENT_LOOP"),
    "GC": ("GC",),
    "RESIDUAL": ("RESIDUAL_UNATTRIBUTED",),
}


def _sorted_levels(by_level: dict[str, Any]) -> list[dict[str, Any]]:
    return [by_level[k] for k in sorted(by_level, key=lambda k: int(k))]


def _median(row: dict[str, Any], key: str) -> float | None:
    val = row.get(key)
    if isinstance(val, dict):
        return val.get("median")
    return val


def _category_share_pct(row: dict[str, Any], cats: tuple[str, ...]) -> float:
    """Bucket share of host CPU (%) from artifact category medians."""
    host_ms = _median(row, "batch_host_cpu_ms") or 0.0
    if host_ms <= 0:
        return 0.0
    cat_ms = row.get("category_cpu_ms") or {}
    total = 0.0
    for cat in cats:
        entry = cat_ms.get(cat)
        if isinstance(entry, dict):
            total += entry.get("median", 0.0)
        elif entry:
            total += entry
    return 100.0 * total / host_ms


def _n_label(row: dict[str, Any]) -> str:
    n = row.get("n_seeds", 0)
    return f"c={row['level']}\n(n={n}{'!' if n == 1 else ''})"


def fig_f1(rows: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    levels = [r["level"] for r in rows]
    shares: dict[str, list[float]] = {b: [] for b in F1_BUCKETS}
    other: list[float] = []
    for r in rows:
        booked = 0.0
        for bucket, cats in F1_BUCKETS.items():
            pct = _category_share_pct(r, cats)
            shares[bucket].append(pct)
            booked += pct
        other.append(max(0.0, 100.0 - booked))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bottom = [0.0] * len(levels)
    x = range(len(levels))
    for bucket in list(F1_BUCKETS) + ["other/untagged"]:
        vals = other if bucket == "other/untagged" else shares[bucket]
        ax.bar(x, vals, bottom=bottom, label=bucket, width=0.65)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(x))
    ax.set_xticklabels([_n_label(r) for r in rows])
    ax.set_ylabel("share of batch host CPU (%)")
    ax.set_title("F1: category share of host CPU vs concurrency level")
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    p1 = out_dir / "f1_category_share_vs_c.png"
    fig.savefig(p1, dpi=150)
    plt.close(fig)

    # Companion: absolute category CPU ms per host wall second vs c.
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for bucket, cats in F1_BUCKETS.items():
        ys = []
        for r in rows:
            wall_s = _median(r, "batch_wall_s") or 0.0
            host_ms = _median(r, "batch_host_cpu_ms") or 0.0
            pct = _category_share_pct(r, cats)
            abs_ms = host_ms * pct / 100.0
            ys.append(abs_ms / wall_s if wall_s > 0 else 0.0)
        ax.plot(levels, ys, marker="o", label=bucket)
    ax.set_xscale("log")
    ax.set_xticks(levels)
    ax.set_xticklabels([str(v) for v in levels])
    ax.set_xlabel("concurrency level c (sessions = workers)")
    ax.set_ylabel("category CPU ms per host wall second")
    ax.set_title("F1 companion: absolute category CPU per wall second vs c")
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    p2 = out_dir / "f1_category_abs_ms_per_wall_s_vs_c.png"
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    return [p1, p2]


def fig_f2(rows: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    pts = [
        (r["level"], _median(r, "orch_dispatch_us_per_decision"))
        for r in rows
        if _median(r, "orch_dispatch_us_per_decision") is not None
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    if pts:
        ax.plot(
            [p[0] for p in pts],
            [p[1] for p in pts],
            marker="o",
            label="sweep (ORCH_DISPATCH cpu_ns / booked dispatch regions)",
        )
    # Optional overlay: legacy trace-based dispatch cost points. Expected
    # format: [{"c": int, "us_per_decision": float, "label": str?}, ...].
    if LEGACY_DISPATCH_POINTS.is_file():
        try:
            legacy = json.loads(LEGACY_DISPATCH_POINTS.read_text(encoding="utf-8"))
            xs = [p["c"] for p in legacy]
            ys = [p["us_per_decision"] for p in legacy]
            ax.scatter(xs, ys, marker="x", color="tab:red", label="legacy trace-based")
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # malformed legacy file: skip overlay silently per spec
    if pts:
        ax.set_xscale("log")
        ax.set_xticks([p[0] for p in pts])
        ax.set_xticklabels([str(p[0]) for p in pts])
    ax.set_xlabel("concurrency level c")
    ax.set_ylabel("us per ORCH_DISPATCH decision")
    ax.set_title("F2: per-decision ORCH_DISPATCH cost vs c")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = out_dir / "f2_dispatch_us_per_decision_vs_c.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return [p]


def fig_f3(
    rows: list[dict[str, Any]],
    capacity: dict[str, Any],
    saturation: dict[str, Any] | None,
    out_dir: Path,
) -> list[Path]:
    pts = [
        (r["level"], _median(r, "throughput_sessions_per_min"))
        for r in rows
        if _median(r, "throughput_sessions_per_min") is not None
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    if pts:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o")
        ax.set_xscale("log")
        ax.set_xticks([p[0] for p in pts])
        ax.set_xticklabels([str(p[0]) for p in pts])
    n_max = capacity.get("n_max_measured")
    if n_max:
        ax.axvline(n_max, color="tab:green", linestyle="--", alpha=0.7)
        label = f"N_max = {n_max}"
        k_s = capacity.get("k_strict")
        k_b = capacity.get("k_broad")
        if k_s:
            label += f"\nk_strict = {k_s:.2f}"
        if k_b:
            label += f"\nk_broad = {k_b:.2f}"
        ax.annotate(
            label,
            xy=(n_max, ax.get_ylim()[1]),
            xytext=(5, -10),
            textcoords="offset points",
            va="top",
            fontsize=9,
            color="tab:green",
        )
    if saturation:
        ax.axvline(saturation["level"], color="tab:red", linestyle=":", alpha=0.7)
        ax.annotate(
            f"saturation at c={saturation['level']}",
            xy=(saturation["level"], ax.get_ylim()[0]),
            xytext=(5, 10),
            textcoords="offset points",
            fontsize=9,
            color="tab:red",
        )
    ax.set_xlabel("concurrency level c")
    ax.set_ylabel("throughput (sessions/min)")
    ax.set_title("F3: throughput vs c (N_max, k annotated)")
    fig.tight_layout()
    p = out_dir / "f3_throughput_vs_c.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return [p]


def fig_f4(rows: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    pts = [
        (r["level"], _median(r, "turn_transition_p99_ms"), _median(r, "turn_transition_p50_ms"))
        for r in rows
        if _median(r, "turn_transition_p99_ms") is not None
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    if pts:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label="p99")
        if any(p[2] is not None for p in pts):
            ax.plot(
                [p[0] for p in pts],
                [p[2] for p in pts],
                marker="s",
                linestyle="--",
                label="p50",
            )
        ax.set_xscale("log")
        ax.set_xticks([p[0] for p in pts])
        ax.set_xticklabels([str(p[0]) for p in pts])
        ax.legend(fontsize=8)
    else:
        ax.text(
            0.5,
            0.5,
            "no turn-transition latency data\n(anchor lacks per-turn timestamps)",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
    ax.set_xlabel("concurrency level c")
    ax.set_ylabel("turn-transition latency (ms)")
    ax.set_title("F4: turn-transition latency vs c")
    fig.tight_layout()
    p = out_dir / "f4_turn_transition_p99_vs_c.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return [p]


def fig_f5(rows: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    levels = [r["level"] for r in rows]
    gc = [_median(r, "gc_ms_per_session") for r in rows]
    res = [_median(r, "residual_provenance_ms_per_session") for r in rows]
    # The anchor row has no per-session gc/residual medians; fall back to the
    # artifact category medians divided by sessions when available.
    for i, r in enumerate(rows):
        sessions = r.get("sessions_per_batch") or r.get("level") or 1
        if gc[i] is None:
            entry = (r.get("category_cpu_ms") or {}).get("GC")
            if isinstance(entry, dict):
                gc[i] = entry.get("median", 0.0) / sessions
        if res[i] is None:
            entry = (r.get("category_cpu_ms") or {}).get("RESIDUAL_UNATTRIBUTED")
            if isinstance(entry, dict):
                res[i] = entry.get("median", 0.0) / sessions

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(levels, [v if v is not None else float("nan") for v in gc], marker="o", label="GC ms/session")
    ax.plot(levels, [v if v is not None else float("nan") for v in res], marker="s", label="residual ms/session")
    ax.set_xscale("log")
    ax.set_xticks(levels)
    ax.set_xticklabels([str(v) for v in levels])
    ax.set_xlabel("concurrency level c")
    ax.set_ylabel("CPU ms per session")
    ax.set_title("F5: GC and residual per session vs c")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = out_dir / "f5_gc_residual_per_session_vs_c.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return [p]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, dest="out_dir")
    args = parser.parse_args()

    combined = json.loads(args.artifact.read_text(encoding="utf-8"))
    if combined.get("mode") != "levels" or "by_level" not in combined:
        raise SystemExit(
            "sweep_figures requires a levels-mode artifact (run the sweep with --levels)"
        )
    rows = _sorted_levels(combined["by_level"])
    capacity = combined.get("capacity") or {}
    saturation = combined.get("saturation")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    written += fig_f1(rows, args.out_dir)
    written += fig_f2(rows, args.out_dir)
    written += fig_f3(rows, capacity, saturation, args.out_dir)
    written += fig_f4(rows, args.out_dir)
    written += fig_f5(rows, args.out_dir)

    validity = combined.get("result_validity")
    print(f"artifact: {args.artifact} (validity: {validity})")
    for p in written:
        print(f"wrote: {p}")


if __name__ == "__main__":
    main()
