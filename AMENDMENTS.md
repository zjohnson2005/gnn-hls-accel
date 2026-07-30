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
| AM-002 | 2026-07-29 | Blueprint §16 | Duplicate section numbers §16.2/§16.3 | OPEN (doc defect) |
| AM-003 | 2026-07-29 | §5.2 vs §6.1 | Spec's manifest schema drops blueprint-required fields | RESOLVED (union) |
| AM-004 | 2026-07-29 | §16.6 vs §3.2 | **Energy acceptance criteria directly conflict** | RESOLVED (2026-07-30, PRE-DATA, Z. Johnson) |
| AM-005 | 2026-07-29 | Spec §2 | Repo layout: `seam/` is both root and package | RESOLVED |
| AM-006 | 2026-07-29 | Thermal | §5.4 constants unknown at M1; manifest needs nulls | RESOLVED |
| AM-007 | 2026-07-29 | Source docs | Source folder holds four documents, not three | RESOLVED (2026-07-30, hybrid ingested) |
| AM-008 | 2026-07-29 | M1 | Topology cannot be verified — no shell | OPEN (blocks M1 accept) |
| AM-009 | 2026-07-29 | Doc ingest | Governing docs transcribed, not byte-copied | RESOLVED (2026-07-30, hashes pinned) |
| AM-010 | 2026-07-29 | §6.1 manifest schema | Refused topology verification must emit a manifest (AF-006) | RESOLVED |

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

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** OPEN (documentation defect)

**Divergence.** `§16` numbers two different subsections `16.2` and two different subsections
`16.3`:

| Number | First use | Second use |
|---|---|---|
| §16.2 | "The controlled-contrast axis" | "Tier 1 — fully executable now" |
| §16.3 | "Consequences to propagate" | "Tier 2 — XPS 16 measurements with lasting value" |

**Why it matters.** Internal cross-references become ambiguous, and both are load-bearing:

- **P-1.10** cites "the two-signal validation described in §16.2." Neither §16.2 describes a
  validation protocol. The intended target is the *Platform A exclusives* bullet list, which
  sits under the first §16.2 ("two independent energy signals … let P0.4 proceed without a wall
  meter"). Resolvable by content.
- **P-1.15** cites "§16.3(3)," meaning item 3 of "Consequences to propagate" (16 GB unified is a
  hard constraint). The second §16.3 is a table with no item 3. Also resolvable by content, but
  only because the numbering happens to fail loudly.

**Decision.** No renumbering performed — the blueprint is the pre-registration artifact and is
tagged; silently renumbering sections in a pre-registered document is worse than the defect.
Cross-references resolved by content as above and recorded here.

**Recommendation.** Fix in the next blueprint revision by renaming the Tier subsections to
§16.4–§16.6 and shifting the existing §16.4–§16.6 accordingly, logged as a normal §14.2
amendment.

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

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** OPEN — **blocks M1 acceptance**

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

| Document | Bytes (archive) | SHA-256 (archive / post-restore match) | Notes |
|---|---:|---|---|
| `SEAM_research_blueprint.md` | 56617 | `6c2221c6dd774183c3a62d520190964f75a74c115cfcd3f1733ebe0c8377be63` | Restored 733 lines; then AM-004 text applied (new hash — see AUDIT_LOG) |
| `PHASE_MINUS1_IMPLEMENTATION_SPEC.md` | 25331 | `cfeada7da592eb59026b98481d52854481dec3d13e549ddc31d6d6b04a81604e` | Repo already byte-identical; **not clobbered**; AM-004 then edited §3.2/M2.5 |
| `CURSOR_KICKOFF_PROMPT.md` | 4143 | (unchanged; pre-existing match) | Not rewritten |
| `hybrid_execution_dse_positioning.md` | 30542 | `ceec363af8a55269a370b63f80473f0cb00f757741be83fa054f56fb7c67d410` | Newly ingested (AM-007) |

**Note.** The source folder is an application cache path and is not durable. Prefer the committed
`docs/` copies and the hashes in `AUDIT_LOG.md` as the pin.

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
