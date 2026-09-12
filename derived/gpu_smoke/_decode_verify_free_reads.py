"""Free-read extract: text_heads + ladder(8tok) vs smoke(64tok) bias. Diagnostic only."""
from __future__ import annotations

import json
import statistics as stats
from collections import defaultdict
from pathlib import Path

root = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel")
targets = [12000, 20000, 32000, 36000]
overlap_ns = [2000, 12000]


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def summarize(vals):
    if not vals:
        return None
    m = mean(vals)
    if len(vals) > 1:
        sd = stats.stdev(vals)
        cv = sd / m if m else None
    else:
        sd = 0.0
        cv = 0.0
    return {"mean": m, "stdev": sd, "cv": cv, "n": len(vals), "vals": vals}


def find_text_head(obj):
    if isinstance(obj, dict):
        if "text_head" in obj and isinstance(obj["text_head"], str):
            return obj["text_head"]
        for v in obj.values():
            r = find_text_head(v)
            if r is not None:
                return r
    return None


def decode_from_gen(g: dict):
    if not isinstance(g, dict):
        return None
    if g.get("decode_tok_s") is not None:
        return g["decode_tok_s"]
    return g.get("r_decode_tok_s")


def prefill_from_gen(g: dict):
    if not isinstance(g, dict):
        return None
    if g.get("prefill_s") is not None:
        return g["prefill_s"]
    if g.get("ttft_ns") is not None:
        return g["ttft_ns"] / 1e9
    # fallback from rate
    n = g.get("prompt_tokens_reported")
    r = g.get("r_prefill_tok_s")
    if n and r:
        return n / r
    return None


def load_ladder_from_repeats(run_id: str, arm: str, ns: list[int]):
    path = root / "raw" / run_id / "repeats.ndjson"
    by_n: dict[int, list] = defaultdict(list)
    want = set(ns)
    with path.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            if o.get("arm_id") and o.get("arm_id") != arm:
                continue
            n = o.get("n_tokens")
            rep = o.get("repeat_index")
            if n not in want:
                continue
            child = ((o.get("result") or {}).get("child") or {})
            g = child.get("generation") or {}
            by_n[n].append(
                {
                    "rep": rep,
                    "text_head": g.get("text_head"),
                    "decode_tok_s": decode_from_gen(g),
                    "prefill_s": prefill_from_gen(g),
                    "completion_tokens_reported": g.get("completion_tokens_reported"),
                    "prompt_tokens_reported": g.get("prompt_tokens_reported"),
                    "admissible": o.get("admissible"),
                    "label": (o.get("envelope") or {}).get("label"),
                    "metric_source": (
                        "decode_tok_s"
                        if g.get("decode_tok_s") is not None
                        else "r_decode_tok_s"
                        if g.get("r_decode_tok_s") is not None
                        else None
                    ),
                }
            )
    return by_n


def load_ladder_from_child_results(session: str, arm_prefix: str, ns: list[int]):
    """Fallback/verify via work/*.result.json; prefer a0 only; dedupe by rep."""
    work = root / "derived" / "ceiling_a" / session / "work"
    by_n: dict[int, list] = defaultdict(list)
    for n in ns:
        paths = sorted(work.glob(f"{arm_prefix}.n{n}.ladder.r*.a0.result.json"))
        seen = set()
        for p in paths:
            name = p.name
            rep = None
            for part in name.split("."):
                if part.startswith("r") and part[1:].isdigit():
                    rep = int(part[1:])
            if rep in seen:
                continue
            seen.add(rep)
            o = json.loads(p.read_text(encoding="utf-8"))
            g = o.get("generation") or {}
            by_n[n].append(
                {
                    "rep": rep,
                    "path": str(p),
                    "text_head": g.get("text_head"),
                    "decode_tok_s": decode_from_gen(g),
                    "prefill_s": prefill_from_gen(g),
                    "completion_tokens_reported": g.get("completion_tokens_reported"),
                    "prompt_tokens_reported": g.get("prompt_tokens_reported"),
                    "metric_source": (
                        "decode_tok_s"
                        if g.get("decode_tok_s") is not None
                        else "r_decode_tok_s"
                        if g.get("r_decode_tok_s") is not None
                        else None
                    ),
                }
            )
    return by_n


