"""One-shot writer for H1-3POLICY prediction / SLO / class-C artifacts. Not a live runner."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    r2a = ROOT / "derived/h1_hybrid/slo_escalate_86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3"
    led = json.loads((r2a / "turn_ledger.json").read_text(encoding="utf-8-sig"))["entries"]

    ttft_lim = 10.0
    dec_lim = 6.0
    ctx_lim = 10_000

    def new_trig(t: dict) -> list[str]:
        reasons: list[str] = []
        ttft = t.get("ttft_s")
        dec = t.get("decode_tok_s")
        if ttft is not None and float(ttft) > ttft_lim:
            reasons.append(f"ttft>{ttft_lim}")
        if dec is not None and float(dec) < dec_lim:
            reasons.append(f"decode<{dec_lim}")
        return reasons

    def old_trig(t: dict) -> list[str]:
        reasons = list(new_trig(t))
        if int(t.get("n_ctx") or 0) > ctx_lim:
            reasons.append(f"ctx>{ctx_lim}")
        return reasons

    old_turn = new_turn = old_entry = new_entry = 0
    ctx_only_turns = ctx_only_entries = 0
    max_ctx = n_local = ttft_n = dec_n = ctx_n = 0
    for e in led:
        old_hit = new_hit = ctx_only_hit = False
        on_cloud_old = on_cloud_new = False
        for t in e.get("turns") or []:
            n_local += 1
            ctx = int(t.get("n_ctx") or 0)
            max_ctx = max(max_ctx, ctx)
            o, n = old_trig(t), new_trig(t)
            if any(r.startswith("ctx>") for r in o):
                ctx_n += 1
            if any(r.startswith("ttft") for r in o):
                ttft_n += 1
            if any(r.startswith("decode") for r in o):
                dec_n += 1
            if o and not on_cloud_old:
                old_turn += 1
                old_hit = True
                on_cloud_old = True
                if o and not n:
                    ctx_only_turns += 1
                    ctx_only_hit = True
            if n and not on_cloud_new:
                new_turn += 1
                new_hit = True
                on_cloud_new = True
        if old_hit:
            old_entry += 1
        if new_hit:
            new_entry += 1
        if ctx_only_hit:
            ctx_only_entries += 1

    n_tool_err_turns = n_tool_err_entries = 0
    field_present = False
    for e in led:
        any_err = False
        for t in e.get("turns") or []:
            if "tool_exec_error" in t:
                field_present = True
                if t.get("tool_exec_error"):
                    n_tool_err_turns += 1
                    any_err = True
        if any_err:
            n_tool_err_entries += 1

    analyze = json.loads(
        (ROOT / "derived/h1_hybrid/h1_analyze.json").read_text(encoding="utf-8-sig")
    )
    census = analyze["census_r2a"]

    slo_cmp = {
        "kind": "slo_rule_old_vs_new",
        "run_id": "86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3",
        "old_rule": "ttft_s>10 OR decode_tok_s<6 OR n_ctx>10000",
        "new_rule": "ttft_s>10 OR decode_tok_s<6  (MEASURED only; no ctx)",
        "rationale": (
            "CTX_LIMIT is CAP-1/C-2 cold-start bound; arms run RESIDENT where depth "
            "TTFT is delta-prefill (~0.16 of full prefill per 41e419bd). Static "
            "cold-start ctx gate would escalate on accumulated context even when "
            "measured TTFT meets SLO."
        ),
        "n_entries": 200,
        "n_local_turns": n_local,
        "max_n_ctx": max_ctx,
        "turn_triggers": {
            "old": old_turn,
            "new": new_turn,
            "ctx_only_old_minus_new": ctx_only_turns,
            "ttft_gt_10": ttft_n,
            "decode_lt_6": dec_n,
            "ctx_gt_10000": ctx_n,
        },
        "entry_first_triggers": {
            "old": old_entry,
            "new": new_entry,
            "ctx_only_old_minus_new": ctx_only_entries,
        },
        "verdict": (
            "On sealed R2a ledger, old and new rules agree: 0 escalations "
            f"(max n_ctx={max_ctx} < 10000; no TTFT/decode SLO trips). "
            "Difference is preventative for deeper RESIDENT contexts."
        ),
    }
    out = ROOT / "derived/h1_hybrid"
    (out / "slo_rule_old_vs_new_86d0f4cf.json").write_text(
        json.dumps(slo_cmp, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    class_c = {
        "kind": "r2a_class_c_census",
        "run_id": "86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3",
        "definition": "Class C = tool_exec_error on a turn (R2c bounce trigger tool_exec_error)",
        "sealed_r2a": {
            "tool_exec_error_field_present": field_present,
            "n_turns_tool_exec_error": n_tool_err_turns,
            "n_entries_tool_exec_error": n_tool_err_entries,
            "note": "LEDGER-C landed after this seal; field absent on 86d0f4cf turns.",
        },
        "h1_analyze_census_r2a_C": census["C_tool_exec_error"],
        "proxy_workload_zero_counts": {
            "q_kv_137f6f46": {"gpu_only_f16": 0, "gpu_only_u8": 0, "gpu_only_u4": 0},
            "q_repro_6dd387aa": {"gpu_only": 0, "gpu_only_f16": 0},
            "q8b_72d270e2": {"int4_4B": 0, "int4_8B": 0},
            "note": (
                "After LEDGER-C, tool_exec_error is recorded on these quality seals; "
                "all zero on this BFCL multi-turn workload."
            ),
        },
        "r2c_third_trigger_status": "effectively_dead_on_this_workload",
        "verdict": (
            "Class-C count on sealed R2a = 0 (field absent). Post-LEDGER-C quality "
            "seals also show 0 tool_exec_error. Trigger is live in code/tests but "
            "expected fire rate on this workload is ~0."
        ),
    }
    (out / "r2a_class_c_census.json").write_text(
        json.dumps(class_c, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    local_completion_mid = 12 / 200
    local_completion_lo = 10 / 200
    local_completion_hi = 14 / 200
    emit_fail_mid, emit_fail_lo, emit_fail_hi = 63, 61, 64
    cloud_rate = 0.65
    a, b = 0.006739318451771448, 0.08430605099324187
    mean_n_cloud_turns = 3.1076923076923078
    usd_per_esc = a + b * mean_n_cloud_turns
    usd_per_bounce = a + b * 1.0
    r2c_superseded_usd = 68 * usd_per_bounce

    n_esc = emit_fail_mid
    r2b_usd = n_esc * usd_per_esc
    r2b_usd_lo = emit_fail_lo * usd_per_esc
    r2b_usd_hi = emit_fail_hi * usd_per_esc
    meas_usd, meas_esc = 17.467878, 65
    r2b_usd_from_meas_scale = meas_usd * (n_esc / meas_esc)
    floor_c = local_completion_mid
    indep_c = local_completion_mid + (n_esc / 200) * cloud_rate

    n_bounce_lo = emit_fail_lo + 3
    n_bounce_mid = emit_fail_mid + 3
    n_bounce_hi = emit_fail_hi + 3
    r2c_usd_mid = n_bounce_mid * usd_per_bounce

    pred = {
        "kind": "h1_3policy_predictions",
        "registered_for": "H1-3POLICY interleaved session (no live measurement in this filing)",
        "session_design": "interleaved",
        "arm_order": ["slo_escalate", "emission_escalate", "full_signal_bounceback"],
        "config": {
            "placement": "gpu_only",
            "residency": "RESIDENT",
            "kv": "u8",
            "weight": "int4",
            "tier": "4B",
            "model": "Qwen3-4B-int4-ov",
            "kv_match_seal": "86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3",
        },
        "caps_usd": {
            "slo_escalate": 5.0,
            "emission_escalate": 20.0,
            "full_signal_bounceback": 10.0,
            "session": 35.0,
        },
        "baseline_regime": {
            "note": (
                "Cross-session absolute rates unstable (W-3 vs Q-KV); numbers below "
                "are the current 4B band."
            ),
            "runs": {
                "q_kv_137f6f46_u8": {"emission_failures": 65, "trajectory_pass": 13},
                "q_repro_6dd387aa_gpu_only": {
                    "emission_failures": 61,
                    "trajectory_pass": 14,
                },
                "q8b_72d270e2_int4_4B": {"emission_failures": 64, "trajectory_pass": 10},
            },
            "completion_band": "10-14 / 200 (~0.05-0.07)",
            "emission_failure_band": "61-64 / 200",
            "local_completion_mid": local_completion_mid,
            "emit_fail_mid": emit_fail_mid,
            "superseded_w3_completion": 0.1,
            "superseded_w3_empty_turn": 45,
        },
        "cost_fit_r2b_8ffd8371": {
            "a": a,
            "b": b,
            "mean_n_cloud_turns": mean_n_cloud_turns,
            "usd_per_escalated_entry": usd_per_esc,
            "usd_per_single_bounce_turn": usd_per_bounce,
        },
        "predictions": {
            "R2a": {
                "label": "R2a",
                "policy": "slo_escalate",
                "completion": {
                    "value": local_completion_mid,
                    "range": [local_completion_lo, local_completion_hi],
                    "tag": "REANCHORED mid(10..14)/200",
                },
                "cloud_usd_total": {
                    "value": 0.0,
                    "tag": "MEASURED(86d0f4cf) 0 esc; new rule still 0",
                },
                "emission": {
                    "value": 1.0 - emit_fail_mid / 200,
                    "range": [1.0 - emit_fail_hi / 200, 1.0 - emit_fail_lo / 200],
                },
                "slo_fraction_local_turns": 1.0,
                "superseded": {
                    "completion": 0.1,
                    "cloud_usd_total": 0.0,
                    "emission": 0.775,
                    "source": "derived/d1_replay/h1_predictions.json",
                },
            },
            "R2b": {
                "label": "R2b",
                "policy": "emission_escalate",
                "n_escalated": {
                    "value": n_esc,
                    "range": [emit_fail_lo, emit_fail_hi],
                },
                "cloud_usd_total": {
                    "value": round(r2b_usd, 4),
                    "lo": round(r2b_usd_lo, 4),
                    "hi": round(r2b_usd_hi, 4),
                    "arithmetic": (
                        f"{n_esc} * ({a:.6f} + {b:.6f}*{mean_n_cloud_turns:.6f}) = "
                        f"{r2b_usd:.4f}"
                    ),
                    "alt_scale_from_8ffd8371": {
                        "value": round(r2b_usd_from_meas_scale, 4),
                        "arithmetic": (
                            f"{meas_usd:.6f} * ({n_esc}/{meas_esc}) = "
                            f"{r2b_usd_from_meas_scale:.4f}"
                        ),
                    },
                },
                "completion": {
                    "floor": floor_c,
                    "indep": indep_c,
                    "arithmetic_indep": (
                        f"{local_completion_mid} + ({n_esc}/200)*{cloud_rate} = {indep_c}"
                    ),
                },
                "superseded": {
                    "n_escalated": 45,
                    "cloud_usd_total": 13.081162053325604,
                    "cloud_usd_interval": [11.875233793513566, 14.287090313137643],
                    "completion_floor": 0.1,
                    "completion_indep": 0.24625,
                    "source": "derived/d1_replay/h1_predictions.json",
                },
            },
            "R2c": {
                "label": "R2c",
                "policy": "full_signal_bounceback",
                "n_bounces": {
                    "value": n_bounce_mid,
                    "range": [n_bounce_lo, n_bounce_hi],
                    "arithmetic": f"{emit_fail_mid}+3+0 = {n_bounce_mid}",
                    "components": {
                        "A_no_parseable_approx": emit_fail_mid,
                        "B_max_steps_sealed_r2a": 3,
                        "C_tool_exec_error": 0,
                    },
                },
                "cloud_usd_total": {
                    "value": round(r2c_usd_mid, 4),
                    "lo": round(n_bounce_lo * usd_per_bounce, 4),
                    "hi": round(n_bounce_hi * usd_per_bounce, 4),
                    "arithmetic": (
                        f"{n_bounce_mid} * ({a:.6f}+{b:.6f}) = {r2c_usd_mid:.4f}"
                    ),
                },
                "completion": {
                    "value": local_completion_mid,
                    "range": [local_completion_lo, local_completion_hi],
                },
                "trigger_surface_note": (
                    "R2c is a two-trigger policy on BFCL multi_turn_base: "
                    "tool_exec_error (class C) is live in code but zero on this "
                    "workload. Active: no_parseable_tool_call + step_budget/max_steps."
                ),
                "injection_note": (
                    "R2C-INJECT: cloud assistant enters local ChatHistory; KV "
                    "invalid after inject; next local generate re-prefills "
                    "(re_prefill_s on bounce ledger)."
                ),
                "superseded": {
                    "n_bounces": 68,
                    "cloud_usd_total": round(r2c_superseded_usd, 4),
                    "arithmetic_superseded": (
                        f"68 * {usd_per_bounce:.6f} = {r2c_superseded_usd:.4f} "
                        "(filed as ~$6.19)"
                    ),
                    "census_note": "Incomplete census: A(65)+B(3), C field absent",
                    "source": "H1-ANALYZE R2c pre-registration from 86d0f4cf census",
                },
            },
        },
        "slo_rule": {
            "old_vs_new_artifact": "derived/h1_hybrid/slo_rule_old_vs_new_86d0f4cf.json",
            "class_c_artifact": "derived/h1_hybrid/r2a_class_c_census.json",
        },
    }
    (out / "H1_3POLICY_PREDICTIONS.json").write_text(
        json.dumps(pred, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    md = f"""# H1-3POLICY predictions (re-anchored)

