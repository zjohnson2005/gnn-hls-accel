# Local model feasibility on BFCL v4 multi-turn

**What this answers:** can a 4B model running on consumer client silicon actually
do the agentic work a hybrid router would send it — and what does weight
configuration change about that?

Headline numbers below are the sealed **n = 200** full-category local arms.
Every figure carries its `run_id`. The earlier **n = 20** prefix is kept as a
**pilot** (superseded, not contradicted).

| Arm | `run_id` | Seal |
|---|---|---|
| Qwen3-4B-int4-ov | `6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a` | sealed |
| Qwen3-4B-int8-ov | `1d8db970-4c18-4bcf-824d-d9c141b6eb22` | sealed |
| Paired analysis | `paired_analysis.json` sha256 `db75b89d…` | under both sealed trees |
| 20-entry pilot (int4) | `a621ff7d-2919-463d-aaf6-673f9e6bafbc` | superseded prefix |

---

## Setup

| | |
|---|---|
| Workload | BFCL v4 `multi_turn_base`, all **200** entries (fixed prefix `questions[:n]`, no shuffle) |
| Source | `bfcl_eval` 2025.12.17, Apache-2.0 |
| Scorer | `bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker` via CAP-01 shim |
| Scorer validation | gold path 200/200 valid on both sealed arms |
| Local arms | Qwen3-4B-int4-ov / Qwen3-4B-int8-ov, OpenVINO GenAI, `gpu_only` RESIDENT (Intel Arc iGPU, Core Ultra 5 325) |
| Generation | greedy (`do_sample=False`); one-entry diffs are not sampling noise (`db75b89d`) |
| Cloud arm | claude-sonnet-5, **still n = 20** — see Limits |

---

## Results (n = 200)

### Trajectory (all turns must pass)

| arm | correct | n | accuracy | `run_id` |
|---|---|---|---|---|
| int4 | 20 | 200 | **10.0%** | `6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a` |
| int8 | 23 | 200 | **11.5%** | `1d8db970-4c18-4bcf-824d-d9c141b6eb22` |

Trajectory McNemar (paired, entry-level): b = 4, c = 7, **p = 0.55**
(`db75b89d`). Configuration does not move task completion at this n.

### Per-turn, prefix-scored (`accuracy_per_turn_f2`)

| arm | correct | total | accuracy | `run_id` |
|---|---|---|---|---|
| int4 | 251 | 732 | **34.3%** | `6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a` |
| int8 | 288 | 734 | **39.2%** | `1d8db970-4c18-4bcf-824d-d9c141b6eb22` |

Per-turn McNemar (b = 17, c = 53, p = 1.9e-5) is recorded in `db75b89d` as
**suggestive only** — confounded by state cascade after divergence.

### 20-entry pilot — superseded, not contradicted

Pilot `a621ff7d-2919-463d-aaf6-673f9e6bafbc` (int4, first 20 of the same
prefix): per-turn **44.1%** (30/68), trajectory **5%** (1/20),
`force_terminated` **10%** (2/20).

That prefix is **unrepresentative** of the full category in three measured
ways (`6225d6e1` / `db75b89d`):

1. **Per-turn accuracy.** Pilot 44.1% vs full-set 34.3% (251/732). Wilson 95% CI
   on the full set is **[30.9%, 37.8%]**; the pilot point lies **outside** that
   interval.
2. **`force_terminated` rate.** Pilot **10%** (2/20) vs **0.56%** on entries
   20–199 (1/180) — about **18×** over-represented in the prefix
   (`db75b89d` `force_terminated_cross`).
3. **Concentration.** The pilot contained **2 of the 3** total
   `force_terminated` events across all 200 int4 entries
   (`multi_turn_base_2`, `_15`; the third is `_34`).

---

## The independence model is falsified at n = 200

At n = 20 the claim was that trajectory accuracy is the product of independent
per-turn competences (“arithmetic, not mechanistic”), and that model
reproduced the pilot scores exactly. **That claim is falsified on both arms at
n = 200** (`db75b89d` `independence_model_n200`):