print("=" * 72)
print("1a. VERBATIM text_head")
print("=" * 72)

# Prefer child results for verbatim text_head; repeats for metrics consistency
child_A = load_ladder_from_child_results(
    "ad7b9288-42e6-42e8-be3e-ad1a1b1abc4c", "A", targets
)
child_G = load_ladder_from_child_results(
    "2804d7fa-d9d1-4d76-b376-48104d47b607", "gpu_only", targets
)
ladder_A = load_ladder_from_repeats(
    "b5ce21e5-9f29-46f4-8319-f74adcdeb628", "A", overlap_ns + targets
)
ladder_G = load_ladder_from_repeats(
    "693b44d2-8234-453c-bc8d-107a9ff259a0", "gpu_only", overlap_ns + targets
)

text_heads = {"A": {}, "gpu_only": {}}
for arm, data in [("A", child_A), ("gpu_only", child_G)]:
    print(f"\n### arm {arm} ladder child results (8 completion tokens)")
    for n in targets:
        cells = sorted(data.get(n, []), key=lambda x: (x["rep"] is None, x["rep"]))
        if not cells:
            print(f"n={n}: MISSING")
            text_heads[arm][n] = None
            continue
        text_heads[arm][n] = [
            {"rep": c["rep"], "text_head": c["text_head"]} for c in cells
        ]
        for c in cells:
            print(f"n={n} r{c['rep']}: {c['text_head']!r}")

print("\n### smoke text_head n=12000 (64 tok) — matrix_partial_39a8a0f5")
smoke_cells_dir = (
    root / "derived/gpu_smoke/matrix_partial_39a8a0f5-1a59-46e5-8f7e-80ccf0943aec/cells"
)
smoke_text = []
for p in sorted(smoke_cells_dir.glob("*n12000*.json")):
    o = json.loads(p.read_text(encoding="utf-8"))
    th = find_text_head(o)
    arm = o.get("arm_id") or (
        "A" if "armA" in p.name else "gpu_only" if "armgpu_only" in p.name else "?"
    )
    smoke_text.append(
        {
            "file": p.name,
            "arm": arm,
            "decode_tok_s": o.get("decode_tok_s"),
            "prefill_s": o.get("prefill_s"),
            "text_head": th,
        }
    )
    print(f"{p.name}: arm={arm}")
    print(f"  text_head={th!r}")

print("\nSmoke n=20000/32000/36000: MISSING (no cells in matrix_partial or loose artifacts)")

print("\n" + "=" * 72)
print("1b. CROSS-TOOL PAIRS (ladder 8-tok vs smoke 64-tok)")
print("=" * 72)

smoke_sum = json.loads(
    (
        root
        / "derived/gpu_smoke/matrix_partial_39a8a0f5-1a59-46e5-8f7e-80ccf0943aec/summary.json"
    ).read_text(encoding="utf-8")
)
smoke_by: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
for c in smoke_sum["cells"]:
    smoke_by[c["arm_id"]][c["n_tokens"]].append(c)

print("\nLadder n (from repeats.ndjson):")
for arm, L in [("A", ladder_A), ("gpu_only", ladder_G)]:
    print(arm, {k: len(v) for k, v in sorted(L.items())})
print("Smoke n:", {arm: {k: len(v) for k, v in sorted(d.items())} for arm, d in smoke_by.items()})