**Status:** filed before interleaved live session. Superseded W-3-anchored values kept visible.

**Session design (INF-5):** `interleaved` - entry-by-entry over policies
`slo_escalate` -> `emission_escalate` -> `full_signal_bounceback`.

**Config:** gpu_only RESIDENT int4-4B, KV=u8 matching `86d0f4cf`.

**Caps:** R2a $5 / R2b $20 / R2c $10 / session $35.

## Baseline regime (current, not W-3)

| run | arm | emission failures | trajectory_pass |
|---|---|---:|---:|
| `137f6f46` | gpu_only_u8 | 65 | 13 |
| `6dd387aa` | gpu_only | 61 | 14 |
| `72d270e2` | int4_4B | 64 | 10 |

Band used: completion **10-14/200** (mid **12/200 = 0.06**); emission failures **61-64** (mid **63**).

**Superseded W-3 anchors (kept):** completion **0.100** (20/200); empty_turn **45**.

## Cost fit (sealed R2b `8ffd8371`)

`usd ~= {a:.6f} + {b:.6f} x n_cloud_turns`
Per escalated entry (mean n_cloud_turns={mean_n_cloud_turns:.4f}): **${usd_per_esc:.4f}**
Per single bounce turn: **${usd_per_bounce:.4f}**

## Predictions

