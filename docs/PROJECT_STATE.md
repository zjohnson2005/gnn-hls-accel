# Project state — handoff document

**Read this first.** It bootstraps a session with no prior context. Current as of 2026-08-06.

---

## What this is

SHARC Lab (Georgia Tech, Callie Hao). A design-space exploration study for **hybrid device↔cloud
agentic AI execution** — treating client silicon as a decision variable rather than a fixed
constraint. Project name SEAM.

**SEAM as a whole is on the back burner.** The current focus is one narrow claim that can stand
alone.

## The current angle — the only thing being worked

> **On unified memory, enabling a compute backend reserves memory that context needs. So the
> routing action space includes hardware state, not just target assignment. Turning a backend off
> is how you make room for context.**

Every router in the surveyed literature assigns work to targets. None changes the target set at
runtime to convert compute into capacity. That is the gap.

**The one measurement that decides it:** `ΔN = max_context(cpu-p) − max_context(cpu-p + igpu)`,
in tokens. Spec: `docs/CURSOR_PROMPT_delta_n.md`.

**Materiality, pre-registered:**

- **Detectable** — `ΔN ≥ 2 ×` the A/A spread, measured not assumed.
- **Consequential** — the band `[ceiling(B), ceiling(A)]` intersects **[5,000, 32,000] tokens**.
  Lower bound from observed pilot peaks (5,105–9,114); upper from real agent operating points
  (LangChain DeepAgents offloads at 20K), capped under the model's 40,960 position limit.

**Decisive early exit:** measure `ceiling(A)` alone first. **If it is ≥ 40,960, memory never binds
on this model — the position limit does — and the line is dead.** Under isolation with ~8 GB free
this is a live possibility, since KV at 40,960 is 3.02 GB against a 2.6 GB model.

**iGPU not NPU** for the primary comparison: the NPU requires `NPUW_LLM_PREFILL_CHUNK_SIZE` to work
around openvino#34617, which bounds prefill activation memory by construction and confounds the
comparison at the magnitude being detected.

## What is dead — do not revive

E-FILTER (escalation filter / over-provisioning), E-ATTRIB (latency decomposition), the A2/A3/A4
throughput-integrity chain, E-CAP, E-NET, D1/D2. Their infrastructure — run lifecycle, sealing,
paging telemetry, canary, machine lock — is retained and reused.

`docs/EXPERIMENT_toggle.md` is a **draft, not a registration.**

## Measured facts, with run_ids

| Fact | Value | Source |
|:--|:--|:--|
| KV cache geometry | **73,728 B/token, u8** — 2 × 36 layers × 8 KV heads × 128 dim × 1 byte | `1fd81d2a` device readback |
| Config declares f16 and is **wrong** | using it doubles every capacity figure | same |
| No cross-call prefix reuse | identical greedy output, **no** speedup; chat mode re-ingests | `6b40e3fe` |
| Practical context ceiling (contended) | ~9,100 tokens vs **40,960** architectural | `0fe5e4c7` |
| Binding resource is **prefill activation memory**, not KV | at 9,114 tokens KV is 672 MB against 2.6 GB model | same |
| Unexplained throughput variance | **1.98×** between nominally identical runs, all detectors blind | `d8f0875b` vs `1a0166b9` |
| PDH frequency detection is **inert** | nominal clocks; 100% of max during a 4-process burn | `1a0166b9` |
| Router proxy bias | `chars//4` under-counts **77%**; `+621` scaffold correction → **−1.03%** | `1a0166b9`, AM-027 |
| Core-cluster contrast (provisional) | **1.881×**, interleaved and randomized, but confinement **UNCLEAR** | `5eb09eba` |

**Withdrawn:** decode figures of 15.1 / 7.4 tok/s and any "29% of bandwidth ceiling" claim. No
sealed run produces them, and **no INT8 arm exists at all.** The quantization framing built on them
is gone.

## Machine setup

**XPS** — Dell XPS 16, Intel Core Ultra 5 325 (Panther Lake), 16 GB soldered, 4 P-cores + 4 LP-E.
Canonical repo, all sealed runs. Hostname `computadora`, `192.168.1.217`.

**Mac** — MacBook Pro. Remote controller via SSH (`ssh xps`), key auth, PowerShell as remote shell.

**Measurement mode** — a mode, not a reconfiguration. See `docs/SETUP_remote_measurement.md`.
Required for any run whose primary endpoint is timing or memory, or whose result feeds a
comparison. `isolation_mode` is recorded in every manifest; **results from different modes are
never pooled or compared.**

**Acceptance test not yet run:** one fixed-config run, wait 20 minutes, run again, report the
ratio. **1.98× is the number to beat.** ΔN does not start until this comes back near 1.0.

## Open blockers

**Amendment identifier collision — resolved 2026-08-06.** Blueprint §14 retains AM-025
(absence-claim / stratification) and AM-027 (router proxy / narrative gate) on sealed-usage
grounds. The prior `AMENDMENTS.md` definitions were tombstoned and reissued as **AM-033**
(Operating mode R1–R4) and **AM-034** (dependency graph / yield queue / gates never descope).
`tools/hooks/check_amendment_ledgers.py` now fails the commit if both ledgers define the same
living identifier with divergent content.

**Gates.** `noise_floor_present` false, M3 partial, no A/A control, all gates unmet. The ceiling
measurement's own repeat structure serves as its A/A — run `cpu-p` twice as separate arms.

**M4 partial** — iGPU and NPU paths never exercised. Required for ΔN.

## Operating rules

**R1** timing is not a constraint. **R2** the claim only strengthens. **R3** maximise contribution
yield per session. **R4** protect the main line — additive, never displacing.

**Absence-claim rule (blueprint Appendix A.2):** no claim that "nobody has done X" enters a pitch,
brief, abstract or paper without a documented search recorded in Appendix A.2. Three prior
absence claims collapsed under searches that should have preceded them.

**Narrative gate (AM-027b):** no quantitative claim leaves the repository without a **run_id
attached at the point of use.** A number whose run_id cannot be named is withdrawn, not caveated.

**Gates never descope.** The response to an unmet gate is to sequence, never to shrink the
comparison.

**Thresholds are derived from baselines and recorded — never chosen to make a run pass.**

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
itself here** · [2603.23640](https://arxiv.org/html/2603.23640v2) sustained-load thermal ·
[KAIROS 2604.16682](https://arxiv.org/pdf/2604.16682) context outgrowing drain into thrashing ·
[Duet Benchmarking 2001.05811](https://arxiv.org/pdf/2001.05811) randomized interleaving under
interference.

**Practitioner baseline to push against:** hybrid routing is widely reported at **60–80% cloud-spend
reduction** — but every such analysis assumes discrete or large dedicated memory, where the
capability channel does not exist.