rows = []
for arm in ["A", "gpu_only"]:
    L = ladder_A if arm == "A" else ladder_G
    for n in sorted(set(L.keys()) & set(smoke_by[arm].keys())):
        l_pref = [x["prefill_s"] for x in L[n] if x["prefill_s"] is not None]
        l_dec = [x["decode_tok_s"] for x in L[n] if x["decode_tok_s"] is not None]
        s_pref = [x["prefill_s"] for x in smoke_by[arm][n] if x.get("prefill_s") is not None]
        s_dec = [x["decode_tok_s"] for x in smoke_by[arm][n] if x.get("decode_tok_s") is not None]
        lp, ld, sp, sd_ = map(summarize, [l_pref, l_dec, s_pref, s_dec])
        decode_LS = (ld["mean"] / sd_["mean"]) if ld and sd_ and sd_["mean"] else None
        decode_SL = (sd_["mean"] / ld["mean"]) if ld and sd_ and ld["mean"] else None
        prefill_LS = (lp["mean"] / sp["mean"]) if lp and sp and sp["mean"] else None
        src = sorted({x.get("metric_source") for x in L[n] if x.get("metric_source")})
        rows.append(
            {
                "arm": arm,
                "n": n,
                "ladder_metric_source": src,
                "ladder_prefill_mean": lp["mean"] if lp else None,
                "smoke_prefill_mean": sp["mean"] if sp else None,
                "prefill_L_over_S": prefill_LS,
                "ladder_decode_mean": ld["mean"] if ld else None,
                "smoke_decode_mean": sd_["mean"] if sd_ else None,
                "decode_L_over_S": decode_LS,
                "decode_S_over_L": decode_SL,
                "ladder_decode_vals": ld["vals"] if ld else None,
                "smoke_decode_vals": sd_["vals"] if sd_ else None,
                "ladder_prefill_vals": lp["vals"] if lp else None,
                "smoke_prefill_vals": sp["vals"] if sp else None,
                "ladder_decode_cv": ld["cv"] if ld else None,
                "smoke_decode_cv": sd_["cv"] if sd_ else None,
            }
        )

print("\nCross-tool table (means):")
print(
    f"{'arm':10} {'n':>6} {'L_pref':>10} {'S_pref':>10} {'L/S_p':>8} "
    f"{'L_dec':>10} {'S_dec':>10} {'L/S_d':>8} {'S/L_d':>8}  src"
)
for r in rows:
    print(
        f"{r['arm']:10} {r['n']:6d} "
        f"{r['ladder_prefill_mean']:10.4f} {r['smoke_prefill_mean']:10.4f} {r['prefill_L_over_S']:8.4f} "
        f"{r['ladder_decode_mean']:10.4f} {r['smoke_decode_mean']:10.4f} "
        f"{r['decode_L_over_S']:8.4f} {r['decode_S_over_L']:8.4f}  {r['ladder_metric_source']}"
    )
    print(f"           L_dec vals={r['ladder_decode_vals']}")
    print(f"           S_dec vals={r['smoke_decode_vals']}")

print("\nPer-arm decode bias smoke/ladder (64tok / 8tok) — correction if stable:")
bias_stable = True
for arm in ["A", "gpu_only"]:
    arm_rows = [r for r in rows if r["arm"] == arm]
    biases = [(r["n"], r["decode_S_over_L"]) for r in arm_rows]
    print(f"  {arm}: {biases}")
    if len(biases) >= 2:
        vals = [b for _, b in biases]
        rel = (max(vals) - min(vals)) / mean(vals)
        print(f"    range {min(vals):.4f}..{max(vals):.4f}  relative_spread={rel:.2%}")
        if rel > 0.15:
            bias_stable = False
            print(f"    UNSTABLE with n (>{15}% relative spread)")

# When does ladder A decode become unusable? Look at absolute decode and ratio vs smoke trend
print("\nLadder-only decode trajectory (targets):")
ladder_only = {}
for arm, L in [("A", ladder_A), ("gpu_only", ladder_G)]:
    ladder_only[arm] = {}
    for n in targets:
        vals = [x["decode_tok_s"] for x in L.get(n, []) if x["decode_tok_s"] is not None]
        prefs = [x["prefill_s"] for x in L.get(n, []) if x["prefill_s"] is not None]
        if vals:
            s = summarize(vals)
            ladder_only[arm][n] = {
                "decode_mean": s["mean"],
                "decode_cv": s["cv"],
                "decode_vals": vals,
                "prefill_mean": mean(prefs),
            }
            print(
                f"  {arm} n={n}: decode mean={s['mean']:.4f} CV={s['cv']:.3f} "
                f"vals={[round(v,4) for v in vals]} prefill_mean={mean(prefs):.2f}s"
            )
        else:
            ladder_only[arm][n] = None
            print(f"  {arm} n={n}: MISSING")