| arm | field | re-anchored | superseded (kept) |
|---|---|---|---|
| R2a | completion | **0.06** [0.05, 0.07] | 0.100 |
| R2a | cloud $ | **0.00** | 0.00 |
| R2a | emission | **0.685** [0.68, 0.695] | 0.775 |
| R2b | n_escalated | **63** [61, 64] | 45 |
| R2b | cloud $ | **{r2b_usd:.2f}** [{r2b_usd_lo:.2f}, {r2b_usd_hi:.2f}] | 13.08 [11.88, 14.29] |
| R2b | completion floor/indep | **{floor_c:.4f} / {indep_c:.4f}** | 0.1000 / 0.2463 |
| R2c | n_bounces | **{n_bounce_mid}** [{n_bounce_lo}, {n_bounce_hi}] | 68 |
| R2c | cloud $ | **{r2c_usd_mid:.2f}** [{n_bounce_lo * usd_per_bounce:.2f}, {n_bounce_hi * usd_per_bounce:.2f}] | ~6.19 |

### Arithmetic

**R2b $:** `63 x (0.006739 + 0.084306 x 3.1077) = 63 x {usd_per_esc:.6f} = {r2b_usd:.4f}`
Alt scale from measured: `17.467878 x (63/65) = {r2b_usd_from_meas_scale:.4f}`

