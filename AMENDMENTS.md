# AMENDMENTS.md — SEAM

Deviations from the governing protocol, recorded per `docs/SEAM_research_blueprint.md` §14.2.
Every entry states the date, what changed, why, and **whether the decision was made before or
after seeing relevant data**. Post-hoc amendments are permitted but must be labelled as such.

**Precedence rule.** `docs/SEAM_research_blueprint.md` is the governing document.
`docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md` implements it. **On conflict, the blueprint governs.**
Divergences are recorded here rather than silently resolved in one direction.

**Status vocabulary:** `RESOLVED` (a decision is made and implemented) · `OPEN` (needs a human
decision) · `DEFERRED` (belongs to a later milestone).

| ID | Date | Scope | Summary | Status |
|---|---|---|---|---|
| AM-001 | 2026-07-29 | AF-001 | Mislabel occurs twice, not once | RESOLVED |
| AM-002 | 2026-07-29 | Blueprint §16 | Duplicate section numbers §16.2/§16.3 | RESOLVED (2026-07-30, as-delivered SHA `11da7b34…`) |
| AM-003 | 2026-07-29 | §5.2 vs §6.1 | Spec's manifest schema drops blueprint-required fields | RESOLVED (union) |
| AM-004 | 2026-07-29 | §16.6 vs §3.2 | **Energy acceptance criteria directly conflict** | RESOLVED (2026-07-30, PRE-DATA, Z. Johnson) |
| AM-005 | 2026-07-29 | Spec §2 | Repo layout: `seam/` is both root and package | RESOLVED |
| AM-006 | 2026-07-29 | Thermal | §5.4 constants unknown at M1; manifest needs nulls | RESOLVED |
| AM-007 | 2026-07-29 | Source docs | Source folder holds four documents, not three | RESOLVED (2026-07-30, hybrid ingested) |
| AM-008 | 2026-07-29 | M1 | Topology cannot be verified — no shell | RESOLVED (2026-07-30, `a3d2323`) |
| AM-009 | 2026-07-29 | Doc ingest | Governing docs transcribed, not byte-copied | RESOLVED (2026-07-30, hashes pinned) |
| AM-010 | 2026-07-29 | §6.1 manifest schema | Refused topology verification must emit a manifest (AF-006) | RESOLVED |
| AM-011 | — | — | *Identifier deliberately unused* (incoming blueprint raw/-policy renumbered to AM-014) | N/A |
| AM-012 | 2026-07-30 | M1 topology gate | Run-to-run agreement is a **relative**-difference criterion | RESOLVED (2026-07-30, POST-DATA, Z. Johnson) |
| AM-013 | 2026-07-30 | M1 topology gate | Agreement is assessed among **settled-charge** runs only | RESOLVED (2026-07-30, POST-DATA, Z. Johnson) |
| AM-014 | 2026-07-30 | raw/ retention | Threshold-based raw/ commit policy (100 MB ceiling) | RESOLVED (PRE-DATA w.r.t. M2) |
| AM-015 | 2026-07-30 | process | From M2 onward, acceptance criteria are pre-registered before data collection | RESOLVED (PRE-DATA) |
| AM-016 | 2026-07-30 | §3.7 | Pinned profiles by measurement class (`ac-pinned` / `battery-pinned`) | RESOLVED (PRE-DATA w.r.t. M2) |
| AM-017 | 2026-07-30 | §7 M2.1 / §10 OQ2 | S1 battery-counter characterization; profile bounds + OQ2 closed | RESOLVED (POST-DATA) |
| AM-018 | 2026-07-30 | §3.2 S1 estimator | Commit `ΔRemainingCapacity` as sole S1 energy estimator for M2.5 | RESOLVED (**PRE-DATA w.r.t. M2.5**) |
| AM-019 | 2026-08-02 | §7 milestones | Dependency graph replaces linear M0→M6 chain; M2=CERTIFY RAPL; M-SLICE | RESOLVED (**PRE-DATA w.r.t. H1–H4**) |
| AM-020 | 2026-08-02 | §7 M3.2 | Model pinning is provider convention, not dated alias | RESOLVED (**PRE-DATA**) |
| AM-021 | 2026-08-02 | H1 metrics | Cross-model token deltas invalid (tokenizer hazard) | RESOLVED (**PRE-DATA**) |
| AM-022 | 2026-08-02 | M-SLICE | Predictive deadline policy pre-registration | RESOLVED (**PRE-DATA**; n_out_pred wording amended by AM-024) |
| AM-023 | 2026-08-02 | §5.3 | Pre-converted IR allowed; manifest must discriminate provenance | RESOLVED (**PRE-DATA**) |
| AM-024 | 2026-08-02 | M-SLICE | Reasoning mode is an explicit two-arm axis | RESOLVED (**PRE-DATA**) |
| AM-025 | 2026-08-02 | Blueprint §0 | TOMBSTONE → AM-033 (Operating mode R1–R4); Blueprint §14 definition retained | RETIRED (tombstone) |
| AM-026 | 2026-08-02 | Blueprint v2.0 | Withdrawals: staged energy, two-paper split, deferred axes | RESOLVED (**PRE-DATA**) |
| AM-027 | 2026-08-02 | §8 / §10 | TOMBSTONE → AM-034 (Structural / yield / gates); Blueprint §14 definition retained | RETIRED (tombstone) |
| AM-028 | 2026-08-02 | §5 | New hypotheses H8–H12 | RESOLVED (**PRE-DATA**) |
| AM-029 | 2026-08-02 | §2.2 | Time-varying coordinate θ(t) — thermal as evolving state | RESOLVED (**PRE-DATA**) |
| AM-030 | 2026-08-02 | §6.4–§6.8 | Mutual exclusion; external verification; cross-boundary confounds; thermal dual regime | RESOLVED (**PRE-DATA**) |
| AM-031 | 2026-08-02 | Pins | Blueprint pin 373f8e25… (v2.0); ffe34980… archived as v1.0-final | RESOLVED (**PRE-DATA**) |
| AM-032 | 2026-08-04 | E-FILTER C2 | Withdraw 8 s headline deadline | RESOLVED (**PRE-DATA**) |
| AM-033 | 2026-08-02 | Blueprint §0 | Operating mode R1–R4 replaces deadline-driven protocol (reissued from AM-025) | RESOLVED (**PRE-DATA** w.r.t. every hypothesis) |
| AM-034 | 2026-08-02 | §8 / §10 | Dependency graph + yield queue; gates never reduce scope (reissued from AM-027) | RESOLVED (**PRE-DATA**) |
| AM-035 | 2026-08-10 | delta-prefill model | Measured turn-2 form; retract arm-A 19.45 s constant | RESOLVED (**POST-DATA**) |
| AM-036 | 2026-08-10 | §5.2 / manifest | Separate measurement vs promote-time power_state; refuse retro-seal leak | RESOLVED (**POST-DATA**) |
| AM-037 | 2026-09-08 | C-1 ceiling | Position limit not enforced; no hard memory ceiling on 16 GB host | RESOLVED (**POST-DATA**) |
| AM-038 | 2026-09-08 | C-2 pre-reg | Withdraw f16>u8≥u4 TTFT order; replace with turn-1 agreement | RESOLVED (**POST-DATA**; held on `62395fdb`) |
| AM-039 | 2026-09-12 | git history | Filter-repo strip of oversized blobs; SHA map in `docs/GIT_SHA_MAP.md` | RESOLVED (**PRE-DATA** w.r.t. sealed evidence bytes) |
| AM-040 | 2026-09-15 | §5.2 / manifest | INF-5 `run_environment` required on `spec_version` 1.1 seals | RESOLVED (**PRE-DATA**) |

---

## AM-001 — AF-001's mislabel occurs twice, not once

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** RESOLVED

**Divergence.** Blueprint Appendix B / AF-001 and spec §7/M0 item 1 both localise the mislabel
to `analysis/aipc-c1/MACHINE.md` **line 12**. It occurs in two places:

- line 12 (Identity table) — `Intel(R) Core(TM) Ultra 5 325 (Lunar Lake)`
- line 24 (Memory table) — `On-package LPDDR5X (Lunar Lake memory-side cache / UMA)`

**Decision.** Both corrected. Correcting only line 12 would satisfy the letter of AF-001 while
leaving a wrong generation label in the document that §5.2 designates as the manifest provenance
source — the exact failure AF-001 exists to prevent.

**Why it matters beyond a typo.** The line-24 text attributes the *memory-side cache
architecture* to the wrong generation. Panther Lake and Lunar Lake differ in memory subsystem
organisation, so this is a technical claim, not just a name.

**Rationale for logging rather than silently fixing.** The correction is a superset of what the
governing document authorises, and spec §9.1 makes `analysis/` read-only with M0 as the single
exception. Widening that exception is recorded.

---

## AM-002 — Blueprint §16 has duplicate section numbers

**Date opened:** 2026-07-29 · **Date resolved:** 2026-07-30 · **Pre/post data:** Pre ·
**Status:** RESOLVED

**Divergence.** Commit `13284ef` restored a blueprint predating the AM-002 renumber, so `§16`
had two `16.2` and two `16.3` subsections and no `§16.9`. Cross-references (P-1.10, P-1.15) were
ambiguous.

**Resolution.** Human-placed corrected blueprint verified as-delivered:

| Document | Bytes | Lines | SHA-256 (as-delivered) |
|---|---:|---:|---|
| `docs/SEAM_research_blueprint.md` | 61725 | 744 | `11da7b34936522fc37531f1321d7150f7f3788da6de6cce0f7472e6a92ef4cfd` |

§16 now reads **16.1–16.9 sequential with no duplicates**; §16.9 (topology/power-pinning note)
is present. The blueprint's own §14 amendment log records AM-002 RESOLVED. This file cites the
**as-delivered** SHA above; subsequent governance-pass edits (AM-014 renumber in the blueprint)
produce a new standing pin recorded under AM-009.

---

## AM-003 — Spec §6.1's manifest schema omits blueprint §5.2 required fields

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** RESOLVED (implemented as a union)

**Divergence.** Spec §6.1 is introduced as "Add these Platform-A fields to the blueprint's
schema," implying a superset of §5.2. It is not a superset. These blueprint-required fields have
no counterpart in the spec's schema:

