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
| AM-004 | 2026-07-29 | §16.6 vs §3.2 | **Energy acceptance criteria directly conflict** | OPEN (decide before M2.5) |
| AM-005 | 2026-07-29 | Spec §2 | Repo layout: `seam/` is both root and package | RESOLVED |
| AM-006 | 2026-07-29 | Thermal | §5.4 constants unknown at M1; manifest needs nulls | RESOLVED |
| AM-007 | 2026-07-29 | Source docs | Source folder holds four documents, not three | OPEN (needs confirmation) |
| AM-008 | 2026-07-29 | M1 | Topology cannot be verified — no shell | OPEN (blocks M1 accept) |
| AM-009 | 2026-07-29 | Doc ingest | Governing docs transcribed, not byte-copied | OPEN (verify hashes) |
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

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** OPEN — **needs a decision before M2.5**

**Divergence.** These two requirements are mutually incompatible, and both are normative:

> **Blueprint §16.6, Gate −1:** "RAPL and battery-discharge energy **agree within 15%** under
> sustained load." Failure response: "Investigate attribution; add explicit error term before any
> energy claim."

> **Spec §3.2 item 5:** "**Do not require agreement within a fixed percentage** — the two signals
> measure different things; what matters is that they track linearly with a stable, reported
> offset." Acceptance is $R^2 \ge 0.95$ with reported slope and intercept.

**Analysis.** The spec is physically correct and the blueprint's Gate −1 criterion is not
achievable as written. Spec §3.2 establishes that S1 (battery discharge) includes display, SSD,
WiFi, EC, and fans, while S2 (RAPL) covers SoC domains only — so $S1 > S2$ **always**, by a
margin set by non-SoC baseline power. On a 16″ laptop with a 120 Hz panel (per MACHINE.md, this
one) display power alone can be several watts, which at low SoC load is far more than 15% of
package power. A 15%-agreement gate would fail for correct measurements and could only be
"passed" by mis-attributing baseline power into the SoC term.

**Why this is not simply "blueprint governs."** The precedence rule resolves *ambiguity*; it
cannot make an unachievable criterion achievable. Applying it literally here would gate Phase −1
on a test that correct instrumentation fails.

**Recommendation (not yet applied — no M2 work performed).** Amend blueprint §16.6 to replace the
15%-agreement row with the §3.2 linear-tracking criterion: $R^2 \ge 0.95$ across ≥8 load levels,
slope/intercept/residuals reported, with the paired idle-load-idle design of §3.2 item 2
estimating $P_{base}$. Keep the blueprint's failure response, which is already correct
("add explicit error term before any energy claim").

**Not decided unilaterally** because Gate −1 is a **pre-registration** criterion. Changing a
pre-registered gate is exactly the class of change that must be visible and human-approved, not
absorbed by an implementing agent. **No energy code was written this session**, so nothing
depends on the resolution yet.

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

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** OPEN (needs confirmation)

**Divergence.** The Phase −1 task specification states the source folder holds "exactly three
files." It contains **four**:

- `SEAM_research_blueprint.md` — ingested
- `PHASE_MINUS1_IMPLEMENTATION_SPEC.md` — ingested
- `CURSOR_KICKOFF_PROMPT.md` — ingested
- `hybrid_execution_dse_positioning.md` — **not ingested**

**Why it matters.** The fourth file is not incidental. Blueprint §2 cites it as normative:
"Positioning (condensed; **full collision map in `hybrid_execution_dse_positioning.md`**)," and
Appendix A defers the audit of six unread related-work papers (HERA, HybridFlow, PAAC, PRISM,
IslandRun, HeRo) to task P-1.7. A blueprint section therefore points at a document the ingest
instruction excluded.

**Decision.** Not copied — the instruction named three files explicitly, and silently importing a
fourth governing-adjacent document exceeds the authorised scope. Flagged for a human decision.

**Recommendation.** Copy it to `docs/hybrid_execution_dse_positioning.md` so blueprint §2's
reference resolves inside the repository. It affects related-work and positioning (P-1.7), not
M0/M1 measurement code, so nothing in this session depends on it.

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

**Date:** 2026-07-29 · **Pre/post data:** Pre · **Status:** OPEN — verify before relying on the copies

**Divergence.** The ingest instruction was to copy the three source documents into `docs/`
**verbatim**. A verbatim copy is a `Copy-Item` operation. With the shell backend dead
(`AUDIT_LOG.md` AF-003), the only available mechanism was to read each document through the editor
and write it back out — i.e. **transcription, not copying**.

**Status per document:**

| Document | Method | Confidence |
|---|---|---|
| `CURSOR_KICKOFF_PROMPT.md` | Pre-existing in repo; **not rewritten** | High — source and repo copy were read and compared line-for-line and match |
| `PHASE_MINUS1_IMPLEMENTATION_SPEC.md` | Transcribed (400 lines) | **Spot-verified** — see below |
| `SEAM_research_blueprint.md` | Transcribed (734 lines) | **Unverified** — no hash comparison possible |

**Spot-verification performed on the implementation spec (2026-07-29).** Line count matches source
(400), zero line-number prefixes leaked, 11 top-level sections. Three high-risk regions were
compared directly against the source and match **exactly, at identical line numbers**:

- the fenced repository-tree block (source lines 40–88), including box-drawing characters and
  comment-column alignment — the one region the transcription flagged as inferred;
- the §3.2 energy-protocol block (lines 122–131), including `$E_{SoC}^{S1} = \int (P_{S1} -
  P_{base})\,dt$`, `$R^2 \ge 0.95$`, `≥8`, and `idle→turbo`;
- the §6.1 manifest JSON block (lines 243–252).

This raises confidence materially but is **not** a substitute for a hash comparison, which remains
required below. Line-count and section-count agreement cannot detect a single altered character
outside the sampled regions.

**Why this is a provenance issue and not a nitpick.** The blueprint is the *governing* document: it
defines the audit standard that every later claim is measured against, and §14.2 makes it the
pre-registration artifact. A transcription can silently drop or alter exactly the content most at
risk — LaTeX math, the U+2212 minus in "Phase −1", Greek letters, em dashes, wide markdown tables,
and the intentional duplicate section numbers recorded in AM-002. A corrupted governing document is
**worse than a missing one**, because a missing file fails loudly whereas a subtly altered one is
trusted.

**Decision.** Transcribe, but record the copies as unverified and require a hash check before they
are treated as authoritative. Transcription was chosen over leaving `docs/` empty because blueprint
§2 and the kickoff both assume the documents are readable from inside the repository, and later
agents are instructed to read them from there.

**Required action.** On shell restoration, for each of the three documents:

```powershell
Get-FileHash -Algorithm SHA256 <source>\<doc>.md
Get-FileHash -Algorithm SHA256 docs\<doc>.md
```

If a pair does not match, **overwrite the repository copy from source with `Copy-Item -Force`** —
do not attempt to reconcile by editing. Then record the confirmed SHA-256 values in `AUDIT_LOG.md`
so the governing documents are pinned the same way the probe artifacts are (blueprint §5.2).

**Note.** The source folder is an application cache path
(`AppData\Local\Packages\Claude_...\LocalCache\...`), which is not a durable location. Archive the
three source documents somewhere stable before that cache is cleared, or the hash comparison above
becomes impossible.

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
