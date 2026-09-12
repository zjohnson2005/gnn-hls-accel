# Project state — handoff document

**Read this first.** It bootstraps a session with no prior context. Body below is the
2026-08-17 snapshot. Claims later marked **RETRACTED** or superseded are left in place
with pointers — do not treat unmarked 2026-08-17 prose as current. Standing picture:
**[Amendment 2026-08-31](#amendment-2026-08-31)** at the end of this file.

---

## What this is

SHARC Lab (Georgia Tech, Callie Hao). A design-space exploration study for **hybrid device↔cloud
agentic AI execution** — client silicon as a decision variable, not a fixed constraint. Project
name SEAM.

## The current direction

**Characterize what specific hardware configurations buy inside a hybrid execution model.** Four
configuration axes, measured against cost, latency and local-feasibility on a real agent workload
(BFCL v4).

The output is not "is the hardware fast" but **which configuration lets what fraction of the work
stay local, and what that saves.**

### The four axes

| Axis | Values | Mechanism |
|:--|:--|:--|
| **Device placement** | `cpu-p` · `cpu-p + igpu` · `gpu_only` | `load_sequence` + `generate_device` in `configs/delta_n.yaml` |
| **Residency** | `RESIDENT` · `NON_RESIDENT` | whether session KV survives between turns |
| **Quantization** | `KV_CACHE_PRECISION` ∈ f16 · u8 · u4 | readback must match request or the cell is failed, not measured |
| **Attention window** | under investigation | the Hypothesis B axis — see the 2.30× amplification below. **Status as of 2026-08-31: AXIS 5 BLOCKED (zero cells)** — see [Amendment 2026-08-31](#amendment-2026-08-31). |

**NPU is deferred, deliberately.** Its path requires `NPUW_LLM_PREFILL_CHUNK_SIZE` to work around
openvino#34617, which bounds prefill activation memory *by construction* — that difference would sit
inside any placement comparison at the magnitude being detected. NPU is a follow-up axis, not part
of the current matrix.

## Headline results

### 1. Configurations interact super-additively

`derived/delta_prefill/OPTIMAL_CONFIG_COST.md` · **AM-035 (POST-DATA)**

| Config | % local | Cost | Saving |
|:--|--:|--:|--:|
| default | 0% | $154.42 | — |
| `gpu_only` alone | 25% | — | 7% |
| `gpu_only` + residency | 42% | $130.33 | 16% |

**Cost interaction 2.3× super-additive. Latency interaction 2.4×.**

The latency figure is the stronger of the two — it comes from **measured medians, not fits**, which
is why it survived the AM-035 retraction while the cost interaction moved from a retracted 6× to
2.3×.

Citing runs: `9f38eb15-6fe6-40b4-871b-a02ec5629bb1` (n_cached=4000, 24/24 OK),
`d5c98342-a0b2-41a9-b6e2-93ac7a39c3ba` (n_cached=12000, 17 OK + robustness).

### 2. Local feasibility is governed by session position, not delta size

```
gpu_only:   turn2_prefill_s ~ C · d · n_cached        C = 4.34e-7   (delta-only term ≈ 0)
arm A:      turn2_prefill_s = k(n) · d               k = 0.0166 · (n/4000)^0.70
```

**RETRACTED (2026-08-31):** the `gpu_only` claim `turn2_prefill_s ~ C · d · n_cached` (purely
delta-driven cost ⇒ d1000/d50 = 20 at every context) is **falsified**. Observed d1000/d50
ratios rise with context (~0.74 at n=2,000 → ~3.0 at n=12,000), not 20 (`41e419bd`). See
[Amendment 2026-08-31](#amendment-2026-08-31) § Retracted claims (3). Feasibility table
below remains historically useful as a routing intuition but must not be derived from
that retracted closed form.

Max feasible Δ at a 10 s bound, `gpu_only` + residency:

| `n_cached` | max feasible Δ |
|---:|---:|
| 4,000 | 5,760 |
| 12,000 | 1,920 |
| 27,600 | 834 |

**The same turn with the same delta is feasible early in a session and infeasible late.** That is a
routing rule no latency-based router derives, because the governing quantity is a property of
session position rather than of the step.

### 3. Quantization moves the binding constraint, not just the footprint

| Precision | Ceiling | Failure class | Citing |
|:--|:--|:--|:--|
| f16 (`gpu_only`) | **36,500** | `CL_OUT_OF_RESOURCES` | session `2804d7fa`, `CLOSEOUT_gpu_only.md` |
| u8 (`gpu_only_u8`) | **≥40,000** | `early_exit_position_limit` | arm `29253ddc`, verdict `2d385fa3`, session `37f78cb1` |
| u4 (`gpu_only_u4`) | **pending** | — | DISPATCH O stage 1, prediction recorded, not yet run |

**RETRACTED (2026-08-31) — f16 ceiling label:** the **36,500**-token `CL_OUT_OF_RESOURCES`
ceiling is a **u8** measurement, not a pinned-f16 ceiling. The arm labelled `gpu_only_f16`
never requested `KV_CACHE_PRECISION` and reads back `"dynamic"`; an interleaved equivalence
probe matched it to pinned u8 within 0.1% at three depths. A pinned `gpu_only_f16` arm now
exists; **its ceiling has never been run.** See [Amendment 2026-08-31](#amendment-2026-08-31)
§ Retracted claims (2). Do not cite 36,500 as an f16 result.

**u8 moved the bind from a memory wall to the model's position limit.** ~~That confirms
Hypothesis A (padded / dtype-scaled KV dominates) for u8 and is the sharpest configuration
result so far.~~ **RETRACTED (2026-08-31):** Hypothesis A **confirmed** is retracted — see
PREREGISTRATION amendment 2026-08-23 and [Amendment 2026-08-31](#amendment-2026-08-31)
§ Retracted claims (1). The u8 position-limit outcome remains a measured fact; the Hypothesis A
confirmation does not.

**And it is nearly free in quality:** AST 17/20 (f16), 16/20 (u8), 17/20 (u4).
**(Note, 2026-08-31):** weight-precision quality is no longer "nearly free" — see AXIS 4
QUALITY in [Amendment 2026-08-31](#amendment-2026-08-31) (int4 vs int8 emission reliability).

### 4. The unexplained amplification — the open mechanism

```
peak working-set slope   171.7 KB/token
nominal KV               73.7 KB/token
amplification            2.30×      (matches the 2.33× decode-traffic factor)
```

**Mechanism unknown.** This is the attention-window axis: Hypothesis B says attention/activation
workspace accounts for the excess and does not scale with KV dtype. u4's ceiling is the falsifier —
if u4 dies with `CL_OUT_OF_RESOURCES` below the position limit, workspace re-enters.

## Predictions on record (DISPATCH O, 2026-08-11, pre-launch)

Grid identical for u4/u8/f16: `n_cached` ∈ {2000, 4000, 8000, 12000} × delta ∈ {50, 150, 400, 1000}
× {RESIDENT, NON_RESIDENT} × 3 repeats = 96 cells per precision.

- **P1** — u4 passes the top rung and trips `early_exit_position_limit`, same class as u8.
  *Falsifier:* u4 dies `CL_OUT_OF_RESOURCES` below the position limit.
- **P2** — no material RESIDENT turn-2 improvement from narrowing KV dtype at matched
  (n_cached, delta) within the operating range.
- **P3** — median RESIDENT/NON_RESIDENT ratio **< 0.5** at deltas 50 and 150 for all precisions.

## Blocked, and it is load-bearing

**BFCL competitiveness: `UNKNOWN — BLOCKED_ON_OPERATOR`.** `derived/bfcl_feasibility/REPORT.md`.

**Superseded in part (2026-08-31):** weight-precision BFCL quality is no longer unknown —
sealed 200-entry paired runs `6225d6e1` (int4) / `1d8db970` (int8); see
[Amendment 2026-08-31](#amendment-2026-08-31) § Axis 4 quality. The broader “42% local”
cost-table competitiveness question remains open where those runs do not speak.

The cost table assumes the local model can carry 42% of the work. **If Qwen3-4B's BFCL accuracy is
poor, "42% local" means 42% done badly and the saving is illusory.** ~~No `gpu_only` generations have
run; no accuracy exists. Do not invent one.~~ **RETRACTED as a standing absence claim
(2026-08-31):** generations have run under int4/int8 weight arms (`6225d6e1` / `1d8db970`).
Do not invent numbers beyond those sealed runs.

DryRunGate refused on tier-1 residents (Cursor ~2.3 GiB, chrome ~1.8 GiB, msedge) with
available 5913 MB < 7000 MB required. One clean session unblocks it:

```
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; .\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode run_gpu --out derived\bfcl_feasibility"
```

**Prompt-format divergence, already measured.** BFCL requires the chat-template tools block, which
sealed timing cells do not pass:

| Category | timing mean | bfcl+tools mean | Δ |
|:--|--:|--:|--:|
| simple_python | 30.8 | 229.2 | +198.4 |
| parallel | 46.0 | 254.6 | +208.6 |
| multi_turn_base | 44.2 | 3619.5 | +3575.3 |

**Timing cells and accuracy cells are not currently measuring the same prompt.** Do not silently
adopt tools for timing claims; do not strip tools to rescue scores.

## Retracted — do not cite

- Arm-A **19.45 s** constant at n_cached=12000 — artifact of two points at one cached length (AM-035).
- Cost interaction **6×** — derived under that bad intercept model. The standing figure is **2.3×**.
- Any feasibility bound that ignores `n_cached`.
- Decode figures **15.1 / 7.4 tok/s** and any **29% of bandwidth ceiling** claim. No sealed run
  produces them and **no INT8 weight arm exists at all.**
  **(Update 2026-08-31):** an INT8 weight arm **does** now exist and is sealed (`1d8db970` quality;
  `a784f5ec` timing). The decode 15.1/7.4 and 29% bandwidth claims remain unretracted only as
  “no sealed run produces them,” not as “no INT8 arm.”
- **Hypothesis A confirmed** — RETRACTED; PREREGISTRATION amendment 2026-08-23 /
  [Amendment 2026-08-31](#amendment-2026-08-31).
- **36,500 as an f16 ceiling** — RETRACTED label; measurement is u8 /
  [Amendment 2026-08-31](#amendment-2026-08-31).
- **`turn2 ~ C · d · n_cached`** — FALSIFIED /
  [Amendment 2026-08-31](#amendment-2026-08-31).
- Independence / “multi-turn penalty is arithmetic, not mechanistic” at n=20 — FALSIFIED at
  n=200 (`6225d6e1` / `1d8db970`) — rewrite `docs/README_feasibility.md`.

## Known defect in the matrix harness — fixed, do not backfill

`Get-CellSpecs` scheduled `NON_RESIDENT` only at `max(-Deltas)` while `RESIDENT` ran at every delta.
Residency ratios at small deltas compared a measured RESIDENT cell to a missing or reused peer.
**Real BFCL turn deltas are ~40–350 tokens, not 2000**, so this hit exactly the regime the session
claim cares about. Fixed in `tools/run_delta_prefill_matrix.ps1`. Prior sealed sessions remain valid
for the cells they ran — **do not re-run to backfill, do not rewrite past summaries.**

## Other measured facts, with run_ids

| Fact | Value | Source |
|:--|:--|:--|
| KV geometry | **73,728 B/token, u8** — 2 × 36 × 8 × 128 × 1 byte | `1fd81d2a` device readback |
| Config declares f16 and is **wrong** | using it doubles every capacity figure | same |
| No cross-call prefix reuse | identical greedy output, no speedup; chat mode re-ingests | `6b40e3fe` |
| Unexplained throughput variance | **1.98×** between nominally identical runs, all detectors blind | `d8f0875b` vs `1a0166b9` |
| PDH frequency detection **inert** | nominal clocks; 100% of max during a 4-process burn | `1a0166b9` |
| Router proxy bias | `chars//4` under-counts **77%**; `+621` scaffold → **−1.03%** | `1a0166b9`, AM-027 |
| Core-cluster contrast (provisional) | **1.881×**, interleaved, but confinement **UNCLEAR** | `5eb09eba` |

## Instrument reproducibility — still FAIL

**Superseded in scope (2026-08-31):** the blanket **FAIL** below is retained as the 2026-08-06
record. Timing and consumption have since been shown to reproduce across sessions; the
σ 0.145 / 0.159 FAIL is scoped to **ceiling / headroom** measurements, not the instrument as
a whole. See [Amendment 2026-08-31](#amendment-2026-08-31) § Reproducibility.

Two orchestrated pairs sealed 2026-08-06. Ratio is fine; **spread is not.**

| Pair | Arms | Verdict | Ratio | s | Outlier |
|:--|:--|:--|:--|:--|:--|
| 1 | `b11553d7` / `21c1a2ab` | `9e3ca312` | near 1 | 0.145 | arm1 r0 |
| 2 | `483751fd` / `c3319520` | `09dfe95d` | 1.0133 | 0.159 | arm2 r2 |

**Pass rule: `|ratio − 1| ≤ 2·s` AND `s ≤ 0.10`.** Both pairs fail the second condition.

- **Modern Standby names pair 2, not both.** Kernel-Power 506/507/566 inside the lock window on
  pair 2's outlier; pair 1's outlier has none.
- **`free_physical_bytes_at_peak` varies 1.47×** between arms (2.688 vs 1.824 GB) while
  `peak_working_set` agrees to 1.0002×. Consumption reproduces; **headroom does not** — and a
  ceiling measurement *is* a headroom measurement.
- `pre_run_settle` improved arm1 CV 0.145→0.037 but the dip moved position — sporadic, not positional.
- Charging state differed between pairs; now wired per-repeat, unrecoverable from sealed artifacts.

## Machine setup

**XPS** — Dell XPS 16, Core Ultra 5 325 (Panther Lake), 16 GB soldered, 4 P + 4 LP-E. Canonical
repo, all sealed runs. **IP changes with network — re-check `ipconfig` before assuming `ssh xps`.**

**Mac** — MacBook Pro, remote controller over SSH, PowerShell as remote shell.

**Measurement mode** — `docs/SETUP_remote_measurement.md`. Required for any run whose primary
endpoint is timing or memory, or whose result feeds a comparison. `isolation_mode` recorded in every
manifest and enforced in `seam/isolation.py`: no default, contradicted declarations refused,
`assert_poolable()` refuses cross-mode comparison. **Results from different modes are never pooled.**

**Detachment** — `Start-Process` children die when the SSH session closes (Win32-OpenSSH job object,
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`). Use `tools/spawn_detached.ps1`, which spawns via WMI. Measured
in `tools/_job_teardown_probe.py`: subprocess dead at tick 4, WMI alive through tick 22.

## Commit state

`5ff4e65` landed the amendment reconciliation and `check_amendment_ledgers.py`. **The isolation
build is still untracked** — `seam/isolation.py`, `tools/spawn_detached.ps1`, `tools/acceptance.ps1`,
`tools/verify_detach.ps1` — along with all acceptance and configuration-matrix run directories.
308 untracked overall.

## Operating rules

**R1** timing is not a constraint · **R2** the claim only strengthens · **R3** maximise contribution
yield per session · **R4** protect the main line, additive never displacing.

**Absence-claim rule (Appendix A.2):** no "nobody has done X" enters a pitch, brief, abstract or
paper without a documented search recorded there. Three prior absence claims collapsed.

**Narrative gate (AM-027b):** no quantitative claim leaves the repo without a **run_id at the point
of use.** A number whose run_id cannot be named is withdrawn, not caveated.

**Gates never descope.** Unmet gate → sequence around it, never shrink the comparison.

**Thresholds are derived from baselines and recorded — never chosen to make a run pass.**

**Readback, not request.** A property set is not a property in effect. Precision, affinity,
working-set lock and reserved CPU sets are all verified by readback; mismatch fails the cell.

## Known platform defects — handle, do not rediscover

- NPU + INT8 weight-only IR: accepted at construction, uncatchable `0xC0000005` at `generate()`
  (openvino#35641). Assert INT4 first.
- NPU dynamic shapes (openvino#34617): set `MAX_PROMPT_LEN` and `NPUW_LLM_PREFILL_CHUNK_SIZE`
  explicitly, record both.
- Panther Lake iGPU `CL_INVALID_WORK_GROUP_SIZE` (openvino#34390): per-model smoke test, classify
  `UNSUPPORTED`, never retry-loop.
- OpenVINO `PCORE_ONLY` silently falls through to all cores while `ECORE_ONLY` binds.
- Windows large-file hashing: `read_bytes()` fails above ~2 GB, stream through `sha256_file`.
- Three runs lost to write-path defects **after** measurement completed — circular reference,
  `UnicodeEncodeError`, schema rejection. The startup dry-run must build its object with the **real
  builder**, not a hand-written synthetic.

## Key literature — audited, cite do not compete

[HeteroMosaic 2607.12839](https://arxiv.org/html/2607.12839v3) heterogeneous roofline + device
allocation · [Agent.xpu 2506.24045](https://arxiv.org/abs/2506.24045) NPU/iGPU affinity ·
[MemExplorer 2604.16007](https://arxiv.org/abs/2604.16007) memory+NPU co-design DSE, datacenter ·
[2607.05475](https://arxiv.org/abs/2607.05475) CPUs beat NPUs on decode ·
[2511.22334](https://arxiv.org/pdf/2511.22334) NPUs dominate on EDP — **the literature contradicts
itself here** · [KAIROS 2604.16682](https://arxiv.org/pdf/2604.16682) context outgrowing drain into
thrashing · [Duet Benchmarking 2001.05811](https://arxiv.org/pdf/2001.05811) randomized interleaving
under interference.

**Practitioner baseline to push against:** hybrid routing is widely reported at **60–80% cloud-spend
reduction** — but those analyses assume discrete or large dedicated memory, where the capability
channel does not exist. The measured saving here is **16%** on unified memory.

---

<a id="amendment-2026-08-31"></a>

## Amendment 2026-08-31 — append-only update to the 2026-08-17 body

Doc-only. Does not rewrite the 2026-08-17 text above except where that text is marked
**RETRACTED** / superseded inline with a pointer here. Every number below carries a `run_id`
(or sealed tree hash) at the point of use.

### Retracted claims (evidence that killed each)

**1. Hypothesis A confirmed → RETRACTED.**  
The 2026-08-17 claim that u8’s move to `early_exit_position_limit` “confirms Hypothesis A
(padded / dtype-scaled KV dominates)” is withdrawn. See **PREREGISTRATION amendment
2026-08-23**. The u8 ceiling class itself remains a measured fact (`29253ddc` / `2d385fa3` /
`37f78cb1`); the Hypothesis A confirmation does not.

**2. The f16 ceiling label → RETRACTED as an f16 result.**  
The **36,500**-token `CL_OUT_OF_RESOURCES` ceiling (session `2804d7fa`, `CLOSEOUT_gpu_only.md`)
is a **u8** measurement. The arm labelled `gpu_only_f16` never requested `KV_CACHE_PRECISION`
and reads back `"dynamic"`. An interleaved equivalence probe matched that arm to pinned u8
within **0.1%** at three depths. A pinned `gpu_only_f16` arm now exists; **its ceiling has
never been run.** Do not cite 36,500 as f16 capacity.

**3. `turn2_prefill_s ~ C · d · n_cached` → FALSIFIED.**  
A purely delta-driven cost implies d1000/d50 = **20** at every context. Observed ratios:
about **0.74** at n=2,000 rising to about **3.0** at n=12,000 — not 20 (sealed multi-depth
delta matrix **`41e419bd`**). The closed form in §2 of the 2026-08-17 body must not be used.

### Axis 4 — weight precision

Sealed run **`a784f5ec`**, `tree_sha256`
`0abd0784bd9871dfaf36df27a51af216d86f591fe0f958515a7c4004ec9dcb85`.
36 cells + 4 canaries; both precisions interleaved in one session.

- Weight-byte delta predicted **+1.763 GB**, observed **+1.737 GB** (1.5% off).
- Decode ratio int8:int4 declines monotonically with context
  (**1.508 / 1.496 / 1.339** at n=2000 / 5000 / 12000) — the pre-registered trend **held**.
- All three point predictions **missed**, all below the band, systematically. Implies a
  precision-independent per-step cost the additive weights+KV bandwidth model does not
  capture. Shape right, level wrong.
- Structural result (superseded for KV on Platform A — see amendment
  2026-09-08 below): **weight precision** costs decode and delta-prefill and
  leaves bulk prefill flat. KV no longer framed as "buys capacity" here.

### Axis 4 quality — 200-entry paired BFCL

Sealed runs: int4 **`6225d6e1`**, int8 **`1d8db970`**.

| Arm | Trajectory | Per-turn |
|:--|:--|:--|
| int4 (`6225d6e1`) | 20/200 | 251/732 = **34.3%** |
| int8 (`1d8db970`) | 23/200 | 288/734 = **39.2%** |

- Trajectory McNemar: b=4, c=7, **p=0.55** — **NULL**.
- Tool-call emission: int4 fails to emit a parseable call where int8 succeeds on **32**
  entries; reverse on **7**. OR **4.57** [1.98, 12.27], **p = 7.0e-5**. Mechanism confirmed
  by inspection: the model narrates intent in prose without emitting `<tool_call>`.
- **First configuration axis measured to move quality**, and it moves **emission
  reliability** specifically, not task competence.
- Per-turn McNemar (b=17, c=53, **p=1.9e-5**) is confounded by state cascade after
  divergence — recorded as **suggestive only**.

### Corrections to `docs/README_feasibility.md` — 20-entry prefix was not representative

Rewrite that README; do not soften.

- Per-turn **44.1% → 34.3%** (int4 full set `6225d6e1`); the pilot lies outside the full-set
  95% CI.
- `force_terminated` overrepresented ~**18×** in the prefix (10% vs 0.56%).
- The **independence model fails at n=200** on both arms: predicted trajectory
  **2.0% / 3.2%**, observed **10.0% / 11.5%** (~**+8 pp** excess). The claim that the
  multi-turn penalty is “arithmetic, not mechanistic” held at n=20 and is **falsified at
  n=200**. Entry-level heterogeneity is the explanation.

### Quality instrument — audited 2026-08-30, PASSED

- **No truncation:** 180 steps, zero at or near the 512 cap; max 272, mean 59.9. Moots
  `enable_thinking` empirically for this instrument.
- **Parser correct:** `findall` over the official QwenFCHandler pattern plus a loose
  fallback; multi-call generations handled.
- **Entry population unbiased:** plain `questions[:n]` prefix — no difficulty or API filter.
- **Execution path proven by the failure mode:** `instance_state_mismatch` is unreachable
  unless template, parsing, execution, and turn handling all work.
- **Failure mechanism:** on `force_terminated` entries the model restates a tool error
  correctly in prose and then re-emits the identical failing call for **21** consecutive
  steps. No error-driven adaptation. This is a mechanism for “failure is capability, not
  context,” which previously rested only on flat hazard.

### Reproducibility — sharpened (supersedes the blanket FAIL)

- Canary cell (`gpu_only_u8`, nc=4000, d=400, RESIDENT): W-2 calibrated
  `ref_t1 = 2.819416 s`; N-1 attempt 2026-08-31 measured **2.820283 s**
  (session `c4ddfd55-f64f-4c72-842c-a6470daaf5ca` canary series). **26 hours and four
  reboots** apart; agree to **0.03%**.
- `peak_working_set` reproduces to **1.0002×**; `free_physical_bytes_at_peak` varies
  **1.47×** (same contrast as the 2026-08-06 pairs).
- Therefore: **TIMING** and **CONSUMPTION** reproduce. **HEADROOM** does not. Ceilings are
  the only measurement that depends on headroom, so the σ **0.145 / 0.159** FAIL
  (`9e3ca312` / `09dfe95d`) is scoped to **ceiling** measurements, not to the instrument
  as a whole.

### Axis 5 — attention window: BLOCKED, zero cells

The CB path now generates (token gate passes: **8** tokens, non-empty —
`derived/delta_prefill/cb_token_gate_attempt.json`). Equivalence design is pre-registered
(`derived/delta_prefill/N1_CB_EQUIVALENCE_PREDICTION.md`). Four separate PowerShell
orchestration failures on the CB matrix:

1. `ConvertTo-Json` walking ETS metadata from `Get-Content -Raw` (~**9.4 GB** leak;
   session `aa9e601a` class).
2. Null exit-code capture → false abort on a passing canary.
3. CB `generate()` called with a list where it requires a scalar (fixed; gate passes).
4. Pipeline return-type check throwing on `PSCustomObject` (`SeamPsCommon.ps1:77`).

Plumbing, not science — but the axis has **no data**. Salvage of incomplete session
`c4ddfd55-f64f-4c72-842c-a6470daaf5ca` is labelled PRELIMINARY / INCOMPLETE and does not
settle corpus reuse.

### Platform A — degradation

Clean-boot available memory has drifted from **10,047 MB** to **8,844 MB** over one week
with no single culprit. On a long-uptime host, inter-cell available settled at ~**6.4 GB**,
below the **7,000 MB** floor (`c4ddfd55`); a fresh reboot restored **9,615 MB**. The floor
was derived when the machine could reach ~10 GB clean (`delta_n.yaml`
`pre_run_available_mb_min` citation). **Do not lower it.** Either the cell set shrinks and
the floor is re-derived from that, or T2 commissioning moves onto the critical path.

### Environment — WorkloadsSessionHost

`WorkloadsSessionHost` costs ~**2.18 GB** and respawns within ~**4 minutes** of a
kill (X-2 cell 1; earlier ~10–15 min notes are superseded for watchdog sizing).
A **300 s** watchdog loses that race even when the sibling stays alive. See
`docs/ENV_CHANGELOG.md` (2026-09-01). Launchers still record kills in
`watchdog_kills.jsonl`; durable Appx / IFEO changes are not applied yet.

### SD-001

Run **`41e419bd`** records no `model_spec` or `ir_sha256`. Within-matrix KV comparisons are
unaffected; cross-run claims must cite the reconstruction, which rests on per-cell
`model_id` rather than commit archaeology.

### Still unbuilt

Six characterized axes are measured curves. `tools/fdr_replay.py` (D-1) rebuilds
the design-space replay over the 48-point factorial; outputs under
`derived/d1_replay/`.


---

<a id="amendment-2026-09-08-c2"></a>

## Amendment 2026-09-08 — Axis 3 reframed after C-1 / C-2

Doc-only relative to sealed C-2. Numbers cite `run_id` / seal tree.

**Sealed C-2** `62395fdb-1899-415f-b708-6adc81a24dda` —
`derived/c2_ttft/sealed_62395fdb-1899-415f-b708-6adc81a24dda/`,
`tree_sha256`
`95cc9d5c28fc87dcefd7c990ab216854997c5fffdf2b8212d6173173da25ae0c`.

**Withdrawn framing.** "KV precision buys capacity / context" on Platform A.

**Replacement.** KV precision moves **memory footprint** and nothing else
measurable on this platform:

| claim | evidence |
|:--|:--|
| Cold-start TTFT limit identical at **10,000** for f16 / u8 / u4 | C-2 `62395fdb` (AM-038 held, span 0) |
| No hard memory ceiling | C-1 `83127e1b`: f16 completed n=44,742 with Available 0.0 MB via paging |
| Quality uninformative at n=20 | `41e419bd`: 17 / 16 / 17; MDE ~24 points |
| Workload max context **7,743** = **77%** of cold-start TTFT limit | vs C-2 limit 10,000 |

Turn-2 delta-prefill still shows a 15–27% f16 advantage (`41e419bd` Finding 2);
that is not a cold-start capability axis and is not folded into C-2
(`separate_experiment_not_c2`).

**C-2 unguarded note.** Session `62395fdb` ran without a drift canary
(ttft_slo path had none). See
`derived/c2_ttft/NOTE_62395fdb_unguarded.md`. INF-1 closes that for CAP-1–3.