| Blueprint §5.2 field | Present in spec §6.1? | Why it matters |
|---|---|---|
| `platform.microcode` | No | Microcode revision changes performance; required for reproducibility |
| `platform.bios_version` | No | Recorded in MACHINE.md (`1.8.2`) but not carried into manifests |
| `platform.kernel` | No | OS build is present; kernel/UBR is not |
| `platform.power_cap_w` | No | **M5 sweeps power caps at 15/25/55 W.** Without this field a sweep cell is not identifiable |
| `platform.cpu_governor` | Partially | `power_state.power_plan` is the Windows analogue |
| `thermal.ambient_c_start` / `ambient_c_end` | Collapsed to one `ambient_c` | §5.4 item 1 wants ambient logged; two endpoints detect ambient drift within a run, one does not |
| `thermal.pkg_temp_series_path` | No | §5.4 item 4 mandates a ≥1 Hz temperature series; the path must be in the manifest |
| `thermal.throttle_events` (count) | Replaced by `throttle_residency_pct` | Residency is the better exclusion criterion, but the event count is separately required by §5.2 |
| `models.cloud.{provider, model_snapshot_id, access_date, pricing_table_version}` | **No** | **Most serious.** `target` may be `"cloud"`, and M3.2/M6 mandate pinned dated snapshots and versioned pricing. The spec's single `model` block cannot describe a cloud run |
| `policy.{name, version, params}` | No | The partition policy under test — the independent variable for H2/H3 |
| `network.{regime_name, measured_rtt_ms_p50/p95, measured_bw_mbps, shaping_rule}` | No | Required by §9.3; cloud latency is uninterpretable without it |
| `outputs.token_ledger_path` | No | M3.2 mandates a token/cost ledger |

**Decision.** Implemented as a **union**, not a choice:

1. Every field enumerated in the Phase −1 task specification is **required** and validated
   exactly as given. That set is the M0/M1 contract.
2. Every blueprint §5.2 field absent from it is added as **optional and nullable**, defaulting to
   `null`, so a blueprint requirement is never silently dropped. Later milestones populate them.
3. The schema is `additionalProperties: false` at the top level, so a field cannot be introduced
   without a schema change and an entry here.

**Rationale.** Blueprint governs, so its fields must exist. The spec's field list is what M1's
acceptance criterion is written against, so those must validate exactly. A union satisfies both.
Making the blueprint extras nullable rather than required is the only honest option at M1 —
`microcode`, `power_cap_w`, and the thermal constants are genuinely unknown until M2, and
populating them with plausible defaults would fabricate provenance.

**Deferred obligation.** Before M3 the `model` block must be widened to carry a cloud snapshot
sub-block, and `policy`/`network` must become required for any run with `target: "cloud"`.
Recorded as DEFERRED here so it is not lost.

---

## AM-004 — Energy acceptance criteria conflict between blueprint Gate −1 and spec §3.2

**Date opened:** 2026-07-29 · **Date resolved:** 2026-07-30 · **Pre/post data:** **PRE** ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson

**Divergence (historical).** These two requirements were mutually incompatible, and both were
normative:

> **Blueprint §16.6, Gate −1 (original):** "RAPL and battery-discharge energy **agree within 15%**
> under sustained load."

> **Blueprint §11 Gate G0 (original energy clause):** "harness energy agrees with wall meter
> within 10%."

> **Spec §3.2 item 5 (original):** "**Do not require agreement within a fixed percentage**" —
> require $R^2 \ge 0.95$ with reported slope and intercept.

**Owner ruling (Z. Johnson, PRE-DATA).** The gate document was wrong. The RAPL package domain is
a strict **subset** of platform electrical draw (excludes display, SSD, WiFi, EC, fans, VRM, and
possibly DRAM). It cannot converge to a fixed 15% (or 10%) agreement with battery-discharge /
wall-meter energy; at idle the ratio is often 3–5×. A %-agreement gate fails for correct
instrumentation and would reward mis-attribution of baseline power into the SoC term.

**Resolved criterion** (applied to blueprint §16.6 Gate −1, §11 G0 energy clause, and Phase −1
spec §3.2 steps 5–6 / M2.5):

1. **Linearity:** $R^2 \ge 0.95$ across ≥8 load levels spanning idle→turbo.
2. **Slope:** $\in [1.0,\ 1.5]$. Slope $< 1.0$ is a **HARD FAILURE** (subset cannot grow faster
   than the whole).
3. **Intercept:** consistent with an independently measured idle baseline, validated by
   differencing two display-brightness levels.
4. **Per execution target:** fit regressions separately for `cpu-p`, `cpu-lpe`, `igpu`, and
   `npu` — **not pooled**. Target-dependent slope reveals RAPL domain-coverage gaps (e.g. higher
   slope under NPU-heavy load ⇒ RAPL missing NPU power).
5. **Resolution:** report the minimum resolvable energy difference **per target**.
6. Emit `derived/energy_calibration.json` with the per-target fields above.

Failure response unchanged: investigate attribution; add an explicit error term before any
energy claim. **No energy / M2 code was written as part of this resolution.**

---

## AM-005 — Repository layout: `seam/` is both repository root and package directory

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** RESOLVED

**Divergence.** Spec §2's tree is rooted at `seam/` and contains a nested `seam/` package
alongside `docs/`, `analysis/`, `configs/`, `raw/`, `derived/`, `figures/`, `tests/`,
`tools/lhm_bridge/`. Read literally that gives `seam/seam/manifest.py`. This repository
(`gnn-hls-accel`) is also **not** a SEAM-only repo — it already contains the unrelated
`apu_characterization/`, `censor/`, and `orchestration_engine/` projects.

**Decision.** The outer `seam/` in spec §2 is read as "the repository root," not a directory.
The SEAM tree is placed at the existing repository root: package at `seam/`, with `configs/`,
`raw/`, `derived/`, `figures/`, `tests/`, `AUDIT_LOG.md`, `AMENDMENTS.md` as siblings. Existing
unrelated projects are untouched. Module paths in the spec (`seam/manifest.py`,
`seam/topology.py`) therefore resolve exactly as written.

**Consequence.** `tests/` at the repository root is SEAM-only; `apu_characterization/tests/` and
`censor/tests/` are separate suites. Pytest scoping must be explicit (`pytest tests/`) so the
SEAM suite is not conflated with the pre-existing ones, whose pass state is not SEAM's
responsibility.

**Scope note.** Only the subtrees M0/M1 require were created. The spec §2 directories belonging
to later milestones (`seam/telemetry/`, `seam/backends/`, `seam/agent/`, `seam/bench/`,
`seam/analysis/`, `tools/lhm_bridge/`, `configs/models/`, `configs/benchmarks/`,
`configs/sweeps/`) were **deliberately not stubbed**, to avoid empty modules that look
implemented.

---

## AM-006 — §5.4 thermal constants are undetermined at M1

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** RESOLVED

**Divergence.** Spec §6.1 shows the `thermal` block fully populated
(`warmup_s: 120`, `cooldown_ceiling_c: 55`, `throttle_threshold_pct: 5.0`, `ambient_c: 22.5`),
but §3.3 and blueprint §5.4 require these to be **determined empirically in M2.3** and only then
frozen. At M1 they do not exist.

**Decision.** The illustrative values in §6.1 are treated as **examples, not defaults**. They are
**not** written into `configs/platforms/aipc-c1.yaml`. The config carries the thermal block with
`null` values and an explicit `determined_by: M2.3` marker; the schema permits `null` for each.
`thermal.excluded` defaults to `false` since no exclusion can be asserted without a threshold.

**Rationale.** Spec §8 forbids magic numbers in code, and §9.2 forbids numbers without a
traceable manifest ID. Copying `warmup_s: 120` from a schema illustration into a platform config
would create exactly such an untraceable number, and it would look measured. A `null` that fails
loudly at M2 is correct; a plausible number that silently propagates is not.

---

## AM-007 — Source document folder contains four documents, not three

**Date opened:** 2026-07-29 · **Date resolved:** 2026-07-30 · **Pre/post data:** Pre ·
**Status:** RESOLVED

**Divergence.** The Phase −1 task specification stated the source folder holds "exactly three
files." It contained **four**:

- `SEAM_research_blueprint.md`
- `PHASE_MINUS1_IMPLEMENTATION_SPEC.md`
- `CURSOR_KICKOFF_PROMPT.md`
- `hybrid_execution_dse_positioning.md`

**Decision (2026-07-30).** Owner authorized ingest. Copied verbatim to
`docs/hybrid_execution_dse_positioning.md`
(SHA-256 `ceec363af8a55269a370b63f80473f0cb00f757741be83fa054f56fb7c67d410`).

**Phase −1 impact.** The hybrid doc imposes **positioning / claim-scope** constraints, not
measurement-harness gates:

1. Client-side (not datacenter) framing is a hard requirement — already aligned with blueprint
   §1.3 / R7.
2. Soften the five-objective novelty claim: claim the *combination* and scope, not the machinery
   (QEIL v2 already has quality/energy/latency). Affects P-1.7 related-work and thesis wording.
3. Routing-amortization bound reframes the hardware question; no change to M0–M2 acceptance
   criteria.

No new Phase −1 measurement AM entries required. Blueprint §2's collision-map reference now
resolves inside the repository. Not added to `configs/platforms/aipc-c1.yaml`
`provenance_artifacts` — that list is for probe/identity artifacts hashed at emit time, not
source positioning docs.

---

## AM-008 — Topology verification could not be executed

**Date opened:** 2026-07-29 · **Date resolved:** 2026-07-30 · **Pre/post data:** Pre ·
**Status:** **RESOLVED** — mapping measured and committed in `a3d23236998e00375c533f3e02561fbb6f457804`

**Divergence.** Spec §4 and M1's acceptance criterion require the P/LP-E split to be verified
empirically and the verified mapping committed to `configs/platforms/aipc-c1.yaml`. The shell
backend was non-functional for the entire session (`AUDIT_LOG.md` AF-003), so no microbenchmark
ran on real silicon.

**Decision.** The verification is **implemented but unexecuted**, and the unverified state is
made explicit rather than papered over:

- `configs/platforms/aipc-c1.yaml` ships `topology.verified: false` with `p_cpus: null` and
  `lpe_cpus: null`.
- `topology.affinity_for()` raises `TopologyNotVerifiedError` when config is unverified, unless a
  caller passes an explicit waiver, which is logged as a structured event.