| arm | p_turn | mean turns | predicted | observed | residual | ratio |
|---|---|---|---|---|---|---|
| int4 (`6225d6e1`) | 0.343 | 3.66 | **0.020** | **0.100** | **+0.080** | **5.0×** |
| int8 (`1d8db970`) | 0.392 | 3.67 | **0.032** | **0.115** | **+0.083** | **3.6×** |

The same independence formula that matched the pilot fails here by a
same-signed ~8 pp excess on two independent weight arms. That is structure,
not noise: a shared misspecification, not a one-arm fluke.

### Per-turn hazard by turn index

Hazard = fail rate among entries still alive entering that turn, using the
same per-turn `pass` bit as `accuracy_per_turn_f2` (computed from sealed
`w3_entry_ledger.json`).

**int4** (`6225d6e1`):

```
turn   alive   fail   pass   hazard
  0      200    145     55    72.5%
  1       55     29     26    52.7%
  2       25     13     12    52.0%
  3        7      2      5    28.6%
  4        4      0      4     0.0%   (n small)
  5        2      1      1    50.0%   (n small)
  6        1      1      0   100.0%   (n=1)
```

**int8** (`1d8db970`):

```
turn   alive   fail   pass   hazard
  0      200    137     63    68.5%
  1       62     37     25    59.7%
  2       24     10     14    41.7%
  3        9      2      7    22.2%
  4        7      2      5    28.6%   (n small)
  5        3      2      1    66.7%   (n small)
  6        1      1      0   100.0%   (n=1)
```

On the well-populated turns (0–3), hazard is **highest at turn 0 and then
flat-to-lower**. It does **not** rise with turn index. Therefore the ~8 pp
excess over the independence prediction is **entry-level heterogeneity**
(variance in entry difficulty — hard entries die early; survivors are easier),
**not** within-session degradation. A rising hazard would have been a
different and bigger claim; the data do not support that.

### Per-entry turn-count distribution

Both arms run the same 200 entries. User-turn counts
(`6225d6e1` / `1d8db970` ledgers):

```
turns/entry :  1   2   3   4   5   6   7
n_entries   :  3  40  50  50  43  12   2
mean        ≈  3.67
```

Trajectory is a product over a **varying** number of turns. A fixed-exponent
model `p_turn ** mean_turns` understates the all-pass rate relative to a
mixture over short and long entries: short entries contribute
disproportionately to observed trajectory passes. Heterogeneous difficulty
and heterogeneous length both push in the same direction as the observed
positive residual.

---

## Emission reliability (configuration moves a different axis)

Artifact: `derived/bfcl_feasibility/w3_weight_quality/empty_turn_mcnemar_and_raw_heads.json`
(sha256 prefix `de7ac2d4`); sessions `6225d6e1` / `1d8db970`.

Definition: entry-level `failure_bucket == multi_turn:empty_turn_model_response`.

| | int8 empty | int8 not |
|---|---|---|
| **int4 empty** | 13 | **32** |
| **int4 not** | **7** | 148 |

- int4 fails to emit a parseable tool call where int8 succeeds on **32**
  entries; reverse on **7**.
- Odds ratio **4.57** [1.98, 12.27], **p = 7.0e-5** (paired McNemar,
  entry-level — no clustering concern).

Mechanism confirmed by inspection of raw outputs: the model narrates intent
in prose without emitting `<tool_call>`. Examples from the b-set
(`6225d6e1` empty / `1d8db970` not):

- `multi_turn_base_20`: *"I will first navigate to the \"documents\" folder…"*
- `multi_turn_base_39`: *"I will navigate into the 'WebDevProjects' directory…"*
- `multi_turn_base_17`: *"Please wait a moment while I retrieve the information."*

Trajectory completion is unchanged (McNemar **p = 0.55**, `db75b89d`).
**Quality is not one number:** emission reliability and task completion
respond differently to configuration. Weight bit-width is the first measured
axis that moves quality, and it moves emission reliability specifically.

