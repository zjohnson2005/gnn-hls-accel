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
| `docs/SEAM_research_blueprint.md` | 62321 | `ca5b0c44b3918acf454669aec5fa41c815acc6a76d4c83fc10a18b94792dfe8c` | After AM-014 renumber/substance replace in §5.3 + §14 |
| `docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md` | 29092 | `89d8feeff92b2947acd5446837c5d2d22aef0135280c5c52c0839182dca72e6c` | After §3.0 elevation preflight inserted |
| `docs/CURSOR_KICKOFF_PROMPT.md` | 4143 | `3a4a3a38cbdef5cb0568940bf0ce55bea8d6999893dfef3b84192fdfb8cd5031` | Unchanged |
| `docs/hybrid_execution_dse_positioning.md` | 30542 | `ceec363af8a55269a370b63f80473f0cb00f757741be83fa054f56fb7c67d410` | Unchanged |

**Superseded archive entries (oldest → newest):**

| Document | Bytes | SHA-256 | Notes |
|---|---:|---|---|
| blueprint (archive, pre-AM-004) | 56617 | `6c2221c6dd774183c3a62d520190964f75a74c115cfcd3f1733ebe0c8377be63` | Claude Desktop restore |
| blueprint (post-AM-004, pre-AM-002-resync) | 58977 | `72d9b6a32ea40d07201d35e22cfc6db6c0f62311a40c15bc5ecf4f9c4567c878` | Duplicate §16.2/§16.3 |
| blueprint (**as-delivered** AM-002-fixed) | 61725 | `11da7b34936522fc37531f1321d7150f7f3788da6de6cce0f7472e6a92ef4cfd` | §16.1–16.9; hash-verified before edit |
| spec (archive, pre-AM-004) | 25331 | `cfeada7da592eb59026b98481d52854481dec3d13e549ddc31d6d6b04a81604e` | Pre-AM-004 |
| spec (post-AM-004, pre-resync) | 26384 | `f42fad5bdf7377393684483b1f36dcc2da99e4fca94e9dd79292dde356198148` | Pre human resync |
| spec (**as-delivered** before §3.0) | 27171 | `5b0275da53be54d382e1b67e28d71c8429d98b4c277c7362f58d0beaaf166ad2` | Hash-verified before elevation insert |

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