- The expected 4/4 split is recorded under `topology.expected` as a **hypothesis to test**, in a
  separate key from the measured result, so an expectation can never be mistaken for a
  measurement.

**Rationale.** Writing `p_cpus: [0,1,2,3]` with `verified: true` would have produced a
green-looking M1 while fabricating the single result M1 exists to establish. The plausible guess
is the dangerous outcome here, not the missing one: spec §4 warns specifically against trusting
`EfficiencyClass` ordering, and open question 4 asks whether that ordering matches measurement —
guessing the mapping would silently answer that question with an assumption.

**Required action.** Run `python -m seam.topology verify --write` on the target hardware. This
also answers **open question 4** (spec §10). Until then M1 is not accepted and M2 must not begin.

### Resolution (2026-07-30) — commit `a3d23236998e00375c533f3e02561fbb6f457804`

`python -m seam.topology verify --write` ran on Platform A under pinned AC conditions. The committed
mapping is **`p_cpus: [0, 1, 2, 3]`, `lpe_cpus: [4, 5, 6, 7]`, `verified: true`**, citing run
**`fb5cd2d5-e850-4de1-9b90-d368b5aa9994`** — separation **1.380460703128493×** against a
pre-registered prediction of > 1.30883×, within-cluster CV 0.0242 / 0.0051,
`efficiency_class_ordering_matched: true`. That run was **pre-declared** as the citing run in
`AUDIT_LOG.md` and committed as such in `282241a` before it was taken, then evaluated once with no
re-rolling. Five independent AC runs agree on the membership. Full results, the criteria checklist,
and the series are in `AUDIT_LOG.md` under "Citing run `fb5cd2d5`".

**Open question 4 is closed with it**: on Platform A, higher `EfficiencyClass` = faster core, matched
in all five runs. Scoped to Platform A only — it does not license inferring the mapping elsewhere.

**What the resolution did not do.** No verification threshold was adjusted (1.25 / 0.15 /
`require_expected_split: true` are byte-unchanged), the measured block is still stored separately from
the `topology.expected` hypothesis, and `affinity_for()` still refuses on any config that is not
verified — now tested against an explicit unverified fixture rather than incidentally against the real
config. The tripwire that guarded this amendment was **strengthened rather than retired**: the
committed `run_id` is pinned by name, and the split is re-derived from the committed per-CPU scores
with the production clustering function, so `verified: true` cannot be hand-written without
fabricating a measurement that actually clusters. See `AUDIT_LOG.md`, "how its protective purpose
survives".

---

## AM-009 — Governing documents were transcribed, not byte-copied

**Date opened:** 2026-07-29 · **Date resolved:** 2026-07-30 · **Pre/post data:** Pre ·
**Status:** RESOLVED (hashes pinned; blueprint restored from source)

**Divergence.** The ingest instruction was to copy source documents into `docs/` **verbatim**.
With the shell backend dead (AF-003), the 2026-07-29 session transcribed rather than
byte-copied. Subsequently the committed `docs/SEAM_research_blueprint.md` was found to be a
**1-line stub** (`@@SEAM_BLUEPRINT_APPEND_POINT@@`, 32 bytes) — agents reading "the blueprint"
were reading nothing.

**Resolution (2026-07-30).** Restored from the Claude Desktop outputs archive via `robocopy`
(long-path staging; direct `Copy-Item` failed at MAX_PATH). SHA-256 of archive bytes vs repo
bytes compared; mismatches overwritten from source. **AM-002 duplicate §16.x numbers left as-is**
(pre-registration defect; no silent renumbering).

### Pin chain (do not delete; history is the audit)

**Standing pins (post governance-pass edits, 2026-07-30):**

| Document | Bytes | SHA-256 | Notes |
|---|---:|---|---|
| `docs/SEAM_research_blueprint.md` | 64861 | `ffe349804fa36de9ac94473ecd9372c6cc1234c91424242e5fc39040a67b1253` | After AM-019 §11 gate rewrite (G0 = RAPL certification; new confirmatory G0-B; G1 energy conditional) |
| `docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md` | 35968 | `9a905a340c513b40cd26a7d381b7d8ba9a28be316eaab04126aeb65cd5e1ca5b` | After AM-019 dependency-graph §7 rewrite; supersedes prior standing pin |
| `docs/CURSOR_KICKOFF_PROMPT.md` | 4143 | `3a4a3a38cbdef5cb0568940bf0ce55bea8d6999893dfef3b84192fdfb8cd5031` | Unchanged |
| `docs/hybrid_execution_dse_positioning.md` | 30542 | `ceec363af8a55269a370b63f80473f0cb00f757741be83fa054f56fb7c67d410` | Unchanged |

**Superseded archive entries (oldest → newest):**

| Document | Bytes | SHA-256 | Notes |
|---|---:|---|---|
| blueprint (archive, pre-AM-004) | 56617 | `6c2221c6dd774183c3a62d520190964f75a74c115cfcd3f1733ebe0c8377be63` | Claude Desktop restore |
| blueprint (post-AM-004, pre-AM-002-resync) | 58977 | `72d9b6a32ea40d07201d35e22cfc6db6c0f62311a40c15bc5ecf4f9c4567c878` | Duplicate §16.2/§16.3 |
| blueprint (**as-delivered** AM-002-fixed) | 61725 | `11da7b34936522fc37531f1321d7150f7f3788da6de6cce0f7472e6a92ef4cfd` | §16.1–16.9; hash-verified before edit |
| blueprint (post-AM-014, pre-AM-019) | 62321 | `ca5b0c44b3918acf454669aec5fa41c815acc6a76d4c83fc10a18b94792dfe8c` | Layer-based G0 still in force |
| spec (archive, pre-AM-004) | 25331 | `cfeada7da592eb59026b98481d52854481dec3d13e549ddc31d6d6b04a81604e` | Pre-AM-004 |
| spec (post-AM-004, pre-resync) | 26384 | `f42fad5bdf7377393684483b1f36dcc2da99e4fca94e9dd79292dde356198148` | Pre human resync |
| spec (**as-delivered** before §3.0) | 27171 | `5b0275da53be54d382e1b67e28d71c8429d98b4c277c7362f58d0beaaf166ad2` | Hash-verified before elevation insert |
| spec (post-§3.0, pre-§3.7) | 29092 | `89d8feeff92b2947acd5446837c5d2d22aef0135280c5c52c0839182dca72e6c` | Elevation preflight only |
| spec (post-§3.7 / AM-016, pre-M2.1 OQ2) | 32411 | `a102d201311405e2d921b4c71dcf79aff9b3fc9994e8a1f438a353945bc6d7f2` | Profiles defined; OQ2 still open |
| spec (post-M2.1 OQ2 / AM-017, pre-AM-019) | 33236 | `18cf9264cef0b08ea01c3d42d1d1d01389a296f6477aac96059816dcc2778328` | Linear milestone chain still in force |

**Note.** Prefer committed `docs/` copies and this table as the pin. Do not edit hashes to force a
match (CRLF / trailing-newline mismatches must be reported).

---

## AM-010 — A refused topology verification emits a manifest; `workload.kind` gains `topology_verify`

**Date:** 2026-07-29 · **Pre/post data:** **Post** — written after two verification runs refused
(AUDIT_LOG.md, "Topology verification RAN but did NOT establish the mapping") · **Status:** RESOLVED

**Divergence.** Spec §6.1 fixes `workload.kind` to `microbench | aa | h1_pilot`, and the schema
requires `platform.topology.verified: true` whenever `target` is `cpu-p` or `cpu-lpe`. Under those
two rules the §4 topology-verification run cannot emit a manifest when it refuses: it has no
verified topology to declare, and no `kind` that describes it. `seam/topology.py:main` therefore
raised before `emit()`, and a refusal produced no `run_id`, no `raw/<run_id>/`, and no record
(AUDIT_LOG.md AF-006).

**Why that is a defect and not merely inconvenient.** Two refused runs produced sixteen per-CPU
scores measured on real silicon. Spec §9.2 says no number may be reported without a traceable
manifest ID, so those numbers were formally unquotable — including in the audit entry explaining
why M1 was not accepted. The rule intended to guarantee traceability was instead discarding
evidence, and only ever for negative results.

**Decision** (authorised by Z. Johnson, 2026-07-29):

1. `workload.kind` gains a fourth value, `topology_verify`. It is a distinct kind rather than a
   `microbench` because it is the one workload whose **refusal is itself the result**.
2. The `cpu-p`/`cpu-lpe` verified-topology precondition is exempted for that kind, and **only** for
   that kind. The exemption is keyed on `workload.kind`, not on `target`, so no measurement
   workload can reach it. The run that produces the mapping cannot be required to assert one.
3. A new schema rule closes the hazard the exemption opens: if `workload.kind` is `topology_verify`
   and `platform.topology.verified` is `false`, then `integrity.self_check` **must** be `"fail"`. A
   refusal cannot be recorded as a pass.
4. A refused run records `p_cpus: null`, `lpe_cpus: null`, `verified: false` in the manifest. The
   clustering it found lives in `summary.json`, where it reads as a measurement, not a mapping.
5. `verify_topology()` is split. `measure_topology()` evaluates **every** acceptance criterion and
   returns a `verdict` plus the reasons; `verify_topology()` raises unless the verdict is `pass`.
   The CLI emits the manifest and then propagates the error, so a refusal is both citable and loud.

**Rationale.** This is spec §5.1's own principle applied one layer up: "an unsupported cell is a
data point, not a failure." A verification establishing that the two core types are not separable
by the current instrument is a finding about the instrument and the platform, and a reviewer should
be able to trace it. The alternative considered and rejected was AF-006's original suggestion of a
new `target` value (`host` / `self-check`): `target` enumerates *execution targets*, and inventing
a non-execution one would weaken a field that M4/M5 rely on for cell identity. `target: cpu-p` is
retained for the topology run because establishing the `cpu-p` / `cpu-lpe` mapping is its purpose.

**`spec_version` was not bumped.** It stays `"1.0"`. Every manifest valid under the previous schema
is still valid: the change adds an enum value and *narrows* the schema in the new case (rule 3). No
existing field changed meaning, and no emitted manifest requires reissue.

