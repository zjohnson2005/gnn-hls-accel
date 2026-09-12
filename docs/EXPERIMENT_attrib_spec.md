# E-ATTRIB — implementation spec

**Track:** `attrib`. Runs concurrently with the `agent` track (E-FILTER). Read §1 before touching
anything — the isolation rules are not advisory.

---

## 0. Audit result — read this first, it narrows the claim

Searched 2026-08-03. **The modeling machinery is not novel and must not be presented as such.**

| Prior work | What it already has |
|:--|:--|
| [Interpretable Latency Model for Speculative Decoding, 2605.15051](https://arxiv.org/html/2605.15051v1) | Regression latency model with explicit **fixed-cost coefficients**, prefill/verify/draft decomposition, MAPE < 2%. Fixed cost attributed to weight movement and kernel setup. |
| [lm-Meter, 2510.06126](https://arxiv.org/html/2510.06126) | Lightweight **on-device** runtime latency profiler; sub-phase attribution without distorting the measurement. |
| [RooflineBench, 2602.11506](https://arxiv.org/html/2602.11506v2) | On-device roofline benchmarking; identifies **context length** as the primary driver of operational intensity. |
| LLM-Viewer, LLMRoofline | Public tools that already answer "bandwidth or compute upgrade?" via roofline. |
| [Transferable Latency Prediction, 2607.21602](https://arxiv.org/html/2607.21602v1) | Cross-device edge latency prediction. |
| Serving-pipeline studies | Tokenization measured at **35.73% of TTFT** in one setting — the fixed-cost story is partly documented. |

**Borrow the model form and cite it.** Fitting `a + b·prompt + c·output` is standard practice, not
a contribution.

**What remains ours — the entire claim reduces to these three:**

1. **The rotation.** The sensitivity vector ∂t/∂(hardware resource) changes rank order as the
   escalation deadline moves. Requires the device↔cloud boundary. No prior work has it.
2. **The agent-step floor.** Prior fixed-cost terms are per-*request* in a serving stack. An agent
   step additionally carries message assembly, tool-result parsing, cache management, and
   re-templating. Nobody has decomposed that.
3. **The router critique.** Escalation policies predict step latency with token-proportional models
   carrying no constant term. If `a` is material, those decisions are biased on short steps.

**Nothing else in this experiment is a claim.** If a result is interesting but outside those three,
record it and move on — do not inflate it.

---

## 1. Concurrency contract — non-negotiable

The `agent` track is running E-FILTER on the same repository and the same physical machine.

### Paths this track owns (create and edit freely)

```
seam/bench/__init__.py
seam/bench/attrib.py              microbenchmark driver
seam/analysis/attrib_fit.py       model fitting + validity dashboard
derived/attrib/**
docs/EXPERIMENT_attrib_results.md
AUDIT_LOG_attrib.md               ← separate file, NOT AUDIT_LOG.md
configs/attrib.yaml
tests/test_attrib_*.py
```

### Read-only — import, never edit

`seam/backends/**`, `seam/manifest.py`, `seam/rawstore.py`, `seam/locks.py`, `seam/kvmath.py`,
`seam/powerstate.py`, `seam/topology.py`, `seam/hashing.py`, `seam/config.py`.

### Forbidden

`seam/agent/**` and `seam/tools/efilter_run.py` belong to the other track and are being actively
edited. `AUDIT_LOG.md` — concurrent appends are the worst merge conflict in this repo.
`docs/SEAM_research_blueprint.md`, `GOVERNING_DOCS.sha256`, `configs/project_state.yaml` — pinned
governing documents, human-authorized only.

**If you need a change in a read-only module, stop and report it. Do not edit it.**

### Machine exclusivity — the real constraint

Both tracks need a quiesced machine. Concurrent timed runs corrupt each other's data and neither
will look wrong.

`seam/locks.py` provides `ExclusiveLock` and `exclusive(path)`. Wrap **every timed measurement
block** in:

```python
from seam.locks import exclusive
with exclusive(repo_root / ".locks" / "machine"):
    ...   # all timed work here
```

Acquire, measure, release. Do not hold across analysis or code generation. **Code, analysis, and
writing proceed concurrently with the other track; only measurement serializes.** If the lock is
held, wait — do not measure anyway, and do not measure "just a quick one" outside it.

Record lock acquisition and release timestamps in every manifest so post-hoc contention is
detectable.

---

## 2. The model

```
t_step  =  a  +  prompt_new / R_prefill  +  n_out × ( d0 + d1 × context )
```

| Parameter | Meaning | Bought down by |
|:--|:--|:--|
| `a` | per-step fixed floor | fusion, graph capture, lighter dispatch — **not silicon** |
| `R_prefill` | new-token ingest rate | compute |
| `d0` | per-token decode cost independent of context: weight streaming + dequantization + per-token dispatch | bandwidth, native INT4, fewer launches |
| `d1` | per-token decode cost per token of resident context: KV streaming | bandwidth, KV layout, KV quantization |

Fit **separately for each execution target and each quantization**. `d0` differences between INT4
and INT8 at matched context isolate weight-streaming from dequantization.

---

## 3. Design — and the trick without which nothing is identifiable

**Context length and new-prompt length must vary independently.** A real agent cannot do this,
because its context *is* accumulated prompt. Use synthetic prompts against a warmed cache: seat a
long resident context, then issue a short new prompt.

If the backend cannot seat a context without re-ingesting it, report the mechanism failure before
running the full sweep and use the interaction route below. Do not repair or tune the failed
seating mechanism after seeing the result.

### Identification routes

The chat mechanism is tested first, under the machine lock, by comparing:

```
seated:  start_chat(); generate(C); generate(N); finish_chat()
cold:    generate(render(C, response_to_C, N))
```

The rendered token IDs must be identical, greedy output bytes must be identical, and the median
`TTFT_seated / TTFT_cold` over at least five randomized repeats must be `< 0.5`.

- **If the mechanism passes**, fit both routes:
  1. **Seated route:** vary resident context and new prompt independently, as originally designed.
  2. **Interaction route:** with `P` equal to total prompt tokens,

     ```
     t = a + P/R_prefill + n_out*d0 + (n_out*P)*d1
     ```

     Sweep `n_out` at several fixed `P`. The decode slope at each `P` is `d0 + d1*P`; regressing
     those slopes against `P` identifies `d1` and `d0`. Center both `P` and `n_out` before fitting
     so the interaction term does not manufacture a poor condition number.

- **If the mechanism fails**, fit the centered interaction route only. The seated-route failure is
  reported as a finding and is not repaired without a new authorization.

### Factorial grid — interaction route, INT4 only

The seated route is unavailable (spike `6b40e3fe`, §7). `context_resident` and `prompt_new` are
therefore not separable and collapse into a single factor `P` = total prompt tokens. Quantization
is dropped: the INT8 IR is absent, and the `d0` split it would enable is **not one of the three
claims in §0**.

```
P (total prompt)   {  512, 1024, 2048, 4096, 8192, 16384, 32768 }   tokens   — 7 levels
n_out              {    8,   32,   64,  128,  256 }                 tokens   — 5 levels
quantization       {  INT4 }                                                  fixed
execution_target   {  cpu-p }                                                 fixed
```

**35 cells × ≥7 repeats**, randomized order. Seven `P` levels are the minimum for the second-stage
regression of decode-slope against `P` to have usable leverage; do not reduce them. Log spacing
is deliberate — `d1` is estimated from curvature in the slope-vs-`P` line and even spacing wastes
resolution at the short end where `a` dominates.

`P = 32768` plus 256 generated stays inside `max_position_embeddings = 40960`. The former 49152
cell was invalid and is removed.

Add **6 held-out cells** at off-grid `(P, n_out)` values for out-of-sample error.

Warmed to thermal steady state, cooled between blocks, AC power with **charging complete** — not
merely connected. A charging taper previously produced a +0.444 tok/s block-position slope that
mimicked a thermal effect.

### Runtime pilot — required before the full sweep

With no prefix reuse, every cell re-prefills `P` in full, so cost scales with `P` and the top
levels may dominate the schedule. **Time the four corner cells** — `(512, 8)`, `(512, 256)`,
`(32768, 8)`, `(32768, 256)` — extrapolate total sweep wall time including cooldowns, and **report
the estimate before committing.** If the projection exceeds one overnight run, report it and stop;
reducing `P` levels is not an available fix and the schedule is the human's to authorize.

### Second half — validation on real agent steps

Take E-FILTER's sealed local-only step logs (**read-only**), predict each step's wall time from the
fitted model, and report held-out MAPE. This is the number that decides whether the model describes
agent behavior or only microbenchmarks.

---

## 4. THE VALIDITY DASHBOARD

Every run emits `derived/attrib/validity.json` and a rendered table. **A conclusion is reported
only if every gate in A, B and C passes.** Report the table whether or not it passes.

### A — Identifiability: can the parameters be separated at all?

| ID | Reported value | Pass | Meaning if it fails |
|:--|:--|:--|:--|
| A1 | design-matrix condition number κ | **< 30** | predictors collinear; coefficients are arbitrary splits of a sum |
| A2 | VIF per predictor | **< 5** each | same, per-term |
| A3 | 95% CI of `a`, `R_prefill`, `d0`, `d1` | each **excludes 0** | that term is not detectable; drop it and refit |
| A4 | max abs pairwise correlation of coefficient estimates | **< 0.8** | two terms are trading off; the split is not trustworthy |
| A5 | route-specific design check | **Seated spike passes:** `corr(context, prompt_new) < 0.2`. **Spike fails:** `P` and `n_out` each have ≥3 levels and interaction-term VIF `< 5` | seated decoupling failed, or the fallback interaction is not identifiable |
| A6 | dual-route agreement | **not evaluable** — seated route unavailable (spike `6b40e3fe`). Report as such; do not silently omit the row | — |
| A6′ | **split-half agreement** (replaces A6 while only one route exists) | partition the design into two halves balanced on `P` and `n_out`, fit independently, 95% CIs overlap on **all four** parameters | the fit is not reproducible within its own dataset. This is the only independent-replication check available once the second route is gone, so it is not optional |
| A7 | synthetic recovery | fitter recovers known coefficients from simulated data within CI, and **refuses loudly** on a rank-deficient design | the estimator itself is unsound; nothing downstream means anything |

### B — Fit quality: is the model form right?

| ID | Reported value | Pass | Meaning if it fails |
|:--|:--|:--|:--|
| B1 | in-sample R² | **≥ 0.95** | model form wrong or noise dominates |
| B2 | held-out-cell MAPE | **≤ 15%** | overfit to the grid |
| B3 | **agent-step MAPE** (E-FILTER logs) | **≤ 25%** | model describes microbenchmarks, not agents — the claim does not transfer |
| B4 | residual vs context: slope p-value | **> 0.05** | missing context term; try quadratic |
| B5 | residual vs repeat index: slope p-value | **> 0.05** | thermal or charging drift contaminated the fit |
| B6 | ΔAIC vs no-constant model (`a ≡ 0`) | **≥ 10** favouring `a` | the constant is not earning its place; the whole CS-31 half is null |
| B7 | ΔAIC vs quadratic-context model | report both | if quadratic wins by ≥10, the linear KV model is wrong — say so |

### C — Measurement validity

| ID | Reported value | Pass | Meaning if it fails |
|:--|:--|:--|:--|
| C1 | CV of each coefficient across repeat blocks | **< 10%** | measurement noise exceeds the effect |
| C2 | first-half vs second-half coefficients | CIs **overlap** | drift during the run; results are not stationary |
| C3 | idle baseline drift across session | **< 5%** | machine state changed underneath the sweep |
| C4 | measured STREAM bandwidth present | **must exist** | any roofline ratio using a *derived* 120 GB/s is provisional and must be labelled so |
| C5 | lock contention windows | **zero overlap** with the other track | concurrent measurement occurred; data suspect |
| C6 | throttle fraction per block | report; **< 5%** for confound regime | thermal regime violated |

### D — Materiality: the finding itself

These do not gate validity. They **are** the result.

| ID | Reported value | Interpretation |
|:--|:--|:--|
| D1 | `a` ÷ median agent step wall time | **≥ 20%** → "most of an agent step is not inference" is supportable · **5–20%** → material; the router must be corrected · **< 5%** → null; report as such |
| D2 | `a` in absolute ms, with CI | the floor no silicon can cross |
| D3 | `d0(INT4)` vs `d0(INT8)` | **DEFERRED** — INT8 IR absent. Not one of the §0 claims; do not block on it and do not export a model to obtain it without authorization |
| D4 | context at which `d1 × context` exceeds `d0` | where KV traffic overtakes weight traffic — the memory-design crossover |
| D5 | **argmax sensitivity across the deadline grid** | **the rotation.** Does the top-ranked hardware resource change? Binary, plus the crossover deadline with CI |
| D6 | router bias: mean signed error of `t_pred` on short steps (n_out ≤ 32) | if systematically negative, the current predictor under-predicts and under-escalates |

### The rotation calculation (D5), explicitly

For each deadline `D` in E-FILTER's grid, take the surviving (non-escalated) step distribution,
and compute the fitted model's sensitivity to each resource, normalized per unit:

```
S_compute(D)   = Σ  ∂t/∂R_prefill      over surviving steps
S_bandwidth(D) = Σ  ∂t/∂(d0, d1)       over surviving steps
S_floor(D)     = N_surviving × a       (pure step count × floor)
```

Report all three against `D`. **The claim holds if argmax changes across the grid.** If it does
not, report the null plainly: the ranking of hardware upgrades is deadline-invariant for this
workload.

---

## 5. Deliverables

1. `seam/bench/attrib.py` — sweep driver, lock-wrapped, manifest-emitting, sealed runs.
2. `seam/analysis/attrib_fit.py` — fit, dashboard, rotation calculation.
3. `derived/attrib/coefficients.json` — parameters with CIs, per target × quantization.
4. `derived/attrib/validity.json` + rendered table — **every gate above, pass/fail, always**.
5. `derived/attrib/rotation.json` + figure — the three sensitivity curves against deadline.
6. `docs/EXPERIMENT_attrib_results.md` — dashboard first, findings second, in that order.
7. `AUDIT_LOG_attrib.md` entry.
8. Tests: synthetic data with known coefficients must be recovered within CI; the fitter must fail
   loudly on a rank-deficient design matrix rather than returning a pseudo-inverse.

## 6. Kill criteria — stop and report, do not work around

- **A5 fails** — if chat seating fails, switch to the pre-declared centered interaction route and
  report the mechanism failure. If the interaction fallback then lacks ≥3 levels for both `P` and
  `n_out`, or its interaction VIF is ≥5, `d1` is unrecoverable and the experiment stops.
- **A1 or A3 fails after grid expansion** — the parameters are not separable on this hardware.
- **B3 fails** — the model describes microbenchmarks but not agent steps. Report it; the negative
  is a real result about the transferability of synthetic latency models.
- **B6 fails** — `a` is not earning its place. CS-31's half is null and only the rotation survives.
- **C5 fails** — concurrent measurement happened. Discard the affected blocks; do not analyze them.

A result that cannot be interpreted is worth more reported than shipped. Every gate above is
reported in every run, including the ones that pass, so the failures are legible in context.

### 2026-08-03 cache-path correction

The earlier conclusion that caching was resolved as “no cross-call prefix reuse; full re-prefill”
was drawn from E-FILTER's **stateless** repeated-prompt path. That conclusion is withdrawn for chat
mode: KV reuse is a calling-convention question, not a runtime-wide property. The dedicated
chat-vs-cold mechanism spike is the authority for the seated route.

---

## 7. Established facts — measured, sealed, not to be re-litigated

### F1 — No cross-call prefix reuse on either API path

Spike `6b40e3fe-cbc1-4b6a-8867-46650b4ead61`:

| Test | Result | Verdict |
|:--|:--|:--|
| Rendered token IDs, seated vs cold | 5/5 identical, 8,148 IDs | PASS |
| Greedy output bytes | 5/5 byte-identical | PASS |
| `TTFT_seated / TTFT_cold` | median 1.0274, CI95 [0.5890, 3.5123] | **FAIL** |

**Identical output with no speedup pins the mechanism precisely.** Chat mode presents the model
with the same context and re-ingests it every call. The 56 Assign sinks are the KV state for the
*within-generation* decode loop — which every autoregressive model requires — and are **not**
cross-call prefix reuse. Those are different mechanisms and the earlier correction conflated them.

**The wide CI does not weaken the conclusion.** Real reuse would give a ratio near `N/(C+N)` ≈
64/8148 ≈ **0.008**. The most favourable end of the interval, 0.589, is **75× away** from that.
When the expected effect spans two orders of magnitude, a noisy null is still decisive. State it
this way rather than apologising for n=5.

The original stateless finding therefore stands, now confirmed on both API paths, and the
alternative explanation is ruled out rather than assumed.

**Consequence beyond this experiment:** the literature holds that agentic workloads are
decode-dominated *because* prefix caching reuses most input tokens. On this stack there is no
reuse, so every step re-prefills the whole accumulated context and prefill cost grows
quadratically across a trajectory. Whether that translates into prefill-dominated *time* is
exactly what this experiment measures — token counts are not time, and no claim about which
resource binds may be made until the fit reports.

### F2 — KV cache is u8, and KV quantization is already spent

Derivation sealed as `1fd81d2a-3bae-40b1-b2a6-b9c5a50586b1`:

```
2 (K and V) × 36 layers × 8 KV heads × 128 dim × 1 byte (u8) = 73,728 bytes/token
```

The 144 KiB figure carried in other project documents assumes a 2-byte f16/bf16 cache. **Dtype,
not head count, explains the 2× discrepancy.** 73,728 is authoritative.

Design-space consequence: the cache already ships INT8, so **KV quantization is not an available
lever for buying down `d1`** — further reduction means going below 8 bits, which is a materially
harder proposition. Record this; it constrains the interpretation of D4.

Downstream correction owed outside this track: the meeting brief, the opening pitch, and the
external email all carry 144 KB/token and the capacity figures derived from it. Those are the
human's to fix — **do not edit them from this track.**
