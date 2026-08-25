# Local model feasibility on BFCL v4 multi-turn

**What this answers:** can a 4B model running on consumer client silicon actually
do the agentic work a hybrid router would send it, and how far short of a cloud
model does it fall?

Measured 2026-08-24. Both arms run the same 20 entries, the same agent loop, and
the same official scorer.

---

## Setup

| | |
|---|---|
| Workload | BFCL v4 `multi_turn_base`, first 20 entries (fixed prefix, no shuffle) |
| Source | `bfcl_eval` 2025.12.17, Apache-2.0 |
| Scorer | `bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker` via CAP-01 shim |
| Scorer validation | gold path 20/20 valid — the checker is trusted, the models are what is under test |
| Local arm | Qwen3-4B-int4-ov, OpenVINO GenAI 2026.2.1, `gpu_only` (Intel Arc iGPU, Core Ultra 5 325, 16 GB unified) |
| Cloud arm | claude-sonnet-5, native Anthropic tool-use blocks |
| Entry pinning | both arms load `multi_turn_probe_entries.json`; ids verified equal |

Tool schemas for the cloud arm are converted from the same BFCL function
definitions via `convert_to_tool(..., ModelStyle.ANTHROPIC)`. The Qwen
chat-template `<tools>` text is not placed in the cloud prompt. The full
name-by-name mapping is recorded in `cloud_multi_turn_report.json`.

---

## Results

### Trajectory (all turns must pass)

| arm | correct | n | |
|---|---|---|---|
| Qwen3-4B local | 1 | 20 | 5% |
| claude-sonnet-5 | 13 | 20 | 65% |

### Per-turn, prefix-scored

| arm | correct | total | |
|---|---|---|---|
| Qwen3-4B local | 18 | 70 | 25.7% |
| claude-sonnet-5 | 50 | 70 | 71.4% |

### Where trajectories first fail

```
              turn0  turn1  turn2  turn3  survived
local           10      5      2      2         1
cloud            2      3      2      0        13
```

### Hazard rate — failures per entry still alive entering that turn

```
             turn0   turn1   turn2   turn3
local         50%     50%     40%     67%
cloud         10%     17%     13%      0%
```

**Failure rate does not rise with turn index in either arm.** The independence
model this implies reproduces both trajectory scores exactly:

```
local:  0.50 x 0.50 x 0.60 x 0.33 = 0.05    observed 1/20  = 0.05
cloud:  0.90 x 0.83 x 0.87 x 1.00 = 0.65    observed 13/20 = 0.65
```

Counting only turns actually attempted, local passes 19 of 38 (50%) against
cloud's 59 of 66 (89%).

### Single-turn, AST-scored (same local arm)

| category | correct | n |
|---|---|---|
| `simple_python` | 3 | 5 |
| `parallel` | 5 | 5 |

---

## What follows from this

**The multi-turn penalty here is arithmetic, not mechanistic.** Trajectory
accuracy is the product of independent per-turn competences. There is no
evidence of state corruption or context degradation accumulating across a
session — if there were, hazard would climb with turn index, and it does not.
A model that is right 50% of the time per step completes a 4-turn session 6% of
the time by construction.

**Trajectory scoring overstates the routing-relevant gap.** A per-step router
cares about per-step competence: 50% against 89%, not 5% against 65%.

**The failure is capability, not context.** Half of local trajectories die at
turn 0, where almost no context has accumulated. No memory, KV-precision,
residency or attention-window configuration addresses a turn-0 failure. Local
quality and hardware configuration are separable concerns, and this experiment
separates them.

---

## Limits — read before citing

- n = 20 entries, four turns deep. The last hazard cell contains three entries.
  Confidence intervals have not been computed.
- One local model and one cloud model. Neither result generalises to a tier.
- `multi_turn_base` only. The `long_context`, `miss_func` and `miss_param`
  categories are untested.
- Cloud wall-clocks in the report are network-inclusive and are **not** a
  latency measurement. Do not cite them against local timings.
- The hazard and independence analysis above was computed by hand from the
  summary tables and has not been re-derived programmatically with CIs.

## Cost note

The cloud run cost **$5.41** for 20 entries. Earlier estimates in this repo
assumed one API call per entry; an agent loop issues one per step with context
growing each time. Any labelling-slice cost figure computed on the one-call
assumption is low by roughly 17x.

---

## Reproducing

```powershell
# local arm, requires a clean host (Available >= 7000 MB, tier-1 closed)
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py `
    --mode run_gpu_multi_turn --out derived\bfcl_feasibility

# cloud arm, requires ANTHROPIC_API_KEY in the environment. Not latency-measured,
# so host cleanliness does not apply.
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py `
    --mode run_cloud_multi_turn --out derived\bfcl_feasibility

# offline scorer selftest, no API call, no GPU
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py `
    --mode run_cloud_multi_turn --selftest --out derived\bfcl_feasibility
```

Artifacts: `multi_turn_gpu_probe_report.json`, `cloud_multi_turn_report.json`,
`MULTI_TURN_CLOUD_REPORT.md`.