**Side effect, deliberate.** The instrument is now named in config
(`topology.verification.kernel`) and recorded as the manifest's `workload.benchmark`, so changing
the microbenchmark changes `config_hash`. Which instrument produced a score is part of the run
identity rather than an implicit property of the code at that commit.

**Also recorded by this change.** The topology run now captures the host power state
(`seam/powerstate.py`) into the manifest's `power_state` block and logs any deviation from
MACHINE.md's pinned run conditions. AF-005 was possible because nothing recorded those conditions
in an artifact. This captures and reports; the *gate* that refuses to start outside them remains
M2 scope, as AF-005 states.

---

## AM-011 — identifier deliberately unused

**Status:** N/A

AM-011 is permanently reserved as unused. Two independent collisions made reassignment unsafe:

1. An M1 closeout brief referred to a non-existent "AM-011 (resolved)"; the gap was left rather
   than filled under a false claim of prior resolution.
2. An incoming blueprint draft numbered a raw/-retention amendment **AM-011**. That identifier
   remains unused here; the amendment is issued as **AM-014** with revised substance (see below).
   The renumber is recorded so a reader comparing blueprint drafts to this file does not treat
   two different texts as the same amendment.

The clarification that followed the first collision is AM-012.

---

## AM-012 — the M1 run-to-run agreement gate is a relative-difference criterion

**Date:** 2026-07-30 · **Pre/post data:** **POST — ruled after seeing the two runs' ratios** ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson

**Divergence.** The M1 topology stop rule, pre-registered in `AUDIT_LOG.md` on 2026-07-30 and
restated in the closeout brief, required that run-to-run separation ratios "agree with each other"
and flagged a difference "more than the larger `cv_fast`" for an explicit report and an owner
decision. It did not say in what units the comparison is made, and the two readings disagree at the
observed margin:

| Reading | Run A vs run B | Limit | Result |
|---|---|---|---|
| Absolute difference in ratio units vs the CV fraction | 0.0276606546042928 | 0.024060827805485196 | exceeds by 0.0036 |
| Relative difference vs the CV, which is itself relative | 2.014% | 2.406% | within |

**Ruling.** The criterion is a **relative**-difference criterion. A coefficient of variation is
dimensionless — a standard deviation divided by a mean — so comparing it against a quantity
expressed in ratio units is dimensionally incoherent, and the absolute reading was a **units
mismatch in the wording of the rule**, not a disagreement in the data. Under the correct reading the
observed spread is roughly **1.1σ** of sampling noise: with `cv_fast ≈ 2.2%` over four cores, a
cluster mean carries ≈1.1% of sampling error, a single ratio ≈1.3%, and the difference of two ≈1.9%.

**Why this is a specification fix and not a loosened threshold.** The numeric tolerance is
**unchanged** — the criterion still compares against the larger `cv_fast` of the pair, and no value
in `topology.verification` was touched (`min_cluster_separation_ratio` stays 1.25,
`max_within_cluster_cv` stays 0.15). What changed is the *units* in which an ambiguous comparison is
evaluated. No run's verdict was reclassified: runs A and B each passed every §4 criterion on their
own, independently of this rule, and both exceeded the pre-registered 1.30883× baseline.

**Recorded as post-data, deliberately.** The ambiguity was discovered *because* the data landed in
the narrow band where the two readings differ, and the ruling was made with the numbers in view.
That is stated here rather than presented as a pre-registered detail, because a reader assessing the
strength of the M1 result is entitled to know which decisions were made after seeing it. The session
that hit the ambiguity did not resolve it in its own favour: it stopped, reported both readings, and
referred the question to the owner.

**Scope.** Applies to the run-to-run agreement comparison in the M1 topology stop rule. It does not
alter blueprint §5.5 A/A variance handling or any M3 noise-floor criterion, which are stated in their
own terms and are not affected by this wording.

**Standing hazard this leaves.** Applied pairwise across more than two runs, the rule necessarily
tests the extreme pair, whose spread grows as runs are added. Four AC runs produced five passing
pairs and one exceedance (B vs D, 2.82% against 2.41%), while every run sits within tolerance of the
four-run mean. A future revision of the rule should compare each run against the ensemble rather
than pairwise; that revision is **not** made here, because the current M1 decision is still being
evaluated under the rule as written.

**Superseded in part by AM-013**, which resolves that standing hazard by defining the comparator
set. AM-012's relative-reading clarification itself **stands and is unaffected**: agreement is still
assessed as a relative difference against the larger `cv_fast` of the compared runs.

---

## AM-013 — the M1 agreement gate is assessed among settled-charge runs only

**Date:** 2026-07-30 · **Pre/post data:** **POST — ruled after seeing all four AC runs' ratios** ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson

**Ruling.** Run-to-run agreement for the M1 topology gate is assessed **only among runs conducted at
settled charge**, defined as battery **> 85% and not under bulk charge**.

**Rationale 1 — charge state is a documented covariate on this platform, not noise.** Separation
rises monotonically as charging load falls:

| Run | Charge condition | Separation ratio |
|---|---|---|
| B `963a849e` | bulk charge, 70 → 71% | 1.3599431469328718 |
| A `3fb88dcd` | bulk charge, 69 → 70% | 1.3876038015371646 |
| C `855e3590` | taper, 87 → 88% | 1.3917174862228963 |
| D `7b5fc2e2` | settled, 90 → 90% | 1.3988665756315648 |

This is the **pre-registered mechanism** — P-core turbo headroom — appearing as a covariate.
Charging draws adapter headroom and adds chassis heat, and both depress P-core turbo more than LP-E
turbo, so the measured gap between the core types compresses under charge load. The prediction
registered on 2026-07-30 said so before any of these runs were taken.

**Rationale 2 — runs at different charge conditions are not exchangeable.** An agreement test asks
whether repeated measurements of the *same* quantity under the *same* conditions scatter more than
sampling error explains. Pooling bulk-charge and settled-charge runs into that test conflates a real
physical effect with sampling noise, and then reports the physical effect as instrument instability.

**Rationale 3 — the prior pairwise rule had an n-dependent defect.** It was written for **two**
runs. Applied pairwise across four it necessarily tests the extremes, and **maximum pairwise spread
grows with n**, so the rule got *harder to satisfy as evidence accumulated* — the opposite of how
replication should work. That is a specification defect, and it is being **corrected, not loosened.**

**What is unchanged.** The **numeric tolerance is identical**: the larger `cv_fast` of the compared
runs, exactly as before. Nothing in `topology.verification` was touched —
`min_cluster_separation_ratio` stays 1.25, `max_within_cluster_cv` stays 0.15,
`require_expected_split` stays true. **No run's individual PASS/FAIL verdict was reclassified**: all
four AC runs passed every §4 criterion on their own, independently of this rule, and each exceeded
the pre-registered 1.30883× baseline. AM-012 stands and is unaffected.

**Status of runs A and B.** They remain **fully logged, citable, and not discarded.** Nothing is
deleted, hidden, or marked invalid. Their role changes: from **agreement comparators** to
**supporting evidence for the charge-state mechanism.** In that role they are more informative than
they were as comparators — they are the low-charge end of the monotone series in Rationale 1, and
without them the covariate could not be demonstrated on this platform at all.

**Recorded as post-data, deliberately.** This was ruled with all four ratios in view, after a session
declined to resolve the ambiguity in its own favour and referred it to the owner. A reader assessing
the strength of the M1 result is entitled to know that the comparator set was defined after the data
were seen. What limits the hazard is that the rule is stated as a *condition on the measurement*
(settled charge) rather than as a tolerance on the outcome, that the tolerance itself did not move,
and that the citing run was pre-declared and evaluated once, with no re-rolling — see `AUDIT_LOG.md`
under "Pre-registration of the citing run".

---

## AM-014 — raw/ retention policy, threshold-based

**Date:** 2026-07-30 · **Pre/post data:** **PRE-DATA with respect to M2** · **Status:** RESOLVED ·
**Authorized by:** Z. Johnson

**Renumber note.** An incoming blueprint draft numbered this substance **AM-011**. That identifier
is deliberately unused in this repository (see AM-011 above). The amendment is issued here as
**AM-014**.

**Policy.** `raw/` payloads **ARE committed to git** while total payload size remains under a
declared ceiling of **100 MB** (`configs/repo.yaml` → `raw_retention.ceiling_mb`). Above that
ceiling, `raw/` payloads move to an externally archived, separately checksummed bundle, and
`raw/MANIFEST.sha256` — the committed index of run directories and seal hashes — becomes the
authoritative in-repo audit record.

**Rationale.** At M1 scale (7 sealed runs, JSON manifests and summaries; measured ~0.09 MB) committing
`raw/` costs almost nothing and buys off-host verification, which is why commit `503a845` was
right. That breaks at M2: `samples.ndjson` at 1–10 Hz produces ~6k samples per 10-minute run, and
M5's sweep is hundreds of runs. The ceiling is declared **now**, before the pressure exists, so the
transition is a pre-registered rule rather than an ad hoc reaction. The §5.3 immutability properties
are enforced by `seam/rawstore.py` in both regimes.

**Supersedes** the blanket "do not commit `raw/`" ruling originally drafted as AM-011. That blanket
ruling is contradicted by `503a845` and is superseded **before it ever took effect**.

**Mechanical enforcement.** `seam/raw_retention.py` + `tests/test_raw_retention.py` measure payload
size (excluding `raw/_blinding/**`) and **fail** when the ceiling is exceeded. The ceiling is not
remembered; it is checked.

---

## AM-015 — From M2 onward, acceptance criteria are pre-registered before data collection

**Date:** 2026-07-30 · **Pre/post data:** **PRE-DATA** · **Status:** RESOLVED ·
**Authorized by:** Z. Johnson

**Rule.** Beginning with M2, every agreement gate, acceptance criterion, comparator set, and stop
rule for a milestone **must be written into `AUDIT_LOG.md` and/or `AMENDMENTS.md` before any
measurement run for that milestone is taken**. A criterion formulated after seeing the numbers for
the milestone it accepts is a post-data amendment and must be labelled as such; it is not a
substitute for pre-registration.