---

## The failure is capability, not context

This claim previously rested on flat hazard alone. It now has a mechanism.

On int4 `force_terminated` entries (`6225d6e1`: `multi_turn_base_2`, `_15`,
`_34`), the model restates a tool error correctly in prose and then
**re-emits the identical failing call** — up to **21** consecutive steps on
`multi_turn_base_15` (payload
`{"name": "wc", "arguments": {"file_name": "DataSet1.csv", "mode": "lwc"}}`).
No error-driven adaptation.

Example (`multi_turn_base_15`, `6225d6e1`), after the tool has already
rejected `mode: "lwc"`:

> I apologize for the error. The `wc` command doesn't have a "lwc" mode. Let me correct that.
>
> Let's count the lines, words, and characters in "DataSet1.csv" using the correct mode.
>
> ```
> <tool_call>
> {"name": "wc", "arguments": {"file_name": "DataSet1.csv", "mode": "lwc"}}
> </tool_call>
> ```

The prose names the error; the next call is identical. That is a capability
failure (no repair), not context growth, KV precision, residency, or
attention-window configuration. Those knobs do not address a model that
cannot revise a failing tool call.

Turn-0 mass is still large (first failures concentrate early under the
per-turn pass bit), which is consistent with the same conclusion: most
trajectories are already lost before meaningful context has accumulated.

---

## Limits — read before citing

- **Cloud arm remains n = 20** (`cloud_multi_turn_report.json`, matched to the
  same first-20 prefix as pilot `a621ff7d`). Any local-vs-cloud comparison is
  **20-entry-limited** even though the local arms are now 200, and that prefix
  is measurably unrepresentative (above). The old **5% vs 65%** trajectory
  framing is **dropped** until restated on matched entries at a common n.
- **Timing cells and quality cells use different prompt formats.** The Qwen3
  chat template injects a `# Tools` system block whenever `tools=` is
  non-empty; timing cells never pass `tools`. The probe records the formats
  as **not comparable**
  (`derived/bfcl_feasibility/gpu_probe_report.json` →
  `prompt_format_divergence`).
- **MDE.** For the per-turn int4-vs-int8 contrast at the sealed n: ~**7.5**
  points unadjusted, ~**10.6** with design effect 2
  (`6225d6e1` / `1d8db970` manifests, `power_analysis`). Resolving a 5-point
  effect would need roughly **800** entries; `multi_turn_base` contains
  **200**. Quality differences of that magnitude are below the resolution of
  the full category.
- `multi_turn_base` only. `long_context`, `miss_func`, and `miss_param` are
  untested at this design.
- Cloud wall-clocks are network-inclusive and are **not** a latency
  measurement against local timings.

## Cost note (20-entry cloud only)

The cloud run cost **$5.41** for **20 entries**
(`cloud_multi_turn_report.json` `spend.usd` = 5.407; rates $3 / $15 per 1M
tokens in/out). This figure is **not** rescaled to n = 200. Earlier repo
estimates assumed one API call per entry; an agent loop issues one per step
with growing context.

---

## Reproducing

```powershell
# local quality arm (n=200 design), requires a clean host
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py `
    --mode run_gpu_multi_turn --out derived\bfcl_feasibility

# cloud arm (n=20), requires ANTHROPIC_API_KEY. Not latency-measured.
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py `
    --mode run_cloud_multi_turn --out derived\bfcl_feasibility

# offline scorer selftest
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py `
    --mode run_cloud_multi_turn --selftest --out derived\bfcl_feasibility
```

Sealed quality artifacts:
`derived/bfcl_feasibility/w3_weight_quality/sealed_6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a/`,
`derived/bfcl_feasibility/w3_weight_quality/sealed_1d8db970-4c18-4bcf-824d-d9c141b6eb22/`,
paired `paired_analysis.json` (`db75b89d`), emission follow-up
`empty_turn_mcnemar_and_raw_heads.json` (`de7ac2d4`).