A20 = [x["decode_tok_s"] for x in ladder_A[20000] if x["decode_tok_s"] is not None]
G20 = [x["decode_tok_s"] for x in ladder_G[20000] if x["decode_tok_s"] is not None]
A12 = [x["decode_tok_s"] for x in ladder_A[12000] if x["decode_tok_s"] is not None]
G12 = [x["decode_tok_s"] for x in ladder_G[12000] if x["decode_tok_s"] is not None]
sA12 = [x["decode_tok_s"] for x in smoke_by["A"][12000]]
sG12 = [x["decode_tok_s"] for x in smoke_by["gpu_only"][12000]]
sA2 = [x["decode_tok_s"] for x in smoke_by["A"][2000]]
sG2 = [x["decode_tok_s"] for x in smoke_by["gpu_only"][2000]]

print("\nRatios decode_tok_s gpu_only:A (speedup convention):")
print(f"  ladder @2000  : {mean([x['decode_tok_s'] for x in ladder_G[2000]])/mean([x['decode_tok_s'] for x in ladder_A[2000]]):.4f}")
print(f"  smoke  @2000  : {mean(sG2)/mean(sA2):.4f}")
print(f"  ladder @12000 : {mean(G12)/mean(A12):.4f}")
print(f"  smoke  @12000 : {mean(sG12)/mean(sA12):.4f}")
print(f"  ladder @20000 : {mean(G20)/mean(A20):.4f}  (A ladder decode collapsed)")

# Usability threshold: arm A ladder decode drops >3x from n=2000 baseline or below 2 tok/s
A2 = [x["decode_tok_s"] for x in ladder_A[2000]]
print("\nLadder A decode usability:")
for n in sorted(ladder_A):
    vals = [x["decode_tok_s"] for x in ladder_A[n] if x["decode_tok_s"] is not None]
    if not vals:
        continue
    m = mean(vals)
    ratio_to_2k = m / mean(A2)
    flag = ""
    if m < 2.0 or ratio_to_2k < 1 / 3:
        flag = "  <-- UNUSABLE vs 8-tok ladder baseline"
    print(f"  n={n}: mean={m:.4f} vs_n2000={ratio_to_2k:.3f}{flag}")

out = {
    "text_heads_ladder": text_heads,
    "text_heads_smoke_n12000": smoke_text,
    "cross_tool_rows": rows,
    "ladder_only_targets": ladder_only,
    "bias_stable_smoke_over_ladder": bias_stable,
    "ratios_gpu_only_over_A": {
        "ladder_n2000": mean([x["decode_tok_s"] for x in ladder_G[2000]])
        / mean([x["decode_tok_s"] for x in ladder_A[2000]]),
        "smoke_n2000": mean(sG2) / mean(sA2),
        "ladder_n12000": mean(G12) / mean(A12),
        "smoke_n12000": mean(sG12) / mean(sA12),
        "ladder_n20000": mean(G20) / mean(A20),
    },
    "note": (
        "ladder completion_tokens=8; smoke -N uses max_new_tokens=64. "
        "Arm A ladder metrics are r_decode_tok_s (decode_tok_s absent). "
        "gpu_only has decode_tok_s==r_decode_tok_s."
    ),
    "remeasure_status": "BLOCKED_ON_OPERATOR",
    "blockers": ["Cursor resident", "Chrome resident", "not in SSH session for measurement"],
}
out_path = root / "derived/gpu_smoke/_decode_verify_free_reads.json"
out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"\nWrote {out_path}")
print(f"bias_stable={bias_stable}")