**Worked example — M1 cost.** The charge-load *mechanism* was pre-registered (`99da687`). The
agreement *criterion* (AM-012 relative difference) and the *comparator restriction* (AM-013
settled-charge set) were both **POST-DATA**. The B-vs-D pair failed the all-pairs agreement gate
(2.8218% vs 2.4061% limit, 1.17× over), and that failure was resolved by a post-data criterion
choice. See `AUDIT_LOG.md` subsection **"M1 limitation: post-data agreement criterion"**. That is
the cost this rule exists to avoid repeating.

**Does not retroactively relabel AM-012 or AM-013 as pre-data.** Their POST-DATA labels stand.
**Does not authorize re-running M1** to manufacture a cleaner history.

---

## AM-016 — Pinned profiles by measurement class (`ac-pinned` / `battery-pinned`)

**Date:** 2026-07-30 · **Pre/post data:** **PRE-DATA with respect to M2** · **Status:** RESOLVED ·
**Authorized by:** Z. Johnson

**Divergence.** AF-005 / `assert_pinned_for_committed_result()` established a single pinned regime
centred on **AC power**. Spec §3.1 states S1 battery telemetry is only valid **on battery**. Those
constraints cannot share one profile.

**Ruling.** Pinning is **profile-scoped**. The harness selects the profile by measurement class and
refuses a mismatch (emit refusal manifest, stop — same pattern as `assert_pinned_for_committed_result()`).

| Profile | Use | Core asserts |
|---|---|---|
| `ac-pinned` | topology, thermal (M2.3), sustained turbo | `on_battery: false`; declared plan / brightness / WiFi / Defender |
| `battery-pinned` | S1 char (M2.1), energy calibration (M2.5) | `on_battery: true`; `charging: false`; settled after `settle_s`; discharge-rate stable; SoC window; quiesce fields recorded |

**Why SoC window alone is insufficient.** M1 showed the covariate is charging **load**, not charge
**level** (citing run E `fb5cd2d5` at 99% SoC had a *lower* separation ratio than C/D). A pack
drawing top-off current is not at rest. Battery profile must assert *not charging and settled*.

**Compound constraint (M2.5).** Energy calibration regresses S1 vs S2 on the *same* runs →
`battery-pinned` **AND** elevated (§3.0). Neither may be relaxed.

**Cross-dependency left open.** Thermal constants from M2.3 (`ac-pinned`) must not be assumed to
transfer to `battery-pinned` energy runs. M2.3 either characterizes both or states the limitation.

**Spec locus.** Phase −1 spec **§3.7**; M2.1/M2.3/M2.5 acceptance bullets updated. Numeric bounds
(`settle_s`, SoC window, discharge-rate band) stay `null` in platform YAML until M2.1 measures them.
**No telemetry code in this amendment** — documentation only.

---

## AM-017 — M2.1 S1 battery-counter characterization landed (OQ2 closed)

**Date:** 2026-07-30 · **Pre/post data:** **POST-DATA** (citing run
`911965cf-257c-4276-954b-17611a5e75eb`) · **Status:** RESOLVED · **Authorized by:** Z. Johnson
(unplug confirmation for Step 5)

**Ruling.** Spec §10 open question 2 is closed with the distributions and CIs recorded in that
question's CLOSED annotation. Platform YAML `power.profiles.battery-pinned` receives
`settle_s=360`, `soc_window_pct=[40, 85]`, `discharge_rate_stable_band_frac=0.05`, each citing
the run_id. Standing spec pin updated to
`18cf9264cef0b08ea01c3d42d1d1d01389a296f6477aac96059816dcc2778328` (33236 bytes). Prior
`a102d201…` archived under AM-009.

**Does not authorize M2.2–M2.5.** Thermal constants remain null; RAPL/STREAM absent.

---

## AM-018 — S1 energy estimator is `ΔRemainingCapacity` only (PRE-DATA w.r.t. M2.5)

**Date:** 2026-07-30 · **Pre/post data:** **PRE-DATA with respect to M2.5** · **Status:** RESOLVED ·
**Authorized by:** Z. Johnson

**Context.** M2.1 citing run `911965cf-257c-4276-954b-17611a5e75eb` measured a systematic
**8.0%** discrepancy between the two S1 sub-signals under constant synthetic load:

| Estimator | Energy (mWh) |
|---|---:|
| Σ\|ΔRemainingCapacity\| | **9054.0** |
| ∫ DischargeRate dt | **9779.1244081429** |
| rate / Δcap ratio | **1.080088845608891** |

Choosing which S1 signal to regress against RAPL **after** seeing the M2.5 slope would be
indefensible: the rate-based estimator would inflate the slope by ~8% inside the AM-004 band
`[1.0, 1.5]`.

**Ruling (locked before M2.5 data).**

1. **S1 energy for all energy work, including the §3.2 / M2.5 regression, is
   `ΔRemainingCapacity` over the analysis window.** This matches spec §3.2's stated preference
   ("Preferred estimator is *not* instantaneous rate but `ΔRemainingCapacity`").
2. The **8.0%** rate-vs-Δcap discrepancy is a **measured Platform A property**, recorded above
   with both totals (citing `911965cf…`). It is not discarded as noise.
3. **Integrated `DischargeRate` is retained as a CROSS-CHECK ONLY.** It must not be substituted
   into the M2.5 regression (or any energy acceptance arithmetic) under any circumstance —
   including if the Δcap-based slope is inconvenient.
4. This amendment is labelled **PRE-DATA w.r.t. M2.5** deliberately: the estimator is fixed
   before RAPL pairing data exist.

**Does not change** the M2.1 min-viable duration numeric (`395.805232` s). **Does not authorize**
starting M2.5.

---

## AM-019 — Structural correction: dependency graph replaces linear milestone chain

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA with respect to H1, H2, H3, H4, and every
figure except S3/S4 energy** · **Status:** RESOLVED · **Authorized by:** Z. Johnson

**Defect.** The Phase −1 milestone chain (M0→M1→M2→M3→M4→M5→M6, "work strictly in order")
encoded an instrument-first ordering. Blueprint §16.7 simultaneously states that the H1 pilot
has priority because "nothing else in the program matters if H1 fails." Where binding sequence
conflicts with prose guidance, sequence wins. The result: weeks of horizontal layer-building
with zero end-to-end evidence about the research question, and a serialization of M2 and M3
which have no dependency on each other.

Instrument-first is correct when all measurements depend equally on the instrument, when the
instrument is the dominant risk, and when the scientific question is settled. None holds here.
H1 requires step counts, token counts, and a wall clock. The dominant risk is scientific. The
question is open.

**Correction — true dependency graph.**

```
M0 (provenance) → M1 (manifest + topology) ─┬→ TRACK I  : instrument
                                            ├→ TRACK A  : agent
                                            └→ TRACK L  : local execution

TRACK I: M2 telemetry ────────────────→ M5 microbenchmarks
TRACK A: M3 harness + A/A + noise ────→ M6 H1 pilot
TRACK L: M4 local backends

M-SLICE (new, first-class): gated on M1 + minimal M3 + minimal M4.
         Produces the first end-to-end data point about the research question.
```

Tracks I, A, and L proceed in **PARALLEL** after M1. No track blocks another.

**M2 re-scoped.** From "characterize energy" to **CERTIFY RAPL.** Rationale: Platform B is
mains-only and has no battery, so RAPL is the only energy signal common to both platforms and
is therefore the reporting currency. M2's job is the binary question of whether RAPL is
trustworthy and whether it covers the NPU. **Stage A** (5 levels/target, one cycle, anchored,
randomized order) answers it. **Stage B** (full ≥8 levels) is confirmatory and conditional on
Stage A. Precision beyond certification gates nothing.

**Gates become risk-based, not layer-based.** The controlling gate for Phase −1 is H1
resolution (blueprint G2), not milestone completion. A milestone may be left incomplete if
completing it does not reduce a live risk.

**Energy is Paper 2 material.** Blueprint §13.2 places cost-model calibration in Phase 3.
Paper 1's claim rests on S1 and S2, neither of which requires a joule. S4's crossover surfaces
may be reported in tokens/sec first, with J/token added once RAPL is certified — throughput
crossovers across four targets are a standalone result.

**Spec locus.** Phase −1 spec **§7** rewritten; prohibition §9.10 softened to match. Standing spec
pin `9a905a340c513b40cd26a7d381b7d8ba9a28be316eaab04126aeb65cd5e1ca5b` (35968 bytes); prior
`18cf9264…` archived under AM-009.

**Blueprint locus.** **§11** rewritten: gates declared risk-based; **G0** energy criterion becomes
RAPL **certification** (Stage A); new confirmatory **G0-B** carries the full ≥8-level AM-004
criterion into Phase 3 / Paper 2 and explicitly does **not** block G1/G2; **G1** energy
decomposition is conditional on G0-B. §14.2 changelog row added. Blueprint §16.7 is **affirmed**
(H1 priority), not rewritten. Standing blueprint pin
`ffe349804fa36de9ac94473ecd9372c6cc1234c91424242e5fc39040a67b1253` (64861 bytes); prior
`ca5b0c44…` archived under AM-009.

**AM-004 is not weakened.** Its physics (R²≥0.95, slope∈[1.0,1.5], slope<1.0 a hard failure,
intercept vs measured idle baseline) is carried verbatim into G0-B. AM-019 changes **when** that
criterion is required, not what it says.

**Does not erase M2.1.** Battery-counter characterization (`911965cf…`) remains citable Platform A
evidence and feeds S1 when battery energy is used; it is not the cross-platform reporting
currency.

---

## AM-020 — Model pinning is "provider convention", not "dated alias"

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** (no cloud call has been made) ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson

**Defect.** Spec §7 M3.2 requires "pinned **dated** model snapshots". That rule encodes an
OpenAI-style convention as if it were universal. For Anthropic models from the 4.6 generation
onward, model IDs are **dateless by design and the dateless ID *is* the pinned snapshot**: weights
are never updated under an existing ID, and a new version ships as a new ID. Constructing a dated
variant of `claude-sonnet-5` would produce an identifier that does not exist, and the run would
fail — or worse, silently resolve elsewhere.

**Correction.** The requirement becomes: **use a pinned snapshot identifier expressed in the
provider's own convention**, and record in the manifest (a) the exact identifier string sent on the
wire, (b) the provider, (c) the convention under which that identifier is a pin, and (d) the
identifier the API reports back in its response. Where a provider offers dated IDs, dated IDs
remain mandatory; a floating alias such as `-latest` remains **forbidden** under every convention.

