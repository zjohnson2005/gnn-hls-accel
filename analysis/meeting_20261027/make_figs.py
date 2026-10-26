"""Tue Oct 27 meeting pack figures (Task BK). Reads only analysis/cc_20261026/*.json (sealed-record
extracts with run_ids), analysis/demo1/SCORE_V1V2_XPS_20261014.json, analysis/demo2_heldout/F2_T2S.json
and the committed prediction files. Writes PNG + PDF + a manifest (sha256 of every input) per figure
into analysis/meeting_20261027/figs/. Palette: reference categorical slots 1-4 in fixed order
(f16 blue, i8 orange, u4 aqua, other yellow); every series also has its own marker and label.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from tools import br_predict as br  # noqa: E402

OUT = Path(__file__).resolve().parent / "figs"
CC = ROOT / "analysis" / "cc_20261026"
COL = {"f16": "#2a78d6", "i8": "#eb6834", "u4": "#1baf7a", "other": "#eda100", "ink": "#333333"}
MARK = {"f16": "o", "i8": "s", "u4": "^"}
GRAY = "#9a9a9a"
plt.rcParams.update(
    {
        "font.size": 8,
        "figure.dpi": 160,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e6e6e6",
        "grid.linewidth": 0.6,
        "axes.edgecolor": "#888888",
    }
)


class Inp:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def json(self, p: Path) -> Any:
        self.paths.append(p)
        return json.loads(p.read_text(encoding="utf-8"))


def save(fig: Any, name: str, inp: Inp, notes: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    man = {
        "figure": name,
        "script": "analysis/meeting_20261027/make_figs.py",
        "inputs_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inp.paths
        },
        "notes": notes,
    }
    (OUT / f"{name}.manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="ascii")
    plt.close(fig)


def fig1_where_bytes_go() -> None:
    inp = Inp()
    by = inp.json(CC / "bytes.json")
    rows = []
    for host, n, cells in (
        (
            "XPS 16 GB",
            12288,
            [
                ("f16", "unl", "xps:bytes_f16_unl"),
                ("f16", "c256", "xps:bytes_f16_c256"),
                ("i8", "unl", "xps:bytes_8_unl"),
                ("i8", "c256", "xps:bytes_8_c256"),
                ("u4", "unl", "xps:bytes_u4_unl"),
                ("u4", "c256", "xps:bytes_u4_c256"),
            ],
        ),
        (
            "T2S 64 GB",
            24576,
            [
                ("f16", "unl", "t2s:slope_f16_unl"),
                ("f16", "c256", "t2s:slope_f16_c256"),
                ("i8", "unl", "t2s:slope_8_unl"),
                ("i8", "c256", "t2s:slope_8_c256"),
                ("u4", "unl", "t2s:slope_u4_unl"),
                ("u4", "c256", "t2s:slope_u4_c256"),
            ],
        ),
    ):
        for prec, cap, key in cells:
            v = by[key]
            p = next(q for q in v["points"] if q["n"] == n)
            rows.append(
                (
                    host,
                    prec,
                    cap,
                    n,
                    v["run_id"],
                    p["W_usm_host"] / 2**30,
                    p["kv_pool_cl_mem"] / 2**30,
                    (p["usm_device_after_turn1"] or 0) / 2**30,
                )
            )
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    xs = list(range(len(rows)))
    w = [r[5] for r in rows]
    kv = [r[6] for r in rows]
    ot = [r[7] for r in rows]
    ax.bar(xs, w, color=GRAY, width=0.7, label="weights (usm_host)", edgecolor="white", linewidth=1)
    ax.bar(
        xs,
        kv,
        bottom=w,
        color=[COL[r[1]] for r in rows],
        width=0.7,
        label="KV pool (cl_mem)",
        edgecolor="white",
        linewidth=1,
    )
    ax.bar(
        xs,
        ot,
        bottom=[a + b for a, b in zip(w, kv, strict=True)],
        color=COL["other"],
        width=0.7,
        hatch="///",
        edgecolor="white",
        linewidth=1,
        label="prefill working set (usm_device)",
    )
    ax.set_xticks(xs, [f"{r[1]}\n{r[2]}\n{r[4]}" for r in rows], fontsize=6)
    ax.axvline(5.5, color="#bbbbbb", lw=0.8)
    ax.text(
        2.5,
        max(a + b + c for a, b, c in zip(w, kv, ot, strict=True)) * 1.02,
        "XPS, n = 12,288",
        ha="center",
    )
    ax.text(
        8.5,
        max(a + b + c for a, b, c in zip(w, kv, ot, strict=True)) * 1.02,
        "T2S, n = 24,576",
        ha="center",
    )
    ax.set_ylabel("GPU memory after turn 1 (GiB)")
    ax.legend(fontsize=6, loc="upper left", frameon=False)
    ax.set_title(
        "Where context bytes go: KV pool = n x compiled k exactly; the prefill working set "
        "(87 kB/token) is the non-KV term and vanishes at cap 256",
        fontsize=7,
    )
    save(
        fig,
        "fig1_where_bytes_go",
        inp,
        [
            "GPU_MEMORY_STATISTICS after turn 1 per type (child records, sealed points)",
            "settled KV slopes f16 147,456 / i8 84,096 / u4 47,232 B/token on both hosts (analysis/cc_20261026/bytes.json)",
            "T2S slope_f16_unl b4a96d44 reached the Mac although its cells.txt line was never written (park failed; queue relaunched)",
        ],
    )


def fig2_context_vs_kv() -> None:
    inp = Inp()
    m = inp.json(CC / "measured.json")
    lim = m["xps_limits"]
    b = br.b_br()
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2), sharey=True)
    ax = axes[0]
    for i, p in enumerate(("f16", "i8", "u4")):
        for j, c in enumerate(("unl", "c1024", "c256")):
            v = lim[f"{p}_{c}"]
            x = i + (j - 1) * 0.22
            ax.scatter(
                [x],
                [v["L_star"]],
                color=COL[p],
                marker=MARK[p],
                s=30,
                zorder=5,
                edgecolor="white",
                linewidth=0.8,
            )
            ax.annotate(
                f"{c} {v['L_star'] // 1000}K",
                (x, v["L_star"]),
                fontsize=5,
                xytext=(0, 5 + 7 * j),
                textcoords="offset points",
                ha="center",
            )
        k = br.K_COMPILED[p]
        ax.hlines(b / (k + br.A), i - 0.35, i + 0.35, color=COL[p], lw=1, ls="--")
        ax.hlines((b - 256 * br.A) / k, i - 0.35, i + 0.35, color=COL[p], lw=1, ls=":")
    for rid, p, v in (
        ("553b3a5c", "f16", 15000),
        ("cf3555d5", "i8", 20000),
        ("e4a22dac", "u4", 26500),
    ):
        i = ("f16", "i8", "u4").index(p)
        ax.scatter([i - 0.42], [v], color=COL[p], marker="x", s=20)
        ax.annotate(
            f"sealed\n{rid}",
            (i - 0.42, v),
            fontsize=4.5,
            xytext=(0, -14),
            textcoords="offset points",
            ha="center",
        )
    ax.axhline(40960, color=COL["ink"], lw=0.8)
    ax.text(2.6, 37500, "window 40,960:\nabove = capacity probe", fontsize=5.5, ha="right")
    ax.set_xticks([0, 1, 2], ["f16", "i8 (8-bit)", "u4"])
    ax.set_ylabel("registered L* (largest held, tokens)")
    ax.set_title(
        "XPS 16 GB: u4/f16 1.79x unchunked, 3.18x at cap 256\n(byte ratio 3.12x compiled, 3.56x nominal)\n"
        "dashed / dotted = law unchunked / cap 256 (DERIVED)",
        fontsize=6.5,
    )
    ax2 = axes[1]
    for i, (p, rid) in enumerate((("f16", "7e249f7e"), ("i8", "6dfd1a12"), ("u4", "2d329db2"))):
        ax2.scatter([i], [40448], color=COL[p], marker=MARK[p], s=30, zorder=5)
        ax2.annotate(
            f"3/3 held\n{rid}",
            (i, 40448),
            fontsize=5.5,
            xytext=(0, -18),
            textcoords="offset points",
            ha="center",
        )
        k = br.K_COMPILED[p]
        mem = 43.0 * 2**30 / (k + br.A)
        ax2.annotate(
            f"memory ~{mem / 1000:.0f}K\n(DERIVED)",
            (i, 40448),
            fontsize=5.5,
            xytext=(0, 22),
            textcoords="offset points",
            ha="center",
            color="#555555",
        )
    ax2.axhline(40960, color=COL["ink"], lw=0.8)
    ax2.set_xticks([0, 1, 2], ["f16", "i8", "u4"])
    ax2.set_ylim(0, 115000)
    ax2.set_title(
        "T2S 64 GB: the window binds\n(40,448 held 3/3 in every arm;\nmemory ceiling far above, BL A11)",
        fontsize=6.5,
    )
    fig.tight_layout()
    save(
        fig,
        "fig2_context_vs_kv",
        inp,
        [
            "L* from sealed bisections: f16 unl aa914c4c, c1024 b48e4cfe, c256 d782cf80; i8 unl fd074be1, c1024 3e45f554, c256 1e9671a0; u4 unl 5943c992, c1024 f7542f68, c256 f8df3847",
            "robust ceilings (ADDENDUM 1) in analysis/cc_20261026/measured.json repeats",
        ],
    )


def fig3_cliff_ttft() -> None:
    inp = Inp()
    m = inp.json(CC / "measured.json")
    tt = m["ttft_cells"]
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    for lab, name, mk, col in (
        ("ttft_u4_unlx", "unchunked", "^", COL["u4"]),
        ("ttft_u4_c1024", "cap 1024", "s", COL["i8"]),
        ("ttft_u4_c256", "cap 256", "o", COL["f16"]),
    ):
        d = tt[lab]["median_turn1_s"]
        xs = [int(x) for x in d]
        ax.plot(
            xs,
            [d[x] for x in d],
            marker=mk,
            color=col,
            lw=1.5,
            ms=5,
            label=f"u4 {name} ({tt[lab]['run_id']})",
        )
    g = m["grow"]
    for lab, col, mk in (("grow_u4_unl", COL["u4"], "v"), ("grow_f16_unl", COL["f16"], "D")):
        a = g[lab]["a23_turns_[L_hist,delta,ttft_s,pred_s]"]
        ax.plot(
            [r[0] for r in a],
            [r[2] for r in a],
            color=col,
            lw=0.8,
            ls="--",
            marker=mk,
            ms=2.5,
            label=f"{g[lab]['arm']} session, 2K turns, per-turn TTFT vs history ({g[lab]['run_id']})",
        )
        ax.plot(
            [r[0] for r in a],
            [r[3] for r in a],
            color=col,
            lw=0.6,
            ls=":",
            label="A23 registered per-turn law (same series)",
        )
    al = m["A24_ttft_law"]
    ax.axhline(20, color=GRAY, lw=0.8)
    ax.text(
        70000, 21, f"20 s: L_TTFT {al['L_TTFT']['20s']:,} (pred 16,729)", fontsize=5.5, ha="right"
    )
    ax.set_xlabel("tokens (prefill n, or session history)")
    ax.set_ylabel("TTFT (s)")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=5, frameon=False, loc="upper left")
    ax.set_title(
        "TTFT once memory is solved: cap 256 doubles cold TTFT at 16K (+112%, A8 MISS);\n"
        "session turns at ~60K take ~53 s (u4) - the TTFT roof",
        fontsize=6.5,
    )
    save(
        fig,
        "fig3_cliff_ttft",
        inp,
        [
            "cliff_f16 83a3c422: 12,000 held, 13,500-22,500 all failed loudly in turn 1; cliff_u4 36e0ec24 NOT RUN (quiescence)"
        ],
    )


def fig4_router_flip() -> None:
    inp = Inp()
    d = inp.json(ROOT / "analysis" / "demo1" / "SCORE_V1V2_XPS_20261014.json")["cells"]
    v1, v2 = d["V1_xps_gpu_4b_u8"], d["V2_xps_cpu_4b"]
    fig, axes = plt.subplots(1, 3, figsize=(6.4, 2.2))
    for ax, key, lab, fmt in (
        (axes[0], "local_share", "local share", "{:.0%}"),
        (axes[1], "usd_per_task", "$ per task", "${:.3f}"),
        (axes[2], "n_hybrid_pass", "hybrid passes / 30", "{}"),
    ):
        vals = [v1["measured"][key], v2["measured"][key]]
        ax.bar([0, 1], vals, color=[COL["f16"], COL["i8"]], width=0.6, edgecolor="white")
        for x, val in zip([0, 1], vals, strict=True):
            ax.text(x, val, fmt.format(val), ha="center", va="bottom", fontsize=6)
        ax.set_xticks([0, 1], ["GPU (V1)\nf7343708", "CPU (V2)\n1acc8c58"], fontsize=5.5)
        ax.set_title(lab, fontsize=7)
        ax.grid(False)
    fig.suptitle(
        "DEMO-1 existence proof (n = 30, one laptop, same model/tasks/router): placement flips the router",
        fontsize=7,
        y=1.06,
    )
    fig.tight_layout()
    save(
        fig,
        "fig4_router_flip",
        inp,
        ["V2 $/task 0.297 MISSED its band 0.320-0.347 (registered); V1 MATCH x3"],
    )


def fig5_demo2_t2s() -> None:
    inp = Inp()
    f2 = inp.json(ROOT / "analysis" / "demo2_heldout" / "F2_T2S.json")
    pr = inp.json(ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_BH_F2_PREDICTIONS.json")[
        "predictions"
    ]["T2S"]
    fig, ax = plt.subplots(figsize=(5.4, 2.6))
    rows = []
    for con in ("A vs P", "A vs C"):
        for met in ("b_wall", "c_time_to_failure"):
            c = f2["contrasts"][con][met]
            p = pr[con][met]
            rows.append(
                (
                    f"{con}: {met}",
                    c["median_paired_diff_s"],
                    p["band_p05"],
                    p["band_p95"],
                    c["p_holm"],
                    c["rejects_holm_0.05"],
                )
            )
    for i, (_lab, val, lo, hi, ph, rej) in enumerate(rows):
        ax.hlines(i, lo, hi, color=GRAY, lw=4, alpha=0.6)
        ax.scatter([val], [i], color=COL["f16"] if rej else COL["i8"], zorder=5, s=25)
        ax.text(val - 0.6, i + 0.25, f"{val:+.2f} s, Holm p {ph:.1g}", fontsize=5.5, ha="right")
    ax.axvline(0, color=COL["ink"], lw=0.6)
    ax.set_xlim(-37, 3)
    ax.set_ylim(-0.5, len(rows) - 0.3)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=6)
    ax.set_xlabel(
        "median paired difference A - X (s); negative = A faster (gray = registered 5-95% band)"
    )
    ax.set_title(
        "DEMO-2 T2S held-out, F2 (not gated): the true default A is faster than P (8B INT8) by ~14 s/entry;\n"
        "C = A. The $ primary (P vs A dC_iso) is PENDING: it needs the shared cloud log (XPS, after Oct 27)",
        fontsize=6.5,
    )
    save(fig, "fig5_demo2_t2s", inp, ["run_ids: A 1f13b75e, P 9eb71a3a, C 89676c43 (sealed MATCH)"])


def fig8_granularity() -> None:
    inp = Inp()
    m = inp.json(CC / "measured.json")
    lim, g = m["xps_limits"], m["grow"]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2))
    ax = axes[0]
    b = br.b_br()
    gs = [64 * 2**i for i in range(0, 10)]
    for p in ("f16", "u4"):
        k = br.K_COMPILED[p]
        ax.plot(
            gs,
            [(b - br.A * x) / k for x in gs],
            color=COL[p],
            lw=1,
            ls=":",
            label=f"{p}: (B - a g)/k (single shot, DERIVED)",
        )
        ax.plot(
            [1024, 2048, 4096],
            [br.session_law(p, t) for t in (1024, 2048, 4096)],
            color=COL[p],
            lw=1,
            ls="--",
            label=f"{p}: session law (B - aT)/k - T",
        )
        for c in ("c256", "c1024"):
            v = lim[f"{p}_{c}"]
            ax.scatter([int(c[1:])], [v["L_star"]], color=COL[p], marker=MARK[p], s=25, zorder=5)
        v = lim[f"{p}_unl"]
        ax.scatter(
            [v["L_star"]],
            [v["L_star"]],
            color=COL[p],
            marker=MARK[p],
            s=25,
            zorder=5,
            facecolor="none",
        )
        for t, lab in (
            (1024, f"grow_{p}_unl_d1k"),
            (2048, f"grow_{p}_unl"),
            (4096, f"grow_{p}_unl_d4k"),
        ):
            ax.scatter([t], [g[lab]["last_held_prompt"]], color=COL[p], marker="*", s=40, zorder=6)
    ax.axhline(40960, color=COL["ink"], lw=0.8)
    ax.text(70, 42500, "window 40,960 (above = capacity probe)", fontsize=5.5)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("prefill granularity g (tokens per step: cap, turn size, or the whole prompt)")
    ax.set_ylabel("ceiling (tokens)")
    ax.legend(fontsize=5, frameon=False, loc="upper right")
    ax.set_title(
        "Ceiling vs prefill granularity (XPS)\nfilled = caps, hollow = single shot, stars = sessions\n"
        "(last held turn); lines DERIVED, in-sample B",
        fontsize=6.5,
    )
    ax2 = axes[1]
    pts = [
        ("single shot", lim["u4_unl"]["L_star"] / lim["f16_unl"]["L_star"]),
        ("cap 1024", lim["u4_c1024"]["L_star"] / lim["f16_c1024"]["L_star"]),
        ("cap 256", lim["u4_c256"]["L_star"] / lim["f16_c256"]["L_star"]),
    ]
    for t, a, bb in (
        (1024, "grow_u4_unl_d1k", "grow_f16_unl_d1k"),
        (2048, "grow_u4_unl", "grow_f16_unl"),
        (4096, "grow_u4_unl_d4k", "grow_f16_unl_d4k"),
    ):
        pts.append((f"session {t // 1024}K", g[a]["last_held_prompt"] / g[bb]["last_held_prompt"]))
    ax2.bar(range(len(pts)), [v for _, v in pts], color=COL["u4"], width=0.6, edgecolor="white")
    for i, (_, v) in enumerate(pts):
        ax2.text(i, v, f"{v:.2f}x", ha="center", va="bottom", fontsize=6)
    ax2.axhline(3.122, color=COL["ink"], lw=0.8, ls="--")
    ax2.text(5.4, 3.18, "compiled byte ratio 3.12x", fontsize=5.5, ha="right")
    ax2.axhline(3.556, color=GRAY, lw=0.8, ls=":")
    ax2.text(5.4, 3.6, "nominal 3.56x", fontsize=5.5, ha="right")
    ax2.set_xticks(range(len(pts)), [n for n, _ in pts], fontsize=6, rotation=20)
    ax2.set_ylabel("u4 / f16 ceiling")
    ax2.set_title(
        "KV precision x granularity:\nu4 buys 1.79x unchunked, ~3.2x chunked", fontsize=6.5
    )
    fig.tight_layout()
    save(
        fig,
        "fig8_granularity",
        inp,
        [
            "sessions use last HELD turn lengths (ADDENDUM 5); u4 session points are capacity probes (> 40,960)"
        ],
    )


def fig9_implied_b() -> None:
    inp = Inp()
    m = inp.json(CC / "measured.json")
    r = m["implied_B"]
    rows = sorted(r["cells"], key=lambda c: c["implied_B_bytes"])
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    for i, c in enumerate(rows):
        p = c["arm"]
        ax.scatter([c["implied_B_bytes"] / 1e9], [i], color=COL[p], marker=MARK[p], s=25, zorder=5)
        ax.text(
            c["implied_B_bytes"] / 1e9 + 0.005,
            i,
            f"{p} cap {c['cap']} L {c['largest_held']:,} {c['run_id']}",
            fontsize=5,
            va="center",
        )
    ax.axvline(r["B_BR_bytes"] / 1e9, color=COL["ink"], lw=0.8)
    ax.axvspan(r["B_BR_bytes"] / 1e9 * 0.95, r["B_BR_bytes"] / 1e9 * 1.05, color=GRAY, alpha=0.15)
    ax.set_yticks([])
    ax.set_xlim(3.0, 3.6)
    ax.set_xlabel(
        "implied non-weight budget B = P + k L + a min(L, cap) (GB), compiled k, a 87,520"
    )
    ax.set_title(
        f"One budget, 14 configurations: median {r['B_BR_GB']} GB, spread +-{r['spread_pct']}% "
        "(IN-SAMPLE; band = +-5%)",
        fontsize=6.5,
    )
    save(
        fig,
        "fig9_implied_b",
        inp,
        [
            "IN-SAMPLE: the same cells define B; held-out tests are SESS-1, STAT-1, 8B (registered BR)"
        ],
    )


def fig10_slider() -> None:
    inp = Inp()
    m = inp.json(CC / "measured.json")
    s = m["slider"]
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    for p, col, mk in (("u4", COL["u4"], "^"), ("f16", COL["f16"], "o")):
        xs = [r[0] for r in s[p] if r[1]]
        ys = [r[1] for r in s[p] if r[1]]
        ax.plot(
            xs,
            ys,
            color=col,
            marker=mk,
            lw=1.5,
            label=f"{p} L* ({', '.join(r[2][:8] for r in s[p])})",
        )
    ax.scatter([74], [8000], color=COL["f16"], marker="x", s=30)
    ax.annotate(
        "f16 failed its 8,000 low rung (39d38c85, UNSEALED);\nchild started with 3.5 GB Available",
        (74, 8000),
        fontsize=5.5,
        xytext=(-140, -5),
        textcoords="offset points",
    )
    ax.scatter([57], [25000], color=COL["u4"], marker="^", facecolor="none", s=30)
    ax.annotate(
        "same setting Fri: 25,000 (5943c992)",
        (57, 25000),
        fontsize=5.5,
        xytext=(4, 2),
        textcoords="offset points",
    )
    for pct, adv in ((50, 6.893), (57, 7.920), (74, 10.413)):
        ax.text(pct, 3000, f"adv. {adv} GiB", fontsize=5, ha="center", color="#555555")
    ax.set_xlabel("Intel Shared GPU/NPU Memory Override (% of RAM)")
    ax.set_ylabel("L* (tokens)")
    ax.set_ylim(0, 28000)
    ax.legend(fontsize=5.5, frameon=False, loc="center right")
    ax.set_title(
        "CANDIDATE (gated at Gate A, Nov 4): more GPU share, less context. n = 1 per setting;\n"
        "only 74% lies outside the ~15% session drift. INV-1 (ABAB x4 boots) decides",
        fontsize=6.5,
    )
    save(
        fig,
        "fig10_slider",
        inp,
        [
            "advertised size = 0.94 x SharedSystemMemory - 450 MiB (Intel compute-runtime source; GPU-share plan)"
        ],
    )


def main() -> int:
    for f in (
        fig1_where_bytes_go,
        fig2_context_vs_kv,
        fig3_cliff_ttft,
        fig4_router_flip,
        fig5_demo2_t2s,
        fig8_granularity,
        fig9_implied_b,
        fig10_slider,
    ):
        f()
        print(f.__name__, "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
