# CAP-3 — 8B-int4 and 4B-int8 gpu_only TTFT limits (pre-registration)

**Status:** `pre_registered_before_measurement`  
**Registered UTC:** 2026-09-17T01:21:47+00:00  
**Do not edit after the first probe starts.**  
**CAP-3-PREP only — no measurement session launched.**

## Why now

Six capability axes are complete, but the capability column previously held only
**4B-int4** (cpu-p limit **500** via `d3dcbd3b`; gpu_only limit **9,750** via
`c647f0c7`). Tier result `72d270e2` makes **8B** quality-relevant; its TTFT
operating limit is load-bearing for whether capacity gates tier choice against
workload max **7,743**.

## Design (shared)

| axis | value |
|---|---|
| launcher | `tools/launch_c2.ps1` |
| worker | `tools/run_c1_ceiling.py --criterion ttft_slo --slo-s 10` |
| placement / arm | `gpu_only` / `gpu_only_f16` (KV f16) |
| residency | RESIDENT (ceiling child path) |
| resolution | **250** (`launch_c2.ps1` / C-2 default) |
| repeats | **3**; median (`launch_c2.ps1` / C-2 default) |
| pass | median `prefill_s` ≤ 10 s |

`-Low` / `-High` / `-Resolution` / `-Repeats` / `-ModelSpec` flow end-to-end:
launcher → worker `--low`/`--high`/`--resolution`/`--repeats`/`--model-spec` →
`bisect_arm` + `load_local_spec(ir_dir)`.

---

## Arm 1 — Qwen3-8B-int4-ov

| axis | value |
|---|---|
| model | `configs/models/Qwen3-8B-int4-ov.yaml` |
| search Low / High | **3000** / **10000** |
| resolution / repeats | 250 / 3 |

**Search basis:** Low below predicted band `[4000, 7000]` for known-good margin if
point ~5500 holds; High above workload **7743** and above 4B anchor / scaling
falsifier **9750**. Resolution/repeats match C-2 defaults.

Invoke:

```text
powershell -NoProfile -File tools/launch_c2.ps1 -Arms gpu_only_f16 -Low 3000 -High 10000 -Resolution 250 -Repeats 3 -ModelSpec configs/models/Qwen3-8B-int4-ov.yaml
```

### P1 — Limit band

**Claim:** `ttft_limit_n` ∈ **[4000, 7000]**; point estimate **~5500**.

**Basis:** 8B ≈ 2× params of 4B → prefill/token roughly proportional; 4B gpu_only
limit **9750** (`c647f0c7`) → half-ish center near ~5500. Band admits moderate
non-linearity and the INT4_ASYM vs INT4_SYM recipe confound on the 8B IR.

### P2 — Below workload 7743 (capacity gates tier)

**Claim:** limit **strictly below 7743**. If held, 8B cannot serve deepest entries
inside the TTFT SLO → **capacity gates tier choice** (with quality relevance from
`72d270e2`).

### P3 — Scaling vs 4B

**Falsified if** limit **exceeds 9750** (8B no slower than 4B at prefill).

---

## Arm 2 — Qwen3-4B-int8-ov

| axis | value |
|---|---|
| model | `configs/models/Qwen3-4B-int8-ov.yaml` |
| search Low / High | **7000** / **12000** |
| resolution / repeats | 250 / 3 |

**Search basis:** Low = lower edge of predicted band `[7000, 9750]`; High =
C-2 default high that located int4’s **9750** (`c647f0c7`). Resolution/repeats
match C-2 defaults.

Invoke:

```text
powershell -NoProfile -File tools/launch_c2.ps1 -Arms gpu_only_f16 -Low 7000 -High 12000 -Resolution 250 -Repeats 3 -ModelSpec configs/models/Qwen3-4B-int8-ov.yaml
```

### P1 — Limit band

**Claim:** `ttft_limit_n` ∈ **[7000, 9750]**.

**Basis:** int8 weights **4.05 GB** vs int4 **2.29 GB**; decode often 1.3–1.5×
slower, but prefill is compute-bound so the TTFT-limit shift should be smaller.

### P2 — Near int4 9750 within resolution

**Claim:** `|ttft_limit_n − 9750| ≤ 250` (one C-2 bisect resolution either way).

**Falsified if** int8 limit differs from int4’s **9750** (`c647f0c7`) by **more
than resolution (250)** either direction.

---

## Citing priors

| id | role |
|---|---|
| `c647f0c7` | 4B-int4 gpu_only TTFT limit **9750** |
| `d3dcbd3b` | 4B-int4 cpu-p TTFT limit **500** |
| `72d270e2` | 8B quality-relevant (tier) |
| **7743** | workload max mid-session prompt size |

## Non-claims

- Not a KV-precision comparison (single arm `gpu_only_f16` per model).
- Not a quality / BFCL accuracy claim (capacity only).
- Do not cite 50 TOPS / ~120 GB/s / 1.38× topology as measurements.

## Launcher wiring (prep)

`-ModelSpec` confirmed by **code-trace only** (no smoke, no spawn): relative path
resolves, appears on `RESOLVED_CMD --model-spec`, and worker argparse +
`load_local_spec` bind the non-default IR.

Prep fixes landed with this registration:

1. `launch_c2.ps1` DryRun tokenizer reads `-ModelSpec` `ir_dir` (was hardcoded 4B-int4).
2. `run_c1_ceiling.py` `plan.json` `ir_bytes` comes from FetchedModelSpec when present.

## Machine-readable twin

`derived/cap3/CAP3_PREDICTIONS.json`