**Pinning does not eliminate drift.** Anthropic documents that serving infrastructure — routing,
classifiers, sampling implementation — may change under a fixed ID and produce minor behavioral
differences. The pin fixes the weights, not the serving stack. The daily canary run is therefore
**retained**, and this is its recorded justification.

**Spec locus.** §7 M3.2. **Applies to** M-SLICE and all later cloud work.

---

## AM-021 — Cross-model token deltas are not a valid behavioral metric (tokenizer hazard)

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA with respect to H1 and M-SLICE** ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson

**Defect.** Spec §7 M6 lists "Δ total tokens" among the primary H1 comparison metrics, and the
blueprint's behavioral-divergence framing inherits it. Claude 4.7 and later use a **newer tokenizer
that emits roughly 30% more tokens for identical text** than earlier models. Sonnet 5 is on the new
tokenizer; local models use their own, unrelated ones. A Δ-token comparison between a local model
and a cloud model therefore measures **tokenizer disagreement plus behavior**, and cannot separate
them.

This bias is **directed toward the hypothesis**: H1 predicts divergence, and a pure tokenizer
artifact would manufacture apparent divergence of roughly the same magnitude as the ≥20% G2
threshold. Discovering this after collection would be unrecoverable, because no post-hoc correction
distinguishes the two sources in already-collected counts.

**Ruling (locked before any H1 or M-SLICE data).**

1. **Native token counts are retained for COST accounting only**, where they are exactly correct —
   the provider bills on its own tokenizer.
2. **Primary behavioral metrics become tokenizer-independent.** Generated **characters** and
   **UTF-8 bytes** are recorded for every step and are the reporting currency for output volume.
3. Where a token-denominated behavioral comparison is unavoidable, all outputs are **re-tokenized
   under one declared reference tokenizer**, recorded by name and revision in the manifest. A
   mixed-tokenizer delta is never reported.
4. Step counts, tool-call counts, tool-call type distributions, and task success are unaffected —
   they were never tokenizer-dependent, and they carry H1.

**Spec locus.** §6.2 step record gains `completion_chars` / `completion_bytes`; §7 M6's metric list
is qualified. **Applies to** M-SLICE immediately.

---

## AM-022 — M-SLICE escalation policy pre-registration

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** (frozen before the throughput baseline and
before any main-run collection) · **Status:** RESOLVED · **Authorized by:** Z. Johnson

Pre-registers the mechanism under test in M-SLICE so that neither the policy nor the success
criterion can be adjusted after seeing the curves.

**1. Semantics are PREDICTIVE, not preemptive.** For step `s` on target `T` with deadline `D`:

```
t_pred(s,T) = prompt_tokens(s) / R_prefill(T) + n_out_pred(step_type(s)) / R_decode(T)
escalate  iff  t_pred(s,T) > D
```

`R_prefill(T)` and `R_decode(T)` are measured per target in the step-1 baseline. `n_out_pred(τ)` is
the **median** output length per step type from the step-1 profiling pass, **frozen before the main
run and identical across both arms**. It is not an oracle and is not recomputed per run. Prefill is
included because it is real local work that grows through a trajectory, so later steps escalate
more often — realistic and wanted. The deadline is **per-step**; a trajectory budget is a different
policy and is not tested here.

**2. Isolation invariant.** Between the `cpu-p` and `cpu-lpe` arms the **only** differing terms are
`R_prefill` and `R_decode`. Tasks, seeds, prompts, step types, `n_out_pred`, and `D` are identical.
This is asserted in code and covered by a test that fails if any other input differs between arms.

**3. The deadline is ADVISORY, not enforced.** Because `n_out_pred` is a median, roughly half of
locally-executed steps will overrun `D`. This is a property of the predictor, not a defect. The
**overrun rate is logged and reported alongside the escalation curve** as the predictor's error
rate.

**4. Pre-registered quantitative prediction.**

```
escalation_rate_lpe(D)  ≈  escalation_rate_p(D × R_p / R_lpe)
```

The two curves should be **one curve, horizontally rescaled by the measured throughput ratio**.
This is tested explicitly. **If they do not collapse under that rescaling, something other than
compute speed is driving the realized partition, and that is reported prominently rather than
smoothed over.**

**5. Escalated steps.** Cloud latency counts toward JCT; **zero local time is charged**, which
follows from predictive semantics. A failed cloud call is retried **once**, then falls back to
local with the step **marked**. Every retry and every fallback is logged as an event, because both
perturb the realized partition and must be visible in analysis.

**6. Decision cost is instrumented.** The wall-clock cost of evaluating the predictor itself is
measured and recorded per step. It is not expected to bind at this scale, but it is precisely the
quantity that **H3's routing-amortization bound** concerns, so the slice establishes its baseline
now.

**7. PREEMPTIVE semantics are DEFERRED as a declared future axis.** Starting locally, abandoning at
the deadline, and paying `local_partial + cloud_full` is where **H4's escalation-cascade cost**
lives — abandoned local work is a cascade cost by definition. Folding it into this slice would
conflate "escalated more often" with "wasted more time per escalation" and destroy the attribution
this slice is built to obtain. The deferral is recorded here as a pre-registered decision, not left
as an omission.

**Spec locus.** New M-SLICE policy section; consumed by `seam/agent/policy.py`.

---

## AM-023 — Pre-converted OpenVINO IR is a documented §5.3 weakening; manifests must discriminate

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** (before M-SLICE collection) ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson

**Divergence.** Spec §5.3 requires conversion to be "scripted and reproducible; never
hand-converted." Obtaining a Hub-published INT4 OpenVINO IR skips our export path: the NNCF
parameters (mode, ratio, group size) were chosen by the publisher, not by us. That is a real
weakening of the reproducibility guarantee.

**Decision.**

1. Pre-converted IRs are **permitted** for M-SLICE when self-conversion is blocked by the
   measured TLS handshake fault to `huggingface.co` (AUDIT_LOG, 2026-08-02) or when the
   download budget favors a ~2 GB IR over an ~8 GB FP16 export source.
2. Every such IR carries a `FetchedModelSpec` (`source: pre-converted`, `self_converted: false`,
   `source_repo`, `download_method`, publisher quantization, our computed `ir_sha256`).
3. Self-exported IRs continue to carry a `ModelSpec` with `export_command` and our own
   `quantization_config`.
4. The run-manifest `model.provenance` object **must** discriminate the two paths via
   `kind ∈ {self_exported, pre_converted}` and `self_converted`. Flattening them into
   `name/revision/quantization/ir_sha256` alone is a protocol violation — analysis would be
   unable to tell which provenance path produced a number.
5. The audit log notes, for each pre-converted IR, that conversion parameters were not under
   our control.

**Spec locus.** §5.3; `seam/model_provenance.py`; `seam/schemas/run_manifest.schema.json`.

---

## AM-024 — Reasoning mode is an explicit two-arm axis (amends AM-022)

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** (before throughput baseline) ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson

**Decision.** Qwen3 hybrid reasoning is **not** disabled by default. It is an experimental axis
with two arms:

| Arm | Local `enable_thinking` | Cloud reasoning | Role |
|---|---|---|---|
| 1 `thinking_off` | false | matched OFF | Fast, low variance; validates mechanism; runs FIRST |
| 2 `thinking_on` | true | matched ON | Primary scientific arm; amplifies silicon effect |