**R2b completion indep:** `0.06 + (63/200)x0.65 = 0.06 + 0.20475 = {indep_c:.5f}`

**R2c bounces:** `63 + 3 (max_steps on 86d0f4cf) + 0 (class C) = {n_bounce_mid}`
**R2c $:** `{n_bounce_mid} x {usd_per_bounce:.6f} = {r2c_usd_mid:.4f}`
**Superseded R2c $:** `68 x {usd_per_bounce:.6f} = {r2c_superseded_usd:.4f}` (filed as ~$6.19)

## SLO rule

New: MEASURED `ttft_s` / `decode_tok_s` only.
Old-vs-new on `86d0f4cf`: see `slo_rule_old_vs_new_86d0f4cf.json` - **0 vs 0** (max ctx {max_ctx}).

## Class C

See `r2a_class_c_census.json` - **0** on sealed R2a; **0** on post-LEDGER-C Q seals. Third R2c trigger is live in code but effectively dead on this workload.

## Launch (no measurement from this filing)

```powershell
powershell -NoProfile -File tools/launch_h1.ps1 -Interleaved
```
"""
    (out / "H1_3POLICY_PREDICTIONS.md").write_text(md, encoding="utf-8")
    print("ok", "max_ctx", max_ctx, "r2b", round(r2b_usd, 4), "r2c", round(r2c_usd_mid, 4))


if __name__ == "__main__":
    main()