**Why not simply disable thinking.** Thinking multiplies absolute time differences between
targets (~10× wider discriminating window in the owner's arithmetic). It is also a primary
channel of behavioral response to capability (H1), a local model that reasons long and still
fails is the escalation cascade (H4), and "what silicon makes local reasoning viable" is the
OEM sizing question (S10). The between-arm comparison — reasoning workloads more
silicon-sensitive than non-reasoning, by a measurable factor — is itself a headline result.

**Amendments to AM-022.**

- `n_out_pred` is measured **separately per reasoning arm and per step type**, frozen before
  that arm's main run, and identical across **targets** within the arm. It is **not** shared
  across reasoning arms (AM-022's "identical across both arms" referred to cpu-p/cpu-lpe; that
  still holds *within* a reasoning arm).
- Deadlines are chosen **per arm** in absolute terms spanning the union of both targets'
  transition regions. Deadlines are **identical across targets within an arm**; setting them
  at each target's own quantiles would destroy the rescaling test.
- The rescaling prediction is tested **per arm**. Holding in Arm 1 but breaking in Arm 2 is a
  finding about reasoning-mode variance, not a bug.
- Arm 2 has a hard wall-clock timeout per local step, well above the largest deadline. Timeout
  hits are a **distinct category**, not deadline escalations.
- Boundary matching: reasoning mode is declared explicitly on **both** local and cloud sides
  per arm and recorded in every manifest. Empirically assert presence of `<think>` blocks in
  Arm 2 and absence in Arm 1.
- Sequence: complete and report Arm 1 before starting Arm 2. If the mechanism fails in the
  fast arm, do not spend days discovering the same failure slowly.
- Wall-clock: estimate Arm 2 runtime from step-1 before committing; if unacceptable, reduce
  **task count**, never deadline count.

**Spec locus.** `configs/mslice.yaml` `reasoning_arms`; manifest `model.reasoning_mode`.

---

## AM-025 — TOMBSTONE (retired; content moved to AM-033)

**Date originally logged:** 2026-08-02 · **Status:** RETIRED (tombstone) · **Reissued as:** AM-033

**Collision.** This identifier was also assigned in Blueprint §14 (2026-08-03) to the
absence-claim rule and step-type stratification correction. Sealed artifacts bind AM-025 /
AM-027 to Blueprint semantics; the Blueprint definition prevailed on sealed-usage grounds.
Identifiers are never reused — this entry is retired, not overwritten.

**Moved content.** Living definition: **AM-033 — Operating mode R1–R4 (blueprint v2.0 §0)**.

---

## AM-026 — Withdrawals under v2.0 (not deferred)

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** · **Status:** RESOLVED ·
**Authorized by:** Z. Johnson

Explicitly withdrawn so they cannot drift back as "future work":

| Withdrawn | Replaced by |
|---|---|
| Stage A / Stage B energy calibration staging | Full per-target multi-cycle design (`configs/energy.yaml`, ≥8 levels × 4 targets) |
| Deadline-driven two-paper split | Contribution ledger (`configs/project_state.yaml` `contribution_ledger`) |
| Preemptive escalation deferral | In scope as a second axis (`policy.escalation_semantics`) |
| CPU-only slice as permanent bound | Four local targets in the design space |
| FPGA/HLS gating engine as later-paper-only | In scope now (H12, S12) |
| Single reasoning arm | Two arms required (AM-024) |

AM-019 language that introduced Stage A certification staging is **superseded** by this entry for
energy design. Historical AM-019 text is retained for chain legibility; operative design is
`configs/energy.yaml`.

---

## AM-027 — TOMBSTONE (retired; content moved to AM-034)

**Date originally logged:** 2026-08-02 · **Status:** RETIRED (tombstone) · **Reissued as:** AM-034

**Collision.** This identifier was also assigned in Blueprint §14 (2026-08-04) to the router
proxy correction and narrative-provenance failure. Two sealed trees
(`raw/6bdfe71b-ee3d-4cb7-9d24-c01381baa2d9`, `raw/f4fd4f79-7c5e-4da7-b5fa-8316dd4e83b0`) bind
AM-027 to Blueprint §14 dated 2026-08-04 and mark the prior AMENDMENTS.md AM-027 as stale.
The Blueprint definition prevailed on sealed-usage grounds. Identifiers are never reused —
this entry is retired, not overwritten.

**Moved content.** Living definition: **AM-034 — Structural: dependency graph, yield queue,
gates never descope**.

---

## AM-028 — New hypotheses H8–H12

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** · **Status:** RESOLVED

Added: H8 thermal non-stationarity, H9 concurrency, H10 power source, H11 cross-boundary KV
residency, H12 hardware gating changes the bound. Manifest fields `thermal.regime`,
`workload.concurrency`, `power_state.power_source`, `policy.kv_residency` exist so these axes
cannot be run without being recorded.

---

## AM-029 — Time-varying coordinate θ(t) (blueprint §2.2)

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** · **Status:** RESOLVED

Thermal state evolves during evaluation; it is a **state**, not a decision variable. That is
what makes the objective surface non-stationary within a single evaluation (H8). Manifest
`thermal.regime ∈ {confound, axis}` forbids silent pooling of the two regimes in analysis.

---

## AM-030 — New audit standards §6.4–§6.8

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** · **Status:** RESOLVED

- §6.6 mutual exclusion: `seam/locks.py`; wired into `fetch_model` and `audit_append`; test
  refuses a second writer.
- §6.7 external verification: LFS `lfs.oid` SHA-256 in `fetch_model`; same-size-wrong-content
  regression in `tests/test_fetch_verification.py`.
- §6.8 cross-boundary confounds: tokenizer-independent primary metrics in `configs/mslice.yaml`;
  reasoning discriminant is non-empty content (`seam/reasoning.py`).
- §6.4 thermal dual regime: `thermal.regime` in the run-manifest schema.

---

## AM-031 — Blueprint pin v2.0

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** · **Status:** RESOLVED

Standing pin `373f8e25b86f68b68f29f85cc7b1db49dfd87294977322c4232fee0969043aa9` for
`docs/SEAM_research_blueprint.md`. Prior `ffe349804fa36de9ac94473ecd9372c6cc1234c91424242e5fc39040a67b1253`
archived in `GOVERNING_DOCS.sha256` as v1.0-final (KNOWN SUPERSESSION). Confirm, do not "fix"
by editing the pin list to silence drift.

---

## AM-032 — Withdraw E-FILTER 8 s headline deadline (C2)

**Date:** 2026-08-04 · **Pre/post data:** **PRE-DATA** (w.r.t. E-FILTER C2 run) · **Status:** RESOLVED

Withdraws the pre-registered `p95_step_target_s: 8.0` headline deadline for E-FILTER under the
C2 amendment (`docs/CURSOR_PROMPT_C2_efilter.md`).

**Reason:** Stage-1 decode floor placed every step near ~13.3 s (`n_out_pred`/`R_decode` constant
term). The 8 s target sat below the achievable floor and made P1–P3 vacuous. Absolute wall-clock
claims are also not admissible while `R` remains unverified pending A4; the over-provisioning
ratio is invariant to uniform throughput scaling when the deadline grid is data-derived.

**Replacement:** P1–P3 evaluate at the **material deadline on the derived `t_pred` grid**
(≥8 points spanning the observed range). Deadlines are reported in distribution units
(empirical CDF / fraction of observed `t_pred` range); seconds are secondary with caveat
`R unverified pending A4`. `configs/efilter.yaml` sets `p95_step_target_s: null` /
`p95_step_target_status: withdrawn_AM-032`.

**Does not invalidate:** sealed Stage-1 run `1a0166b9-cbaf-43f4-8d76-bcd7c01841e0` as a baseline
point for P6 (over-provisioning 1.243×, CI 1.115–1.409, peak context 1826).

---

## AM-033 — Operating mode R1–R4 (blueprint v2.0 §0)

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA with respect to every hypothesis** ·
**Status:** RESOLVED · **Authorized by:** Z. Johnson ·
**Reissued from:** AM-025 (tombstoned 2026-08-06; dual-definition collision with Blueprint §14)

**Change.** Timing removed as a constraint (R1). The claim strengthens monotonically (R2).
Yield maximization per session (R3). Main-line protection via the additive/displacing filter (R4).
Owner directive — replaces the v1.0 deadline-driven operating mode.

**Enforcement.** `.cursor/rules/seam-core.mdc` (`alwaysApply: true`) carries R1–R4 as standing
agent constraints. Gates that answer unmet criteria with "reduce scope" are forbidden in
`configs/project_state.yaml` gate commentary and seam-core.

---

## AM-034 — Structural: dependency graph, yield queue, gates never descope

**Date:** 2026-08-02 · **Pre/post data:** **PRE-DATA** · **Status:** RESOLVED ·
**Reissued from:** AM-027 (tombstoned 2026-08-06; dual-definition collision with Blueprint §14)

Timeline → dependency graph + yield queue. Milestone chain → parallel tracks after M1.
Gates rewritten so **no** gate response is ever "reduce scope." Recorded in
`configs/project_state.yaml` (`tracks`, `yield_queue`, gate names) and seam-core.

---

## AM-035 — Delta-prefill model: measured form; retract arm-A 19.45 s constant

**Date:** 2026-08-10 · **Pre/post data:** **POST-DATA** · **Status:** RESOLVED

**Citing seals (derived_diagnostic; raw/ promotion blocked while tier-1 resident — see
`PROMOTION_ATTEMPT.json` under each session):**

| Session / run_id | Matrix | Seal path |
|---|---|---|
| `d5c98342-a0b2-41a9-b6e2-93ac7a39c3ba` | n_cached=12000; 17 OK / 1 failed (robustness) | `derived/delta_prefill/sealed_d5c98342-a0b2-41a9-b6e2-93ac7a39c3ba/` |
| `9f38eb15-6fe6-40b4-871b-a02ec5629bb1` | n_cached=4000; 24/24 OK | `derived/delta_prefill/sealed_9f38eb15-6fe6-40b4-871b-a02ec5629bb1/` |

**Prior form (retracted).** A constant-plus-linear (or constant-plus-delta) fit for arm A at a
single cached length produced an intercept of **19.45 s** at `n_cached=12000`. That constant was
an artifact of fitting two points at one cached length. It is withdrawn.

**What depended on the retracted constant (also withdrawn or recomputed):**

- Any local-feasibility bound that treated turn-2 cost as `19.45 + k·Δ` (or equivalent) independent
  of session position / `n_cached`.
- Cost-interaction claims that used that intercept in the replay / optimal-config stack — the
  prior **6×** super-additive cost interaction is superseded (see corrected figures below).
- Max-feasible-delta tables that did not condition on `n_cached`.

**Latency interaction 2.4× is not retracted.** It came from measured medians, not from the
retracted intercept fit.

**Measured replacement (standing).** At two cached lengths (`9f38eb15` n=4000; `d5c98342` n=12000):

```
turn2_prefill_s ~ C · d · n_cached     (gpu_only; delta-only term fits ~0)
gpu_only:  C = 4.34e-7

arm A:     k(n) = 0.0166 · (n/4000)^0.70
           turn2_prefill_s = k(n) · d
```

Per-delta-token cost is **flat in delta at fixed n** (three points at n=4000 from `9f38eb15`:
0.0166 / 0.0159 / 0.0175 s/token) and **scales with n**.

**Consequence.** Local feasibility depends on position in the session (`n_cached`), not delta
alone. Max feasible delta at the 10 s bound under gpu_only+residency:

| n_cached | max feasible Δ (10 s) |
|---:|---:|
| 4000 | 5760 |
| 12000 | 1920 |
| 27600 | 834 |

**Corrected optimal-config cost figures** (supersede any prior narrative table that used the
retracted model; standing writeup:
`derived/delta_prefill/OPTIMAL_CONFIG_COST.md`):

| Config | % local | Cost | Saving vs default |
|---|---:|---:|---:|
| default | 0% | $154.42 | — |
| gpu_only alone | 25% | — | 7% |
| gpu_only+residency | 42% | $130.33 | 16% |

- Cost interaction super-additive at **2.3×** (was 6× on the retracted model).
- Latency interaction **2.4× UNCHANGED**.

**Does not invent a dual-definition collision.** This identifier is AMENDMENTS.md-only; Blueprint
§14 is not given a parallel AM-035 row (see AM-025/AM-027 collision history and
`tools/hooks/check_amendment_ledgers.py`).

**Machine-readable companion:** `derived/delta_prefill/AM035_delta_prefill_model.json`.

---

## AM-036 — Measurement vs promote-time power_state; refuse retro-seal leakage

**Date:** 2026-08-10 · **Pre/post data:** **POST-DATA** (leaked ceiling_a promotes already sealed)
· **Status:** RESOLVED

**What changed.** The run-manifest schema and emitter now distinguish:

1. ``power_state`` — **measurement-time** host environment only (self-seal during the run, or
   values derived from measurement / cell records).
2. ``promote_time_power_state`` — optional forensic sample taken at raw-promote / retro-seal time.
   Must never be read as measurement environment.
3. ``power_state_note`` — provenance note when measurement power is unrecorded.

``seam.manifest.emit(..., retro_seal=True)`` refuses any non-null measurement ``power_state``
unless ``measurement_power_from_records=True``. Retro-seal tools
(``tools/seal_ceiling_a_partial_session.py``, ``tools/seal_delta_prefill_session.py``) pass
``power_state=None`` and may record promote-time samples only under ``promote_time_power_state``.

**Why.** Post-hoc promote of ceiling_a arms ``b5ce21e5`` / ``64e525e7`` / ``404dc3d0`` called
``capture_power_state()`` at promote time (2026-08-10) and wrote the result into ``power_state``,
so sealed manifests claim ``on_battery=true`` / ``battery_pct_start=88.0`` for work measured on
AC on 2026-08-06. Measurements are unaffected; this is sealed-metadata provenance error (AF-036).

**Correction path.** ``raw/`` is write-once (``seam.rawstore`` refuses mutation and re-seal).
No prior sealed-metadata amend-in-place pattern exists. Loaders use
``seam.manifest.load_run_manifest``:

1. Explicit amendments for the three AF-036 digests in
   ``derived/manifest_corrections/registry.json``.
2. A **structural** safety net (not a run_id list): when a run is marked retro-seal
   (``manifest.retro_seal``) or post-hoc promote (``summary.promotion`` starts with
   ``post_hoc``), ``promote_time_power_state`` is absent, measurement ``power_state`` is
   populated, and ``measurement_power_from_records`` is not true — treat measurement power as
   a promote-time leak (null it; move sealed sample to ``promote_time_power_state``; attach
   note). Emit also stamps ``retro_seal`` / ``measurement_power_from_records`` on new
   manifests so the rule stays marker-based.

Sealed digests are unchanged and remain verifiable. Do not backfill measurement power from
memory.

**Self-sealed control.** ``693b44d2`` (sealed during the run) retains ``on_battery=false`` /
``100.0``. Delta-prefill promotes ``d5c98342`` / ``9f38eb15`` already had null measurement power
and stay null.

---

## AM-037 — C-1: position limit not enforced; no hard memory ceiling on 16 GB host

**Date:** 2026-09-08 · **Pre/post data:** **POST-DATA** (session
`83127e1b-9d6e-4103-bee6-2a63c00f479f`) · **Status:** RESOLVED

**What changed (two corrections).**

1. **`max_position_embeddings` of 40,960 is not enforced at inference.**
   Config `models/Qwen3-4B-int4-ov/config.json` claims 40960, but
   `gpu_only_f16` probes completed at **n=44,742** (incomplete attempt at
   44,871). C-1 must not treat 40960 as a hard wall or as the PRIMARY
   position-bound prediction without an observed failure naming a position /
   context bound.

2. **There is no hard memory ceiling on this 16 GB host.** The OS pages.
   `available_mb_min` reached **0.0** on completed probes
   (`n=36750` r0, `n=44742` r0) while generate continued. Memory-wall
   predictions of the form `n_max=(M−W)/(k+w)` against Available do not
   describe a hard stop under paging. Fit consumption with
   **`peak_commit_bytes`**, not RSS (RSS is capped by
   `SetProcessWorkingSetSizeEx` at 12 GB / 12884901888 bytes).

**Session disposition.** `83127e1b` marked **aborted**,
`abort_reason=no_ceiling_found_in_range`. Worker
`tools/run_c1_ceiling.py` now probes `high` after `low` and, if `high`
passes, terminates with that abort status instead of converging on the
search upper bound as a fake ceiling.

**Capability reframing.** Real capability numbers are SLO crossings
(TTFT/prefill ≤ 10 s; decode ≥ 6 tok/s), not a memory/position hard wall
in [12k, 45k]. See `derived/c1_ceiling/83127e1b-…/salvage_analysis.json`.

---

## AM-038 — C-2 pre-registration: withdraw turn-1 ordering; replace with agreement

**Date:** 2026-09-08 · **Pre/post data:** registered **PRE-DATA**; evaluated
**POST-DATA** on sealed C-2 `62395fdb-1899-415f-b708-6adc81a24dda` ·
**Status:** RESOLVED (held)

**WITHDRAWN.** `TTFT-bound limit orders f16 > u8 >= u4`.

**Reason.** That ordering was inferred from the 15–27% f16 advantage in
41e419bd Finding 2, which is a **turn-2 delta prefill** measurement. C-2
bisects on **turn-1 bulk prefill**. Finding 2's direct statement about
turn-1 is that arms agree within 1%.

**REPLACEMENT (active).** The three turn-1 TTFT limits **AGREE** within the
250-token resolution. KV precision does not move the cold-start context
limit. **Falsified** if any pair differs by more than 250 tokens.

**Outcome (`62395fdb`).** Limits f16 = u8 = u4 = **10,000**; span 0;
`primary_prediction_held` true. Seal
`derived/c2_ttft/sealed_62395fdb-1899-415f-b708-6adc81a24dda/`,
`tree_sha256`
`95cc9d5c28fc87dcefd7c990ab216854997c5fffdf2b8212d6173173da25ae0c`.

**Consequence.** KV precision affects neither capability (memory does not
bind, C-1) nor the cold-start SLO limit. Its only remaining measured effect
on this hardware is memory footprint — report it that way rather than as
buying context.

**Separate experiment, not C-2.** Turn-2 delta-prefill 10 s limit (binds
under RESIDENT; 15–27% advantage lives there; wider search above 12,000).
Prediction there remains `f16 > u8 >= u4`. Recorded as
`separate_experiment_not_c2` in C-2 `plan.json` so it is not folded into
C-2.

**Record.** Both withdrawn and replacement stay in
`tools/run_c1_ceiling.py` (`_ttft_slo_predictions`) → `plan.json`
`pre_registered_predictions`. Former `tools/run_c2_ttft.py` retired to
`tools/_retired/run_c2_ttft.py`; C-2 launches
`run_c1_ceiling.py --criterion ttft_slo`.

---

## Finding note — C9 practical context ceiling (C2b)

**Date:** 2026-08-04 · **Status:** RECORDED · **Not an AM number**

Citing partial pilot `0fe5e4c7-bb38-4666-826b-2c512b17a969` (IN_PROGRESS; not sealed — do not
mutate). At 9114 tokens KV ≈ 672 MB should fit with a ~2.6 GB model under KV-only arithmetic, but
re-prefill activation bound the practical ceiling near ~9100 vs architectural 40960 (4.5× below).
Contradicts meeting-brief KV-only capacity arithmetic. Artifact:
`derived/efilter/c9_practical_ceiling_note.json`. C2b response: `context_cap_tokens=7000`,
`max_tokens=128`, OpenVINO GenAI structured tool-call decoding.

---

## AM-039 — History rewrite to strip oversized blobs; sealed files untouched

**Date:** 2026-09-12 · **Pre/post data:** PRE-DATA w.r.t. sealed evidence bytes
(no sealed file edited) · **Status:** RESOLVED

**Divergence.** Pushing the evidence-bearing branch failed GitHub's 100 MB hard
limit on `apu_characterization/fixtures/vectors.npy` (146 MB), introduced in
`1486fe7` and present in every descendant commit. Sealed manifests cite those
descendant commits via `git_sha`. A naive rewrite would leave those citations
pointing at unreachable SHAs.

**Decision.** Rewrite history with `git filter-repo` to remove
`apu_characterization/fixtures/vectors.npy` and
`orchestration_engine/**/mock_action_heavy_c5000.json` from all commits; keep
both files on disk and gitignored; archive the pre-rewrite graph
(`../gnn-hls-accel-prerewrite-875dc74.bundle`, tag `prerewrite/875dc74`); record
the filter-repo commit-map and a verified old→new table for every sealed- and
ledger-cited SHA in `docs/GIT_SHA_MAP.md`. Do **not** edit any sealed file.

**Why this preserves provenance.** Tree diffs for each cited SHA show the only
change is deletion of the oversized paths (never referenced as run inputs). The
`raw/` + `derived/` file-content digest is identical before and after. Old SHAs
remain interpretable via the committed map and the local bundle/tag.

---

## AM-040 — INF-5 run_environment on every new seal (`spec_version` 1.1)

**Date:** 2026-09-15 · **Pre/post data:** **PRE-DATA** (instrumentation; no experiment
re-run) · **Status:** RESOLVED

**Divergence.** ENV-DIFF of W-3 (`6225d6e1`) vs Q-KV / Q-REPRO showed every *recorded*
decode-critical pin matching, yet `trajectory_pass` halved. The residual cause sat in
fields the seal did not capture: GPU driver, measured Windows build, active power-scheme
GUID, full pip-freeze hash, `tokenizers` version, prompt-render SHA-256, Available MB
bookends, WorkloadsSessionHost residency, and session design / arm order.

**Decision.** Additive schema bump `1.0` → `1.1`. New top-level `run_environment` block is
**required** when `spec_version` is `1.1`. Historical `1.0` seals remain valid without the
block (`raw/` write-once; never rewritten). Seal refuses (hard) if any required field is
absent, null, or empty — no silent defaults. Host-readable fields are collected in
`seam/run_environment.py` at emit; session fields must be supplied by the caller (or staged
on `summary["run_environment"]`).

**Pip-freeze canonicalization.** UTF-8, LF newlines, stripped non-empty lines **sorted**
ascending, trailing newline, then SHA-256.

---

## DEFERRED-BY-DEPENDENCY — adopted confinement mechanism citing run_id

**Date:** 2026-08-02 · **Status:** DEFERRED-BY-DEPENDENCY · **Blocker:** A1–A6 confinement
matrix on the verified 4B under quiesced conditions (not started in this dispatch; download may
still be in flight).

`configs/mslice.yaml` `openvino.adopted_mechanism` and
`configs/project_state.yaml` `milestones.M_SLICE.confinement` remain null until that matrix
resolves. Not deferred for cost or time (R1 forbids that).

---

## DEFERRED-BY-DEPENDENCY — Phase 4 sustained-burst execution

**Date:** 2026-08-02 · **Status:** DEFERRED-BY-DEPENDENCY · **Blocker:** First paid action is
gated on Phase 3 reasoning discriminant PASS; this dispatch takes no spend.

Requirement is **landed** in `configs/canary.yaml` (`sustained_burst.required_before_collection`,
n_calls≥10, prompt_chars_min≥20000) with a test that fails if removed. Execution of the burst
itself awaits the paid-phase gate.
