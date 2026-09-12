# AUDIT_LOG.md — SEAM

Integrity findings, canary results, drift verdicts, incidents, discards, and amendments.
Governed by `docs/SEAM_research_blueprint.md` §5 (audit and data-integrity standard); §5.6
requires an append-only weekly entry.

**Scope:** this log covers the SEAM harness (`seam/`, `configs/`, `raw/`, `derived/`,
`figures/`) and the Platform A provenance documents under `analysis/aipc-c1/`. The unrelated
projects in this repository (`apu_characterization/`, `censor/`, `orchestration_engine/`) are
out of scope and have their own audit trails.

**Append-only.** Never edit or delete an existing entry. Corrections are new entries that
reference the entry they supersede.

---

## 2026-07-29 — AF-001 — Platform mislabel in the provenance document

**Class:** provenance integrity
**Found:** 2026-07-29, before any SEAM data collection
**Milestone:** M0
**Blueprint reference:** Appendix B / AF-001; §5.2 (run manifest); §14.2 amendment log entry
2026-07-29

### Found

`analysis/aipc-c1/MACHINE.md` labelled the CPU
`Intel(R) Core(TM) Ultra 5 325 (Lunar Lake)`. The part is **Panther Lake**.

The mislabel occurred **twice**, not once. Blueprint AF-001 and spec §7/M0 both name only
"line 12":

| Location | Original text |
|---|---|
| Identity table, line 12 | `Intel(R) Core(TM) Ultra 5 325 (Lunar Lake)` |
| Memory (UMA) table, line 24 | `On-package LPDDR5X (Lunar Lake memory-side cache / UMA)` |

Both were corrected. The second occurrence is logged as amendment **AM-001** in
`AMENDMENTS.md` because it is a divergence from the governing document's description of the
finding, not merely an implementation detail.

### Blast radius

`MACHINE.md` is the provenance source for the `platform` block of every run manifest (§5.2).
Uncorrected, every manifest would inherit a wrong silicon generation, and every figure caption
or paper claim derived from a manifest would misattribute it. Caught before data collection, so
**no emitted number is affected**. No `raw/` run directories existed at the time of the
correction, so no manifest required reissue.

### Evidence recorded

Written into `analysis/aipc-c1/MACHINE.md` § "Platform identification evidence (AF-001)",
partitioned by independence:

**Load-bearing (probe-attested, mutually independent):**

- **E1** — SKU `Core Ultra 5 325` is a 3xx part → Core Ultra Series 3 → Panther Lake
  (Lunar Lake is 2xxV). Source: `analysis/_c1_machine_probe.txt` line 17, verbatim
  `Intel(R) Core(TM) Ultra 5 325`.
- **E2** — Graphics PCI device ID `DEV_B090` is in the Xe3 range (Lunar Lake is `64A0`, Xe2).
  Source: `analysis/_c1_drivers_probe.txt` line 4, verbatim
  `PCI\VEN_8086&DEV_B090&SUBSYS_0DBA1028&REV_00\3&11583659&0&10`.

E1 comes from a CPU brand string, E2 from PCI enumeration — different subsystems, and they
agree. **The identification rests on E1 and E2.**

**Non-independent (human inference — marked as such in MACHINE.md):**

- **E3** — core names **Cougar Cove / Darkmont**. **This is an inference, not a probe-reported
  field.** Per spec §7/M0 item 4, this was checked directly: the strings `Cougar`, `Darkmont`,
  `Lion Cove`, and `Skymont` appear in **none** of the five committed probe artifacts. Windows
  exposes no microarchitecture code-name field. The names were supplied from vendor
  documentation *after* Panther Lake was concluded from E1, so citing them as evidence for
  Panther Lake is **circular**. Marked `NON-INDEPENDENT` in MACHINE.md.
- **E4** — `Xe3` is an inference from E2; the string appears in no artifact. The raw DID is the
  evidence, "Xe3" is its interpretation.
- **E5** — `Panther Lake` as a literal string appears in no artifact; it is the conclusion.

**Explicitly non-discriminating:** the 4 P + 4 LP-E, 8C/8T, no-SMT topology **does not**
distinguish Panther Lake from Lunar Lake — Lunar Lake has the identical signature (4 Lion Cove
+ 4 Skymont, 8C/8T, no SMT). Recorded in MACHINE.md as invalid reasoning.

### Additional provenance gaps found while auditing

Recorded, not fixed — `analysis/` probe artifacts are read-only under spec §9.1. Full detail in
MACHINE.md § "Provenance gaps found while auditing".

1. `_c1_mem_probe.txt` is effectively empty (a `wmic` SPD header that returned no rows). The
   memory table's 8 × 2 GiB banks and `ConfiguredClockSpeed=7467` are **not attested by any
   committed artifact**.
2. `_c1_probe.txt` contains no hardware content — a timestamp, the hostname, and `done`.
3. `_c1_machine_probe.txt` is internally inconsistent: line 3 `Microsoft Windows 11 Home` vs
   line 19 `Windows 10 Home 25H2 build 26200.8875` (stale registry `ProductName`).
4. No probe captures CPU microarchitecture, core topology, microcode, or `EfficiencyClass`.
   **The 4P/4LP-E split is unverified by artifact** and is verified empirically by
   `seam/topology.py` under M1.
5. NPU model `NPU 5` / `NPU 5010` and its 50 TOPS figure are **not** probe-attested; the probe
   attests only `Intel(R) NPU`, `ComputeAccelerator`, `oem127.inf`/`npu.inf`. 50 TOPS is a
   vendor **peak INT8** figure and is never to be reported as achieved.

### Action taken

- Corrected both occurrences in `analysis/aipc-c1/MACHINE.md`.
- Added the auditable evidence section with independence classification.
- Added the explicit non-discrimination note for the 4+4/8T topology.
- Recorded the divergence from AF-001's "line 12" wording as AM-001 in `AMENDMENTS.md`.

**Correction commit SHA:** `PENDING-SHELL-RESTORATION`

> This log entry cannot be completed until a shell is available. The shell backend was
> **non-functional for the entire M0/M1 session** (see AF-003 below), so `git commit` could not
> be executed and no SHA exists to record. The MACHINE.md correction is present in the working
> tree. **On shell restoration: commit the correction and replace the placeholder above with the
> real SHA in a new appended entry.** Under the append-only rule this entry is not edited; the
> follow-up entry supersedes this field.

---

## 2026-07-29 — AF-002 — Probe artifacts are recorded, not live

**Class:** provenance freshness
**Found:** 2026-07-29 (originally logged in blueprint Appendix B)
**Milestone:** M0 (item 5) — **NOT DISCHARGED**
**Blueprint reference:** Appendix B / AF-002; §16.1

### Found

Blueprint §16.1's confirmed configuration rests on artifacts recorded **2026-07-28**, not on a
live probe, because the shell backend was unavailable in the session that produced it.

### Blast radius

Low but non-zero. Driver and firmware versions can change between recording and measurement,
and §5.2 requires them in every manifest. Specifically at risk: iGPU driver `32.0.101.8622`,
NPU driver `32.0.100.4724`, BIOS `1.8.2`, OS build `26200.8875` — any Windows Update between
recording and measurement invalidates these.

### Required action (per blueprint)

On shell restoration: re-run the probe, diff against the committed artifacts, and record the
probe-artifact SHA-256 values in the manifest emitter so every run pins the exact provenance
snapshot it relied on.

### Status this session: **NOT DISCHARGED — still open**

AF-002 could **not** be closed. The shell backend was non-functional for the entire session
(AF-003), so:

- The probe could **not** be re-run. No diff against the committed artifacts exists.
- Artifact SHA-256 values could **not** be computed. Computing a file hash requires executing
  code; it cannot be done by reading a file through an editor, and a hash transcribed by hand
  from a rendered file view would be fabricated. **No hash was invented.**

The manifest emitter (`seam/manifest.py`) is nonetheless wired for this: it computes
`platform.provenance_artifacts[].sha256` **at emit time** by hashing the artifact bytes on disk,
so the values are measured at run time rather than transcribed from this log. The artifact path
list is declared in `configs/platforms/aipc-c1.yaml`. There is therefore no hardcoded hash
anywhere to go stale — but equally, **no hash is committed yet**, so this half of M0's
acceptance criterion is outstanding.

**Blocks:** M0 acceptance (partial — "artifact hashes committed"). Does not block M1 code, which
computes hashes at runtime.

---

## 2026-07-29 — AF-003 — Shell backend non-functional during M0/M1

**Class:** harness / tooling availability
**Found:** 2026-07-29, at the start of the M0/M1 session
**Milestone:** M0, M1
**Raised by:** this session (new finding; not in blueprint Appendix B)

### Found

Every shell invocation returned `the shell command returned no exit status, so its result is
unknown` — including trivial commands (`Write-Output`, `git rev-parse HEAD`, `cmd /c echo`).
This was **verified to be genuine non-execution, not merely unreported success**: a command was
issued to write a probe file into the repository, and the file was subsequently confirmed absent
from disk. Commands are not running.

This is the same condition that produced blueprint AF-002 in the prior session, recurring. It
is recorded as its own finding because it is now a **repeated** environmental failure with a
direct effect on which acceptance criteria can be met, rather than a one-off.

**Independent corroboration.** The diagnosis was reproduced from a second, separately spawned
process, which ruled out a per-session fault:

| Probe | Shell | Result |
|---|---|---|
| `Write-Output hello` | PowerShell | no exit status, no stdout |
| `echo probe_sub_2` | PowerShell | no exit status, no stdout |
| `cmd /c echo probe_sub_3` | `cmd.exe` | no exit status, no stdout |

The third probe was deliberately routed through `cmd.exe` rather than PowerShell and failed
identically, which localises the fault to the **shell-execution layer of the tool harness**, not
to a PowerShell profile, a PowerShell host hang, or a credential/lock prompt. The environment
requires a restart. A bare `Write-Output hello` returning actual stdout is a sufficient check
that it has recovered.

### Blast radius

Blocks every acceptance criterion that requires executing code:

| Blocked | Milestone | Consequence |
|---|---|---|
| `git commit`, `git rev-parse` | M0 | No correction commit SHA for AF-001 |
| Probe re-run and diff | M0 (AF-002) | AF-002 stays open |
| `Get-FileHash` on probe artifacts | M0 | No committed artifact hashes |
| Topology microbenchmark on real silicon | M1 | P/LP-E split **not** empirically verified; open question 4 unanswered |
| `pytest`, `ruff`, `mypy` | M1 | Test suite authored but **never executed** |

### Action taken

- Recorded rather than worked around. **No result that requires execution was fabricated,
  estimated, or transcribed by hand.**
- `configs/platforms/aipc-c1.yaml` ships with `topology.verified: false` and
  `p_cpus`/`lpe_cpus` set to `null`, so the unverified state is explicit in config rather than
  implied by a plausible-looking default. `seam/topology.py` refuses to return an affinity list
  from unverified config unless verification is explicitly waived, and the waiver is logged.
- Milestone status reported honestly as partial rather than as passing.

### Required action

On shell restoration, in order:

1. `ruff check`, `mypy`, `pytest` — confirm the authored suite is green.
2. `python -m seam.topology verify --write` — measure the P/LP-E split, flip
   `topology.verified` to `true`, and answer open question 4 (does `EfficiencyClass` ordering
   match the measured split?).
3. Re-run the hardware probe, diff against committed artifacts (AF-002).
4. Commit; append a new entry recording the AF-001 correction SHA and the AF-002 diff result.

**Until steps 1–3 pass, M0 and M1 are NOT accepted and M2 must not begin.**

---

## 2026-07-29 — AF-003 RESOLVED — execution restored, root cause identified

**Class:** harness / tooling availability
**Milestone:** M0, M1
**Relationship:** supersedes the "Required action" list in the AF-003 entry above. Under the
append-only rule that entry is not edited.

### Root cause

**Not a permission denial.** This Windows host has **no sandbox backend**, so any tool call that
asked for the `workspace_readwrite` sandbox policy could not be satisfied. Depending on the call it
either failed explicitly with `Terminal unavailable: this machine cannot enforce the
'workspace_readwrite' sandbox policy`, or returned "no exit status" — *total non-execution*, which is
indistinguishable from a hang from the caller's side. The previous session's localisation ("the
shell-execution layer of the tool harness, not a PowerShell profile or a credential prompt") was
correct as far as it went, but it attributed the fault to the shell itself rather than to
sandbox-policy enforcement sitting in front of the shell.

The previous session's verification method was sound and is worth keeping: a command was issued to
write a file, and the file was then confirmed absent. That is what distinguished non-execution from
unreported success.

### Resolution

Commands on this host must be issued with **unsandboxed execution**. Every command in this session
was issued that way and produced real exit codes and observable side effects. Side effects were
confirmed by reading files back rather than by trusting a command's own report — the same discipline
that diagnosed the fault.

### AF-003 required actions — status

| Step | Status |
|---|---|
| 1. `ruff`, `mypy`, `pytest` | **DONE** — all three clean; see "First execution of the toolchain" below |
| 2. `python -m seam.topology verify --write` | **RAN, DID NOT PASS.** `topology.verified` remains `false`. See "Topology verification" below |
| 3. Re-run the probe, diff against committed artifacts | **DONE** — AF-002 discharged below |
| 4. Commit, append the correction SHA | **DONE** — this entry |

---

## 2026-07-29 — AF-001 correction commit SHA

**Relationship:** supplies the value left as `PENDING-SHELL-RESTORATION` in the AF-001 entry above.
That entry is not edited; this entry supersedes the field.

**Correction commit SHA:** `c034b41c12f491458d302954ea6650e3386efaf9`

47 files: the harness (`seam/`, `tests/`, `configs/`, `pyproject.toml`, `.gitattributes`), the
governing documents under `docs/`, `AMENDMENTS.md`, `AUDIT_LOG.md` in its pre-this-entry state, the
corrected `analysis/aipc-c1/MACHINE.md`, `analysis/aipc-c1/TOOLING.md`, the five committed probe
artifacts, and the AF-002 re-capture.

Deliberately **excluded**: `raw/`, `derived/`, `figures/`, every `_tmp_*` scratch file, and
everything belonging to `apu_characterization/`, `censor/`, and `orchestration_engine/`, which remain
uncommitted and untouched. `.gitignore` was staged **partially** — only its SEAM section — because
its working-tree diff also carried another project's ignore rules.

> **Open item.** `raw/` is deliberately *not* gitignored, because blueprint §5.3 and §5.7 require the
> raw data to be committed for artifact evaluation. This commit nonetheless excludes `raw/` on
> instruction. The manifest emitted by the M1 smoke test below therefore exists on disk but not in
> git. Reconcile before M2: either commit `raw/` as the blueprint intends, or amend the blueprint.

---

## 2026-07-29 — AF-002 DISCHARGED — probe re-run, diffed, and hashed

**Class:** provenance freshness
**Milestone:** M0 item 5
**Relationship:** discharges the AF-002 entry above, which recorded "NOT DISCHARGED — still open".

### What was done

The probe was re-run by `analysis/aipc-c1/scripts/reprobe_af002.ps1` (new, committed, so the
re-capture is repeatable rather than ad hoc — the originals were produced by interactive commands
with no script behind them). Fresh output went to a **new** directory,
`analysis/aipc-c1/reprobe_af002_2026-07-29/`. The five committed artifacts are read-only under spec
§9.1 and were **not** modified, re-encoded, or overwritten. The diff was produced by
`analysis/aipc-c1/scripts/diff_af002.py` and is committed as
`analysis/aipc-c1/reprobe_af002_2026-07-29/DIFF_vs_committed.md`.

### SHA-256 of the committed provenance artifacts

Computed from bytes on disk. Independently reproduced by the manifest emitter at emit time during the
M1 smoke run below, and the two agree.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `analysis/aipc-c1/MACHINE.md` | — | `d8839946bd6f591051d78968b3a1e022ba35b68070a001628d9f800346636ee2` |
| `analysis/aipc-c1/TOOLING.md` | — | `77c949f9d9614acf24333379dbab307d33b3cefe4efc7aea1f39cc2e03d4c26c` |
| `analysis/_c1_machine_probe.txt` | 1402 | `b6917b7ad7eb6dff899ec855eab9b41fa087510fa104efd1357f518e4bdc83e0` |
| `analysis/_c1_drivers_probe.txt` | 7848 | `9b95cdf75961f23897bda5d97ad5fb4b778ff1d4ad60632b1826cd1f447f0a9d` |
| `analysis/_c1_probe.txt` | 94 | `f8c333e43ca98b1de9438e8abb2bf481547419ccd7f2af86d718bb7235d28573` |
| `analysis/_c1_mem_probe.txt` | 264 | `f83cd5d261fa29ba7f732567d9683ac5632ab0cdb285ea06d68e6a755dc7804c` |
| `analysis/_c1_tools_probe.txt` | 15464 | `8c5544481eb0025274eb221a19cf52cb81d8521b625a47417fb9ef322360871f` |

### Diff outcome

**No contradiction of any load-bearing claim.**

- `_c1_machine_probe.txt` re-captured **identically** after whitespace normalisation. E1 (the SKU
  string `Intel(R) Core(TM) Ultra 5 325`) is unchanged.
- E2 (`DEV_B090`) re-captured unchanged.
- Driver versions are unchanged from the AF-002 blast-radius list: iGPU `32.0.101.8622`
  (2026-02-18 local), NPU `32.0.100.4724` (2026-03-18 local). No Windows Update intervened.
- Total physical memory unchanged (`15,976 MB`; `TotalPhysicalMemory=16752234496`, which is exactly
  15976 MiB).

### Provenance gaps closed

**Gap 1 (memory) — CLOSED.** `_c1_mem_probe.txt` captured zero rows because it used `wmic`, which is
removed on Windows 11 25H2. Re-captured via CIM `Win32_PhysicalMemory`, which returns 8 rows. The
memory table in MACHINE.md is now attested by artifact and **confirmed exactly**: 8 banks ×
2147483648 bytes (2 GiB), `DeviceLocator=Motherboard`, `Speed=9600`, `ConfiguredClockSpeed=7467`,
`SMBIOSMemoryType=35` (LPDDR5), `ConfiguredVoltage=500`. `Win32_PhysicalMemoryArray` independently
reports `MemoryDevices=8` and `MaxCapacity=16777216` KB. Vendor/part number remain null, as
MACHINE.md already stated.

**Gap 4 (core topology / EfficiencyClass) — CLOSED as to capture, not as to verification.**
`topology_probe.txt` records, for the first time in any artifact: `NumberOfCores=8`,
`NumberOfLogicalProcessors=8` (confirming 8C/8T, no SMT), and per-core `EfficiencyClass` from
`GetLogicalProcessorInformationEx` — cores 0–3 class 1, cores 4–7 class 0, `smt=False` on all eight.
The artifact carries an explicit note that this is the **OS hypothesis only** and that spec §4
requires the microbenchmark to establish the P/LP-E split. Capturing the hypothesis does not verify
it.

> MACHINE.md's statement that "no probe captures CPU microarchitecture, core topology, microcode, or
> `EfficiencyClass`" remains true **of the five committed original artifacts**, which is the set it
> refers to. It is now false of the re-capture. MACHINE.md is read-only and was not edited; this
> entry is the record.

**Gaps 2, 3, 5 — unchanged and still open.** `_c1_probe.txt` still carries no hardware content (no
counterpart was captured; there is nothing there to re-capture). The `Windows 11 Home` vs
`Windows 10 Home 25H2` internal inconsistency is reproduced by the fresh capture, confirming it is a
stale registry `ProductName` reporting artifact rather than a transcription error. NPU model and the
50 TOPS peak figure remain not probe-attested; the fresh capture attests only
`Device Description: Intel(R) NPU`, `Class Name: ComputeAccelerator`, `oem127.inf`/`oem66.inf`.

### New evidence bearing on AF-001

`topology_probe.txt` captures `Description: Intel64 Family 6 Model 204 Stepping 3`. **Family 6
Model 204 (0xCC)** is a CPUID signature, read from CIM, and is a **third mutually independent
discriminator** alongside E1 (CPU brand string) and E2 (graphics PCI DID) — it comes from the CPUID
leaf rather than from a brand string or PCI enumeration. Lunar Lake is a different signature.

Classified with the same discipline as E2: the **raw value `Family 6 Model 204` is probe-attested**;
the mapping "Model 204 → Panther Lake" is **vendor documentation, i.e. interpretation**, exactly as
"DID B090 → Xe3" is. Cite the raw signature, not the code name. Recorded here rather than in
MACHINE.md, which is read-only.

### Elevation limit

`pnputil /enum-drivers` (the driver-store section of the original artifact) **requires
Administrator**, which this session did not have. The fresh capture records
`PROBE_SKIPPED: pnputil /enum-drivers requires elevation; not elevated in this session.` rather than
omitting the section silently. Driver versions were obtained unelevated via
`Win32_PnPSignedDriver`, which is why the version comparison above was still possible. Re-run
elevated to close the driver-store half.

---

## 2026-07-29 — First execution of the toolchain; defects found and fixed

**Class:** harness correctness
**Milestone:** M1

`ruff check` — clean. `mypy` — clean, 19 source files. `pytest` — **148 passed**, 0 failed,
0 skipped, 0 xfailed. As inherited, the suite reported 14 ruff findings, 21 mypy errors, and
2 failing tests. **No test was weakened, skipped, xfailed, or deleted.**

| Defect | Where | Fix |
|---|---|---|
| Probe artifacts decoded as UTF-8 but are UTF-16LE | `tests/test_provenance.py` | Decode on the byte-order mark. See AF-004 — this is a finding, not just a bug |
| mypy override for tests matched no module | `pyproject.toml` | `tests/` had no `__init__.py`, so mypy named the modules `conftest`/`test_*`, not `tests.*`. Added `tests/__init__.py`; annotated the `RunDir` fixtures rather than relaxing strictness |
| `float ** float` is `Any` under `warn_return_any` | `seam/topology.py` `_cv` | `math.sqrt` |
| `marker["raw_sha256"]` is `Any` | `seam/rawstore.py` `verify_sealed` | Explicit `str` annotation |
| `raise` in an `except` clause without a `from` cause | `seam/topology.py` `affinity_for` | `from exc` |
| `os.stat` where `Path.stat` applies; unused `os` import | `seam/rawstore.py` | `child.stat()` |
| Dead mypy override for `jsonschema.*` | `pyproject.toml` | Removed; `warn_unused_configs` was reporting it on every run |
| Line length, `UP012`, `UP017`, `RUF005`, `ARG005`, import order | 6 files | Mechanical |

**No test encoded a requirement the code failed to meet.** Both failures were the test *reading* the
artifact wrongly; the artifacts contained what the tests asserted all along.

`test_committed_config_ships_unverified` — the AM-008 tripwire — **still passes and was not
touched**, because topology verification did not succeed and the committed config still carries
`verified: false`, `p_cpus: null`, `lpe_cpus: null`, `measured.run_id: null`. The transition that
test anticipates has not yet occurred.

---

## 2026-07-29 — AF-004 — Probe artifacts are UTF-16LE; three provenance tests were vacuous

**Class:** provenance integrity / test validity
**Milestone:** M0
**Raised by:** this session (new finding)

### Found

All five committed probe artifacts are **UTF-16LE with a BOM** (`ff fe`), because they were produced
by Windows PowerShell 5.1 output redirection. `tests/test_provenance.py` read them with
`read_text(encoding="utf-8", errors="replace")`.

Two tests failed outright, which is how this was found. The more serious consequence is the three
that **passed vacuously**: `errors="replace"` turns the file into mojibake in which *no* substring is
ever found, so an assertion of the form "this string appears in **no** artifact" is satisfied by
construction and tests nothing.

| Test | Before | After correct decoding |
|---|---|---|
| `test_sku_string_is_probe_attested` | failed | passes — E1 genuinely attested |
| `test_graphics_device_id_is_probe_attested` | failed | passes — E2 genuinely attested |
| `test_core_names_appear_in_no_probe_artifact` (×4 names) | passed **vacuously** | passes for real — E3's `NON-INDEPENDENT` classification is now genuinely evidenced |
| `test_probe_artifacts_do_not_attest_the_core_topology` | passed **vacuously** | passes for real — no original artifact contains `EfficiencyClass` |

### Blast radius

The AF-001 evidence classification (E1/E2 load-bearing, E3 inferred) was **correct**, but two of the
tests asserting it were not actually checking it. The conclusion survives; the assurance behind it
did not exist until now.

### Action taken

`read_probe_text()` decodes on the BOM and **does not** pass `errors="replace"` — an artifact this
project cannot decode is a finding to report, not damage to paper over. The artifacts were **not**
re-encoded on disk: they are read-only under §9.1, so the reader adapts, not the evidence.

---

## 2026-07-29 — Topology verification RAN but did NOT establish the mapping

**Class:** measurement / milestone status
**Milestone:** M1 — **NOT ACCEPTED**
**Spec reference:** §4; §10 open question 4

### Result

`python -m seam.topology verify` was executed twice on the target hardware. Both runs **refused** to
verify, and `configs/platforms/aipc-c1.yaml` still carries `topology.verified: false` with null
CPU lists. `--write` was therefore never allowed to take effect.

The clusters separated **cleanly in ordering** — all of CPUs 0–3 faster than all of CPUs 4–7, no
interleaving, in the expected 4/4 sizes, both runs — but the **magnitude** of separation fell below
the acceptance threshold:

| Run | Fast-cluster mean | Slow-cluster mean | Ratio | Threshold | Verdict |
|---|---|---|---|---|---|
| 1 | 5.350 M work-units/s (CPUs 0–3) | 4.772 M (CPUs 4–7) | **1.121×** | ≥ 1.25× | REFUSED |
| 2 | 5.475 M (CPUs 0–3) | 4.615 M (CPUs 4–7) | **1.186×** | ≥ 1.25× | REFUSED |

Per-CPU scores, M work-units/s:

| CPU | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| Run 1 | 5.374 | 5.248 | 5.368 | 5.409 | 4.914 | 4.868 | 4.700 | 4.604 |
| Run 2 | 5.268 | 5.606 | 5.442 | 5.585 | 4.600 | 4.426 | 4.830 | 4.604 |

Within-cluster coefficient of variation, computed from the logged scores (the tool checks separation
before CV and so never reported them): run 1 — 1.1% fast, 2.6% slow; run 2 — 2.5% fast, 3.1% slow.
All far inside the 15% limit. **The clusters are tight; they are simply close together.**

> **These numbers have no `run_id` and are NOT quotable.** `verify_topology` raises before
> `emit()` is reached, so a failed verification produces no manifest — see AF-006. They are recorded
> here as diagnostic evidence for *why* M1 is not accepted, not as a measurement result.

### The threshold was not lowered

`min_cluster_separation_ratio: 1.25` was left untouched. Its documented rationale is the vendor
frequency gap (P 2.1/4.5 GHz vs LP-E 1.6/3.4 GHz). Editing a config threshold to make a refusing
measurement pass would manufacture a verified mapping, which is precisely what AM-008 and the
tripwire test exist to prevent.

### Why the separation is probably compressed

Two candidate causes, neither yet isolated:

1. **The host is on battery** (`PowerOnline=False`, 24–26%), under the **Balanced** power plan. This
   independently invalidates the session — see AF-005. Battery power limiting clamps P-core turbo
   hardest, which compresses exactly the gap being measured.
2. **The kernel is a CPython bytecode loop.** Interpreter dispatch and reference counting dominate
   its cost, which compresses an IPC and frequency difference between core types. This is a property
   of the instrument, not of the silicon, and it may not clear 1.25× even on AC power.

### Open question 4 — provisional answer, NOT a verified result

`EfficiencyClass` from `GetLogicalProcessorInformationEx`: CPUs 0–3 = **1**, CPUs 4–7 = **0**.
Measured-fast cluster = {0,1,2,3} in both runs.

**The EfficiencyClass ordering MATCHED the measured split**, in the documented direction
(higher `EfficiencyClass` = faster = P-core), with the partitions identical as sets. Spec §4's
warning did not materialise on this platform.

This answer is **provisional and must not be recorded as closing open question 4.**
`_evaluate_efficiency_class_agreement` is only reached *after* the separation gate passes, so the
harness itself never computed this comparison — it is derived here by hand from the enumerated
`EfficiencyClass` map and the logged scores. Open question 4 is answered when a run that **passes**
verification records `efficiency_class_ordering_matched: true` with its `run_id`.

### To close M1

1. Put the host on **AC power** and activate the pinned plan (AF-005). Quiesce background load.
2. Re-run `python -m seam.topology verify --write`.
3. If it passes: the tripwire `test_committed_config_ships_unverified` must be updated **in the same
   commit** that records the measurement's `run_id`, so the change is visible in review.
4. If it still refuses on AC power with a quiet machine, the finding is that **the microbenchmark
   kernel is not discriminating enough on this platform** — a spec §4 instrument decision for the
   spec owner. Do not resolve it by moving the threshold.

---

## 2026-07-29 — AF-005 — Session violates MACHINE.md pinned run conditions

**Class:** session validity
**Milestone:** M1
**Raised by:** this session (new finding)

### Found

`analysis/aipc-c1/MACHINE.md` § "Pinned run conditions (MANDATORY)" states that sessions violating
them are **INVALID, not noisy**, and requires **AC power (`ACLineStatus=1`)** and the pinned
`Best Performance` plan. Observed during this session:

| Condition | Required | Observed |
|---|---|---|
| AC power | `ACLineStatus=1` | **`PowerOnline=False`** — on battery, 24–26% |
| Power plan | `Best Performance` `ec87a53a-…` | **Balanced** `381b4222-f694-41f0-9685-ff5bb260df2e` |
| Background load | quiesced | **~26% total CPU** (Chrome, Cursor, and other agent processes) |

This is the **same violation** MACHINE.md already records for its own "Item 0 snapshot (NOT a valid
measurement session)": AC offline, Balanced active, pinned plan present but not activated. It has now
recurred, which makes it a standing condition rather than a one-off.

Note also that `powercfg /list` reports **only** Balanced on this SKU. The pinned GUID
`ec87a53a-19a6-4f4a-980f-ab27cc929b25` is a Windows **power-mode overlay**, not a listed scheme,
consistent with MACHINE.md's own note that it "may be omitted from `powercfg /list` on this SKU".
`analysis/aipc-c1/scripts/assert_power_pin.ps1` exists but was not run as a gate.

### Action taken

**Nothing was changed on the machine.** The power plan was not switched and no user process was
killed: quiescing a machine by terminating another party's applications is not this session's call to
make, and switching the power plan at 24% battery would not have satisfied the AC requirement
anyway. The condition is recorded instead.

Consequently the topology runs above are **invalid as measurement sessions on two independent
grounds** — they failed their own acceptance threshold, *and* they ran outside the mandatory pinned
conditions. Either alone is sufficient to withhold `verified: true`.

### Required action

Before any M1 or M2 measurement: plug in, activate the pinned overlay, run
`assert_power_pin.ps1` as a **gate that aborts** rather than as an advisory, and close background
load. Wiring that assertion into the harness so a run cannot start outside pinned conditions is the
durable fix; it is M2 scope and was not built here.

---

## 2026-07-29 — AF-006 — A failed topology verification emits no manifest

**Class:** traceability
**Milestone:** M1
**Raised by:** this session (new finding)
**Status:** OPEN — design decision for the spec owner, deliberately **not** resolved unilaterally

### Found

In `seam/topology.py:main`, `verify_topology(config)` runs **before** `emit(...)`. A verification
that refuses therefore raises, and no manifest, no `run_id`, and no `raw/<run_id>/` directory are
produced. The measurement it took — eight per-CPU scores, the cluster ratio, the `EfficiencyClass`
map — survives only in console output.

That collides with spec §9.2 ("no number without a `run_id`"). The per-CPU scores in the topology
entry above are exactly such numbers: real measurements of real silicon, with nothing to cite. A
negative result is still a result, and "the P/LP-E split could not be established, here is the
evidence" is a finding a reviewer should be able to trace.

### Why it was not fixed here

The natural fix — emit a manifest with `integrity.self_check: "fail"` — collides with the schema.
`run_manifest.schema.json` constrains `target` to `["cpu-p","cpu-lpe","igpu","npu","cloud"]`, and
`allOf[2]` requires `platform.topology.verified: true` whenever `target` is `cpu-p` or `cpu-lpe`. A
failed verification must not claim `verified: true`, and **no target value honestly describes a
diagnostic run that establishes nothing.** Emitting one would need a new `target` value or a relaxed
constraint — a change to the governing schema, which requires an `AMENDMENTS.md` entry and a
`spec_version` decision. Not a change to make silently while closing out someone else's milestone.

### Recommended resolution

Add a non-execution target (e.g. `host`, or `self-check`) to the schema `target` enum, exempt it from
the verified-topology precondition, and have `main()` emit a `self_check: "fail"` manifest carrying
the measurement before propagating the error. Record as an amendment.

---

## 2026-07-29 — AF-007 — Line-ending normalisation would have broken cited artifact hashes

**Class:** provenance integrity
**Milestone:** M0
**Raised by:** this session (new finding)
**Status:** RESOLVED in `c034b41c12f491458d302954ea6650e3386efaf9`

### Found

This repository has `core.autocrlf=true` and had **no `.gitattributes`**. Git therefore normalises
text files to LF in the index and rewrites them to CRLF on checkout. `seam/manifest.py` hashes each
provenance artifact **from bytes on disk at emit time**, so for any artifact git considers text, the
hash recorded in a manifest depends on which platform performed the checkout. A manifest emitted on
Windows would fail to reproduce on Linux, and vice versa — silently, with no error anywhere.

Caught by comparing staged blob bytes against working-tree bytes before committing: the fresh AF-002
capture files had been written CRLF and were normalised to LF in the index, so the SHA-256 values
recorded in `DIFF_vs_committed.md` did not match their own committed bytes.

The five original probe artifacts were **never at risk**: git classifies UTF-16 as binary and leaves
it alone, which is why their hashes were stable throughout. `MACHINE.md` and `TOOLING.md` *were* at
risk, and both are named in `provenance_artifacts`.

### Action taken

1. `analysis/aipc-c1/scripts/reprobe_af002.ps1` now writes LF explicitly rather than via
   `WriteAllLines` (which uses CRLF on Windows); `diff_af002.py` writes its report with
   `newline=""`. The capture was regenerated and the report recomputed from the LF files.
2. Added `.gitattributes` marking the SEAM provenance paths `-text`, so committed bytes are checkout
   bytes on every platform: `analysis/_c1_*.txt`, `analysis/aipc-c1/MACHINE.md`,
   `analysis/aipc-c1/TOOLING.md`, `analysis/aipc-c1/reprobe_af002_*/**`, and `raw/**` — the last
   because a sealed run's tree hash is checked by `verify_sealed()` and an end-of-line rewrite would
   fail it. Scoped to SEAM paths only; nothing changes for the other projects in this repository.
3. Verified after staging that all 45 SEAM content files were byte-identical between index and
   working tree. (`.gitignore` differs by design — partial stage.)

---

## 2026-07-29 — M1 manifest and write-once guards verified against the real repository

**Class:** milestone verification
**Milestone:** M1
**Run ID:** `4042b031-6d78-48d9-b142-ba9804bd6e64`

`tests/test_manifest.py` and `tests/test_rawstore.py` cover these guards with git and the filesystem
mocked. A mocked guard passing and a real guard passing are different claims, so all of them were
additionally exercised end to end against the real dirty tree, the real provenance artifacts, and a
real sealed `raw/` directory. **26 of 26 checks passed.**

| M1 criterion | Result |
|---|---|
| `emit()` produces a schema-valid manifest | PASS — re-read from disk and validated against `run_manifest.schema.json` |
| Dirty tree refused without `--allow-dirty` | PASS — refused with 101 uncommitted paths, and **no run directory was created** |
| `--allow-dirty` recorded in the manifest | PASS — `git_dirty: true`, `allow_dirty: true`, and all 101 paths enumerated in `git_dirty_files` |
| Provenance artifacts hashed at emit time | PASS — 7 of 7; values match the independently computed hashes in the AF-002 table above |
| `raw/` write-once guard refuses modification of a sealed run | PASS — all 7 mutating paths refused (`write_text` on a new and on an existing file, `write_json`, `append_ndjson` on a new and on an existing file, `open_write`, re-`seal`), including after reopening the directory by `run_id`. No stray file landed |
| `verify_sealed()` confirms the recorded tree hash | PASS |
| Schema refuses `target: cpu-p` while topology is unverified | PASS — the M1 precondition holds against the real config |
| Thermal constants null, not defaulted to spec §6.1 examples | PASS (AM-006) |
| `blinded_label` does not leak the condition | PASS |

`elevated: false` is recorded truthfully; this session was not elevated. The manifest correctly
reports `topology: {p_cpus: null, lpe_cpus: null, verified: false}`.

---

## 2026-07-29 — Milestone status after this session

**M0 — ACCEPTED**, with one instruction-driven caveat.

- AF-001 corrected, evidence classified, and now committed: `c034b41c12f491458d302954ea6650e3386efaf9`.
- AF-002 discharged: probe re-run, diffed, artifact SHA-256 values committed. No load-bearing claim
  contradicted; two provenance gaps closed; a third independent AF-001 discriminator found.
- Caveat: `raw/` was excluded from the commit although the blueprint requires it to be committed.
  See the AF-001 SHA entry above.

**M1 — NOT ACCEPTED.** One criterion outstanding:

- Manifest emission, schema validation, dirty-tree refusal, `--allow-dirty` recording, and the
  `raw/` write-once guard are all verified against the real repository (26/26).
- Toolchain green: ruff, mypy, 148 tests.
- **Topology verification is not established.** `topology.verified` remains `false`, so spec §10 open
  question 4 is not closed and AM-008 stays OPEN. Blocked on AC power (AF-005), and possibly on the
  discriminating power of the microbenchmark kernel itself.

**M2 must not begin.** No telemetry, LHM bridge, energy, or thermal code was written this session.
The `cpu-p` and `cpu-lpe` targets cannot be used at all until the mapping is verified — the schema
enforces this, and `affinity_for` refuses.

---

## 2026-07-30 — AF-006 RESOLVED — a refused verification now emits a manifest

**Class:** traceability
**Milestone:** M1
**Status:** RESOLVED in `899bf23b4c8909639566dfd924312a574afaeeea`
**Relationship:** discharges the AF-006 entry above, which was left OPEN as a design decision for
the spec owner. Decision taken by Z. Johnson on 2026-07-29 and recorded as `AMENDMENTS.md` AM-010.

### What changed

| Change | Where |
|---|---|
| `workload.kind` gains `topology_verify` | `seam/schemas/run_manifest.schema.json` |
| The `cpu-p`/`cpu-lpe` verified-topology precondition is exempted for that kind only, keyed on `workload.kind` rather than on `target` | same |
| New rule: `topology_verify` + `topology.verified: false` ⇒ `integrity.self_check` **must** be `"fail"` | same |
| `measure_topology()` evaluates every criterion and returns a `verdict` + reasons; `verify_topology()` raises unless it passed | `seam/topology.py` |
| The CLI emits the manifest for either verdict, then propagates a refusal | same |
| The microbenchmark kernel is selected by name from config and recorded as `workload.benchmark` | same, `configs/platforms/aipc-c1.yaml` |
| Host power state captured into the manifest `power_state` block; pinned-condition deviations logged | `seam/powerstate.py` (new) |

**AF-006's own recommendation was not followed.** It suggested adding a non-execution `target`
(`host` / `self-check`). `target` enumerates execution targets and M4/M5 identify sweep cells by
it, so widening it for a diagnostic would weaken a load-bearing field. The workload kind carries
the diagnostic nature instead, and `target: cpu-p` is retained because establishing the
`cpu-p` / `cpu-lpe` mapping is precisely what the run does. Reasoning in full in AM-010.

**A hazard the fix creates, and its guard.** An exemption that lets a run declare
`verified: false` under a CPU target could let a refusal be filed as a success. Schema rule 3
above makes that combination invalid: a refused verification is *structurally* unable to report
`self_check: "pass"`. Covered by `test_refused_topology_verify_must_record_a_failing_verdict`.

**Side effect worth stating.** Because the earlier refused runs raised at the first failing check,
they could not report their within-cluster CV at all — the CV values in the topology entry above
were computed by hand afterwards. Every criterion is now evaluated and recorded, so a refusal
reports its full diagnostic picture.

`ruff` clean, `mypy` clean (21 source files), `pytest` **178 passed** (up from 148; 30 new tests,
none weakened, skipped, xfailed, or deleted).

---

## 2026-07-30 — Pinned run conditions: what was changed on the host, and why

**Class:** session validity
**Milestone:** M1
**Relationship:** follows AF-005, which required "plug in, activate the pinned overlay, run
`assert_power_pin.ps1` as a gate that aborts". This entry records the attempt and its outcome.

### State observed before any change (2026-07-30, ~10:52 local)

| Condition | Observed |
|---|---|
| AC | **online** — `ACLineStatus=1`, battery 29→31% and **charging** |
| Power plan | **Balanced** `381b4222-f694-41f0-9685-ff5bb260df2e` |
| Power-mode overlay | **`961cc777-2547-4f9d-8174-7d86181b8a7a`** — "Best power efficiency" |
| Battery saver | off (`SystemStatusFlag=0`) |
| Background load | ~12% total CPU (was ~26% in the previous session) |

The overlay is the finding here. AF-005 recorded the plan as Balanced but nothing had read the
Windows **power-mode slider**, which is a separate control: the host was running the *most
aggressive power-saving* overlay available while the previous topology runs were taken. That
clamps turbo directly.

### Changes made — power configuration only

1. **Activated the pinned plan** `ec87a53a-19a6-4f4a-980f-ab27cc929b25` ("Best Performance") by
   GUID. MACHINE.md predicted it "may be omitted from `powercfg /list` on this SKU — activate by
   GUID", and that is exactly the situation: `powercfg /list` shows only Balanced, but
   `powercfg /duplicatescheme` refused with *"a power scheme with the specified GUID already
   exists"*, which is how the scheme's presence was confirmed before activating it. **AF-005's
   inference that the pinned GUID is an overlay rather than a scheme was incorrect** — it is a
   hidden scheme, as MACHINE.md says.
2. **Set the power-mode overlay** to Best Performance `ded574b5-45a0-4f42-8737-46345c09c238`.
   Under the High-Performance-derived scheme Windows reports the *effective* overlay as the
   all-zero GUID (the slider does not apply to that scheme), which is what manifests now record.
   The "Best power efficiency" overlay is no longer in effect either way.

Nothing else was touched. **No user process was killed** and no non-power setting was altered.
`assert_power_pin.ps1` then exited **0** (`acOk=True planOk=True`) for the first time in this
project's history.

> **The host is left in the pinned configuration**, since MACHINE.md requires it for every
> measurement session. To revert: `powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e`.

### AC power was then lost mid-session, and this is unresolved

Between the pre-run check and the verification run, **the charger disconnected.** Confirmed by
three independent sources rather than assumed from one:

| Source | Reading |
|---|---|
| `GetSystemPowerStatus` | `ACLineStatus=0`, `BatteryFlag=2` |
| `Win32_Battery` (CIM) | `BatteryStatus=1` (discharging) |
| `assert_power_pin.ps1` | exit **2** (AC offline) |

Battery fell 31% → 25% monotonically over ~9 minutes of polling. This is a physical disconnection,
not a software state that this session could restore.

---

## 2026-07-30 — Topology verification PASSED its criteria, on an INVALID session

**Class:** measurement / session validity
**Milestone:** M1 — **still NOT ACCEPTED**
**Run ID:** `0d7c607b-b80b-4563-a5cc-00fa34d51fd8`
**Git SHA:** `899bf23b4c8909639566dfd924312a574afaeeea` (dirty tree, `--allow-dirty`; all
uncommitted paths belong to the unrelated projects in this repository — SEAM paths were clean)
**Kernel:** `python_intfp_v1` · **config_hash:** `1492611a666e397eba7cf0869ad9cc3a5bf63e6e9e420874ba247b600251072d`

### Result

| Quantity | Value |
|---|---|
| Verdict | **PASS** — every §4 acceptance criterion held |
| Fast cluster (CPUs) | 0, 1, 2, 3 |
| Slow cluster (CPUs) | 4, 5, 6, 7 |
| Cluster separation | **1.309×** (required ≥ 1.25×) |
| Within-cluster CV | fast 3.32%, slow 0.24% (limit 15%) |
| `EfficiencyClass` ordering | **MATCHED**, `higher_is_faster`, partitions identical as sets |

Per-CPU scores, M work-units/s:

| CPU | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| `0d7c607b` | 12.909 | 13.959 | 12.858 | 13.302 | 10.167 | 10.100 | 10.127 | 10.121 |

**These numbers are quotable against `run_id: 0d7c607b-b80b-4563-a5cc-00fa34d51fd8`** — the first
topology measurement in this project that is. That is AF-006's fix working as intended.

### Why the mapping was still NOT committed

The run was taken **on battery** (27% → 26%, discharging), because AC was lost between the
pre-flight check and the run. MACHINE.md classifies such a session as **INVALID, not noisy**, and
a passing measurement does not change the classification. Therefore:

- `configs/platforms/aipc-c1.yaml` still carries `topology.verified: false` with null CPU lists.
- `--write` was **not** passed; had it been, it would now be refused — this session added
  `assert_pinned_for_committed_result()`, which lets an unpinned session run and emit its manifest
  but forbids it from writing a result back into platform config. Discarding the run instead would
  recreate the AF-006 hole; the correct treatment is *citable but not authoritative*.
- The manifest records the violation itself: `power_state.on_battery: true`, and
  `summary.json` `session.pinned_condition_deviations` names it. The invalidity travels with the
  artifact rather than living in this log alone.

### What this run establishes anyway: the earlier refusals were the POWER PLAN

Comparing against the two refused runs (battery + **Balanced** + "Best power efficiency" overlay):

| Session | Fast mean | Slow mean | Ratio |
|---|---|---|---|
| Refused run 1 (Balanced) | 5.350 M | 4.772 M | 1.121× |
| Refused run 2 (Balanced) | 5.475 M | 4.615 M | 1.186× |
| `0d7c607b` (Best Performance) | 13.257 M | 10.129 M | **1.309×** |

Absolute throughput is **~2.4× higher** under the pinned plan, on the same kernel, on the same
battery power. The dominant compressor of the P/LP-E gap was the **Balanced plan and the
power-efficiency overlay**, not the AC/battery axis and **not the CPython kernel**. AF-005's
hypothesis 1 is substantially confirmed with the plan identified as the specific mechanism;
hypothesis 2 (interpreter dispatch masking the difference) is **not supported** — `python_intfp_v1`
discriminates the two core types at 1.309× once the host is not being clamped.

**No kernel replacement was performed**, and the spec §4 instrument stands as pre-registered. The
owner's Decision 3 (replace the kernel with a native/numpy loop) is therefore not triggered by this
evidence. `min_cluster_separation_ratio` was not touched and remains 1.25.

### Open question 4 — still provisional, but for a different reason than before

The harness itself computed the comparison this time and recorded it in a manifest, rather than it
being derived by hand from console output. It **matched**: Windows `EfficiencyClass` 1 on CPUs 0–3
= the measured-fast cluster, in the documented direction. It is not yet *closed*, because the run
carrying it is an invalid session. Closing it requires the same numbers from a run on AC power.

### To close M1

1. Reconnect AC power (physical action; outside this session's control).
2. `python -m seam.topology verify --write --allow-dirty`, ≥2 repeats.
3. Update the `test_committed_config_ships_unverified` tripwire in the same commit that records
   the run_id, as the earlier entry requires.

---

## 2026-07-30 — Governance restore: blueprint stub, hybrid ingest, AM-004 (PRE-DATA)

**Class:** provenance / pre-registration amendment
**Milestone:** M1 still NOT ACCEPTED; **M2 not started**
**Authorized by:** Z. Johnson (AM-004 energy-gate ruling; hybrid ingest; seam rule)

### Found

`docs/SEAM_research_blueprint.md` was committed as a **1-line stub**
(`@@SEAM_BLUEPRINT_APPEND_POINT@@`, 32 bytes). Agents reading "the blueprint" were reading
nothing. `docs/hybrid_execution_dse_positioning.md` was absent (AM-007). `.cursor/rules/seam.mdc`
was absent.

### Actions (docs / amendments only — no M2, no topology flip)

1. **Restored** `docs/SEAM_research_blueprint.md` from the Claude Desktop outputs archive via
   `robocopy` long-path staging (direct `Copy-Item` fails past MAX_PATH on that cache path).
   Archive bytes: 56617; **733 lines**; SHA-256
   `6c2221c6dd774183c3a62d520190964f75a74c115cfcd3f1733ebe0c8377be63`.
   AM-002 duplicate §16.x numbers **not** renumbered.
2. **Ingested** `docs/hybrid_execution_dse_positioning.md` (245 lines; SHA-256
   `ceec363af8a55269a370b63f80473f0cb00f757741be83fa054f56fb7c67d410`). AM-007 → RESOLVED.
   Phase −1 impact: positioning/claim-scope only (client-side hard; soften five-objective novelty;
   routing-amortization bound) — **no new measurement gates**. Not added to
   `configs/platforms/aipc-c1.yaml` `provenance_artifacts` (that list is probe/identity artifacts).
3. **PHASE_MINUS1_IMPLEMENTATION_SPEC.md** archive SHA matched the repo copy
   (`cfeada7da592eb59026b98481d52854481dec3d13e549ddc31d6d6b04a81604e`) — not clobbered; then
   AM-004 edits applied to §3.2 / M2.5.
4. **AM-004 RESOLVED (PRE-DATA, Z. Johnson).** Gate −1 "15% agreement" and G0 "wall meter within
   10%" replaced with per-target linear-tracking: $R^2 \ge 0.95$ across ≥8 load levels; slope
   $\in [1.0,\ 1.5]$ (slope $< 1.0$ HARD FAILURE); intercept vs brightness-differenced idle
   baseline; min resolvable ΔE per target; fits for `cpu-p` / `cpu-lpe` / `igpu` / `npu` not
   pooled. Logged in blueprint §14.2 and `AMENDMENTS.md`.
5. Created `.cursor/rules/seam.mdc` (alwaysApply).
6. AM-009 → RESOLVED (hashes pinned).

### Post-amendment document pins

| Path | Lines | SHA-256 (after this session's edits) |
|---|---:|---|
| `docs/SEAM_research_blueprint.md` | 750 | `72d9b6a32ea40d07201d35e22cfc6db6c0f62311a40c15bc5ecf4f9c4567c878` |
| `docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md` | 405 | `f42fad5bdf7377393684483b1f36dcc2da99e4fca94e9dd79292dde356198148` |
| `docs/hybrid_execution_dse_positioning.md` | 245 | `ceec363af8a55269a370b63f80473f0cb00f757741be83fa054f56fb7c67d410` |

### Explicit non-actions

- `topology.verified` left `false`; no `verify --write`.
- No M2 / telemetry / LHM / energy code.
- No test weakened.

**Remaining M1 blocker:** AC-power topology verification under pinned conditions (AF-005 /
prior entry). Physical reconnect required.

---

## 2026-07-30 — PRE-REGISTERED PREDICTION for the AC-power topology verification

**Class:** pre-registration
**Milestone:** M1 — attempting to close
**Status:** recorded **BEFORE** any AC measurement was taken. This entry is committed in its own
commit, ahead of the runs it predicts, so the prediction cannot have been written to fit a number
that was already known. A directional claim recorded after seeing the result is worthless.
**Comparison baseline:** `run_id 0d7c607b-b80b-4563-a5cc-00fa34d51fd8` — separation **1.30883×**,
CV fast 3.32%, CV slow 0.24%, fast {0,1,2,3} / slow {4,5,6,7}, `EfficiencyClass` ordering matched.
That session was on battery and is therefore INVALID as a committable platform result, but it is
citable, and it is the number this prediction is stated against.

### Session conditions declared in advance

AC reconnected. Reported by the owner before this work began: `powercfg /getactivescheme` =
`ec87a53a-19a6-4f4a-980f-ab27cc929b25` (Best Performance, the pinned plan), `Win32_Battery`
`BatteryStatus = 2` (AC connected), `EstimatedChargeRemaining = 54`. So the runs below are taken on
AC **while the battery is taking bulk charge at roughly half capacity.**

### Predictions

1. **The AC separation ratio exceeds 1.30883×.** Mechanism: greater power and thermal headroom on
   AC lets the Cougar Cove P-cores hold higher turbo residency, while the Darkmont LP-E cores are
   nearer their ceiling already and gain less. The gap the ratio measures should therefore widen.
2. **Cluster membership is unchanged:** fast {0,1,2,3}, slow {4,5,6,7}.
3. `EfficiencyClass` ordering matches the measured split in the documented `higher_is_faster`
   direction, as it did on battery.

### Charge-state confound, declared before measuring

Charging is a **load**, not a neutral background condition. It draws adapter headroom and adds
chassis heat, and both depress P-core turbo more than LP-E turbo, because the P-cores are the cores
with turbo headroom left to lose. Bulk charge at ~54% is close to the worst case for this, since
charge current is highest well below the constant-voltage knee.

Therefore **a pass under charging load is conservative evidence, not weak evidence.** If the
separation clears 1.30883× while the charger is pushing current into a half-empty battery, it will
clear it at full charge too. The confound can only work against the prediction.

### Stop rule, amended for the confound (pre-registered)

- Ratio **> 1.30883×** on every AC run, with the other §4 criteria holding → prediction HELD,
  mapping committable.
- Ratio **below 1.30883×** at ~54% charge → **INCONCLUSIVE, not a failed prediction.** Log both
  attempts, charge above 85%, re-run twice, and only then evaluate against the prediction. Do not
  investigate hardware or pinning first, and do not touch a threshold.
- Cluster membership differing from {0,1,2,3} / {4,5,6,7} → **STOP.** That is not a confound. It
  would contradict both the battery session and the committed platform provenance, and must be
  understood before anything is written to config.
- Every run is logged whatever it returns. No run is discarded for being inconvenient.

### Run plan, pre-registered

Two measurement runs of `python -m seam.topology verify` **without** `--write`, evaluated against
the criteria above; only then a third run with `--write` to persist, which is held to the *same*
criteria. Splitting measurement from persistence this way keeps the evaluation from being able to
read a config that the first run already mutated, and it means three AC runs must clear the
prediction rather than two. `--allow-dirty` is required and recorded: the repository carries
uncommitted work belonging to the unrelated projects (`apu_characterization/`, `censor/`,
`orchestration_engine/`), while the SEAM paths are clean.

### Schema extension committed with this prediction (precondition, not a result)

`power_state` recorded `battery_pct_start` and `battery_pct_end` but had **no charging field**, so
the confound above would not have been recorded in the artifact — only in this log. Added
`power_state.charging`, decoded from `SYSTEM_POWER_STATUS.BatteryFlag` bit 3, with an unknown flag
recorded as an explicit `null` rather than `false`. Schema, emitter, and tests changed together;
suite 178 → 185 tests. Done **before** measuring, so every run below records its own charge state.
`spec_version` stays `"1.0"`: the field is additive and every manifest valid under the previous
schema remains valid.

---

## 2026-07-30 — Topology verification PASSED on a VALID pinned AC session (×2)

**Class:** measurement
**Milestone:** M1 — **not yet accepted at the time of writing**; one pre-registered gate is
ambiguous and awaits an owner ruling (see "Run-to-run agreement" below)
**Prediction:** the entry immediately above, committed in `99da687` **before** these runs
**Power pin:** `analysis/aipc-c1/scripts/assert_power_pin.ps1` exit **0**
(`AC online=True raw=1`, `Plan active: Best Performance ec87a53a-…`, `acOk=True planOk=True`) —
run as a gate before measuring, as AF-005 required
**Git SHA (both runs):** `99da68716227b41c9548ba6e335bc6a1d242dbe9`, `git_dirty: true`,
`allow_dirty: true` — every uncommitted path belongs to the unrelated projects in this repository;
the SEAM paths (`seam/`, `tests/`, `configs/`, `docs/`, `AUDIT_LOG.md`, `AMENDMENTS.md`) were clean
**config_hash (both runs):** `1492611a666e397eba7cf0869ad9cc3a5bf63e6e9e420874ba247b600251072d`
— identical to the battery session `0d7c607b`, so the instrument and its parameters are unchanged
**Kernel:** `python_intfp_v1`, 6 000 000 work-units per trial, 7 repeats + 2 warm-up, min-elapsed
**Elevated:** false (not required for this measurement)

### Results

| Quantity | Run A `3fb88dcd-35e7-4826-96b9-8a3edce2b341` | Run B `963a849e-e8b3-4bde-83ac-2cc33add2f7e` |
|---|---|---|
| Verdict | **PASS**, no refusal reasons | **PASS**, no refusal reasons |
| Separation ratio | **1.3876038015371646** | **1.3599431469328718** |
| CV fast | 0.021644540218476584 | 0.024060827805485196 |
| CV slow | 0.009691545939056138 | 0.008466216319797161 |
| Fast cluster | {0, 1, 2, 3} | {0, 1, 2, 3} |
| Slow cluster | {4, 5, 6, 7} | {4, 5, 6, 7} |
| `EfficiencyClass` ordering | **matched**, `higher_is_faster`, partition matched | **matched**, `higher_is_faster`, partition matched |
| `integrity.self_check` | `pass` | `pass` |
| `integrity.raw_sha256` | `9eaa8404ddbc8ff40ff3270377bdf0bd11be97882e39a0143941cd15c5d65237` | `9a2dd67a3a4ec8fe38ec64fa38143040faef3dbfbdbe88d5fe8235f633728693` |
| `timestamp_utc` | 2026-07-30T23:18:49.897357+00:00 | 2026-07-30T23:19:36.922937+00:00 |

`EfficiencyClass` map, both runs: CPUs 0–3 → 1, CPUs 4–7 → 0. The EC convention observed is
**higher EfficiencyClass = faster core**, which is the documented Windows direction.

Per-CPU scores, M work-units/s:

| CPU | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| Run A | 14.152 | 14.528 | 13.711 | 13.908 | 10.172 | 10.153 | 9.988 | 10.260 |
| Run B | 14.000 | 14.094 | 13.265 | 13.605 | 9.996 | 10.155 | 10.052 | 10.215 |

### Session conditions, as recorded in the artifacts

Both runs: `power_state.on_battery: false`, `power_plan: "Best Performance
(ec87a53a-19a6-4f4a-980f-ab27cc929b25)"`, effective overlay `00000000-0000-0000-0000-000000000000`
(the slider does not apply to this scheme), battery saver off, and
`session.pinned_condition_deviations: []` — **an empty deviation list for the first time on a
topology run.** Run A: `battery_pct_start 69.0 → battery_pct_end 70.0`, `charging: true`.
Run B: `70.0 → 71.0`, `charging: true`.

Charge was **69–71%, not the ~54%** stated when the prediction was written — the host had been
charging in the interim. Still below the ~85% level at which charge current tapers, so both runs
were taken under bulk-charge load and the conservative-evidence argument in the prediction applies
unchanged.

### Prediction outcome: HELD

1. **Separation exceeds 1.30883×** on both runs: 1.38760× (+6.02%) and 1.35994× (+3.90%). The
   *lower* of the two clears the baseline, so the prediction does not depend on which run is cited.
2. **Cluster membership unchanged:** {0,1,2,3} fast / {4,5,6,7} slow, identical across both runs and
   to `0d7c607b`.
3. `EfficiencyClass` ordering matched in the documented direction on both runs.

The mechanism proposed in advance — P-cores gaining more turbo headroom than LP-E cores under AC —
is consistent with what moved. Comparing against `0d7c607b` (battery, same plan, same kernel, same
`config_hash`): the fast-cluster mean rose 13.257 → 14.075 M work-units/s (+6.2%) in run A, while
the slow-cluster mean was flat, 10.129 → 10.143 M (+0.1%). The ratio widened because the P-cores
got faster, not because the LP-E cores got slower.

### Run-to-run agreement — the one gate that is ambiguous

The pre-registered stop rule requires the two ratios to "agree with each other," and flags a
difference "more than the larger `cv_fast`" for an explicit report and an owner decision before
committing. The observed difference is **0.0276606546042928** and the larger `cv_fast` is
**0.024060827805485196**. Whether that passes depends on how the comparison is read, and the rule
did not say:

| Reading | Comparison | Verdict |
|---|---|---|
| Absolute difference in ratio units vs the CV fraction | 0.02766 > 0.02406 | **exceeds by 0.0036 (15% over)** |
| Relative difference vs the CV, which is itself relative | 0.02766 / 1.37377 = **2.014%** < 2.406% | within |

A coefficient of variation is dimensionless, so comparing it to a difference expressed in ratio
units is dimensionally inconsistent; the second reading is the defensible one. For scale: the
standard error of a cluster mean over 4 cores is ≈ `cv/√4`, giving ≈1.2% on the fast mean and ≈0.45%
on the slow, so a single ratio carries ≈1.3% (≈0.018) of sampling error and the difference of two
carries ≈0.025. The observed 0.0277 is therefore **≈1.1σ** — unremarkable noise, concentrated in the
fast cluster, where CPU 2 differs most between runs (13.711 vs 13.265 M).

**No threshold was touched and no run was discarded.** Both runs are sealed in `raw/` and citable.
Because the rule is a pre-registered gate, it is not this session's call to resolve by choosing the
convenient reading: the ambiguity is recorded here and referred to the owner. `--write` was **not**
passed, so `configs/platforms/aipc-c1.yaml` still carries `topology.verified: false` with null CPU
lists, and the tripwire test is unchanged.

### What remains to close M1

1. Owner ruling on the agreement reading above (or a third measurement run to characterise the
   spread, which must be authorised rather than added to fish for a tighter number).
2. `python -m seam.topology verify --write --allow-dirty` to persist, held to the same criteria.
3. Config + tripwire-test update in one commit; then AF-005 closure and AM-008 resolution citing
   that commit SHA.

---

## 2026-07-30 — Owner rulings applied; two write runs; OQ4 CLOSED; mapping commit still held

**Class:** measurement / governance
**Milestone:** M1 — **still NOT ACCEPTED.** One criterion the owner set for the persisting run did
not hold; see "The one criterion that did not hold" below.
**Authorized by:** Z. Johnson (Ruling 1, gate reading; Ruling 2, charge-state correction)
**Power pin:** `assert_power_pin.ps1` exit **0** before each run below (battery 87%, then 90%)

### Ruling 1 recorded — the agreement gate is a RELATIVE-difference criterion

The owner ruled that the run A vs run B comparison in the previous entry **satisfies** the gate. A
coefficient of variation is dimensionless, so comparing a difference of separation ratios against a
CV is only coherent as a relative comparison: 2.014% observed against the larger `cv_fast` of
2.406%, roughly 1.1σ of sampling noise. The absolute reading (0.0277 vs 0.0241) was a **units
mismatch in how the criterion was worded**, not a disagreement in the data.

**This ruling was made after seeing the data, and that is stated plainly rather than obscured.** It
is a units clarification, not a threshold change: the numeric tolerance is untouched, and no run's
verdict was reclassified by moving a number. Logged as `AMENDMENTS.md` **AM-012**.

### Ruling 2 recorded — charge-state correction to the pre-registration

The pre-registration stated ~54% charge, quoting the owner's pre-session reading. **The actual
charge state per run, from each manifest:**

| Run | `battery_pct_start` → `end` | `charging` | Relative to the ~85% taper |
|---|---|---|---|
| A `3fb88dcd` | 69.0 → 70.0 | true | below — bulk charge |
| B `963a849e` | 70.0 → 71.0 | true | below — bulk charge |
| C `855e3590` | 87.0 → 88.0 | true | above — charge current tapering |
| D `7b5fc2e2` | 90.0 → 90.0 | true | above — near full |

The host had been charging between the owner's reading and the runs. Per the ruling, this is
corrected here rather than re-measured. **The conservative-evidence argument in the pre-registration
still holds:** runs A and B were taken under bulk-charge load below the taper point, which is the
condition that depresses P-core turbo most, and they still cleared the predicted 1.30883×.

The correction also produced *supporting* evidence for the pre-registered mechanism that was not
available when the prediction was written. Separation rises monotonically as charge load falls:
1.3599× and 1.3876× under bulk charge (69–71%), 1.3917× and 1.3989× as the current tapers (87–90%).
That is the direction the pre-registration predicted for charging as a load, observed across the
charge curve rather than argued from theory.

### Citation error in the task brief — blueprint "§16.9" does not exist

The instructions that opened this work directed the agent to re-read blueprint **§16.9** before
starting. **There is no §16.9.** At the pinned SHA
`72d9b6a32ea40d07201d35e22cfc6db6c0f62311a40c15bc5ecf4f9c4567c878` (750 lines), §16 runs 16.1 →
16.6 (Gate −1) and is followed by Appendix B and Appendix A, and it carries the duplicate §16.2 /
§16.3 numbering already recorded as AM-002. The governing text used instead was blueprint §5 (audit
and data-integrity standard), spec §4 (core topology and affinity), and spec §7 / M1 (acceptance
criteria). Recorded so the phantom citation does not propagate into later milestones.

The same brief referred to "AM-011 (resolved)". **No AM-011 exists** in `AMENDMENTS.md`, which ends
at AM-010. Since the brief also forbade touching AM-011, that ID is left deliberately unused rather
than reassigned, and this entry explains the gap.

### Two defects in the config writer, found by reading the written file back

`_write_verified_topology` uses `ruamel.yaml` specifically to preserve this config's provenance
comments. Both defects broke exactly what it exists to protect, and neither would have failed a
test or changed a hash — they were found only by diffing the file the harness produced.

1. **A measured list was relabelled as a hypothesis.** The comment introducing `topology.expected`
   ("Hypothesis, from vendor documentation. **NOT evidence**") is attached to the preceding
   `lpe_cpus` key. Replacing that key's `null` with a *block* sequence emitted the comment between
   the key and its items, leaving that text sitting on top of the **measured** LP-E CPU list —
   asserting the opposite of the truth about those four numbers. Fixed by writing both CPU lists as
   flow sequences, which keep the value on the key's own line. Commit `1ddc9eb`.
2. **Every unmeasured `null` was blanked.** ruamel renders `None` as an empty value, so the write
   rewrote unrelated fields as `field:` instead of `field: null` — `memory.bandwidth_gbps_measured`,
   both NPU achieved-throughput fields, `power.turbo_sustainable_s`, and **all four `thermal.*`
   constants**. This config gives `null` the specific meaning "not yet measured, never to be
   replaced with a plausible number", which is AM-006's entire subject; a blank value cannot be
   distinguished from a field someone forgot to fill in. Fixed with an explicit `null` representer,
   plus block-sequence indentation so an unrelated 15-line reindentation stops riding along. Commit
   `190904e`.

Four regression tests now cover the writer: comments survive, the hypothesis comment stays between
`lpe_cpus` and `expected`, everything outside the `topology:` block comes back byte-identical, and
the written file reads back as a verified topology. Suite 185 → 189.

### The two persisting runs

Both were `python -m seam.topology verify --write --allow-dirty` under the pinned conditions, and
both **PASSED** every §4 criterion. Run C ran on the pre-fix writer; run D ran after fix 1, with fix
2 not yet found. Neither is discarded — both are sealed and citable, and C's numbers stand as
measurements regardless of the writer defect that spoiled its config output.

| Quantity | Run C `855e3590-10af-4723-ab38-fb3ae0f16c86` | Run D `7b5fc2e2-dc9d-4741-8e4b-8b6e64a37f5c` |
|---|---|---|
| Verdict | **PASS**, no refusal reasons | **PASS**, no refusal reasons |
| Separation ratio | **1.3917174862228963** | **1.3988665756315648** |
| CV fast | 0.020705448258056293 | 0.019990792091298136 |
| CV slow | 0.0029834462281206962 | 0.01973098452292933 |
| Fast / slow cluster | {0,1,2,3} / {4,5,6,7} | {0,1,2,3} / {4,5,6,7} |
| `EfficiencyClass` ordering | matched, `higher_is_faster`, partition matched | matched, `higher_is_faster`, partition matched |
| `integrity.self_check` | `pass` | `pass` |
| `integrity.raw_sha256` | `b5ad22def2f376dd7cad0e5510e6196fbed84f767cf6b491f71f4090944a6110` | `d80e87c9347a15d06a6609a25957668be2ce5fdf75dc1b69567a340eb3816c8c` |
| `power_state.on_battery` | false | false |
| `power_plan` | Best Performance (`ec87a53a-…`) | Best Performance (`ec87a53a-…`) |
| Effective overlay | `00000000-0000-0000-0000-000000000000` | `00000000-0000-0000-0000-000000000000` |
| Battery saver | off | off |
| `pinned_condition_deviations` | **[]** | **[]** |
| `git_sha` / `git_dirty` / `allow_dirty` | `44212a60…93ecf4` / true / true | `44212a60…93ecf4` / true / true |
| `config_hash` | `1492611a…51072d` | `1492611a…51072d` |
| `timestamp_utc` | 2026-07-30T23:34:56.632181+00:00 | 2026-07-30T23:38:18.265168+00:00 |
| `workload.kind` / `benchmark` | `topology_verify` / `python_intfp_v1` | `topology_verify` / `python_intfp_v1` |
| Elevated | false | false |

Per-CPU scores, M work-units/s:

| CPU | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| Run C | 14.267 | 14.676 | 13.881 | 14.073 | 10.180 | 10.204 | 10.255 | 10.244 |
| Run D | 14.297 | 14.748 | 13.947 | 14.251 | 10.330 | 10.281 | 9.891 | 10.419 |

`config_hash` is identical across all four AC runs and to the battery run `0d7c607b`, so the
instrument and every one of its parameters were unchanged throughout. `git_dirty: true` with
`allow_dirty: true` records that the writer fixes were applied but not yet committed when C and D
ran; the SEAM paths carried only those fixes, and all other uncommitted paths belong to the
unrelated projects in this repository.

### All four AC runs, and the agreement matrix under Ruling 1

| Run | Separation ratio | `cv_fast` | `cv_slow` | Charge | Verdict |
|---|---|---|---|---|---|
| A `3fb88dcd` | 1.3876038015371646 | 0.021645 | 0.009692 | 69→70% bulk | PASS |
| B `963a849e` | 1.3599431469328718 | 0.024061 | 0.008466 | 70→71% bulk | PASS |
| C `855e3590` | 1.3917174862228963 | 0.020705 | 0.002983 | 87→88% taper | PASS |
| D `7b5fc2e2` | 1.3988665756315648 | 0.019991 | 0.019731 | 90→90% near full | PASS |

Pairwise, relative difference against the larger `cv_fast` of the pair:

| Pair | Relative difference | Limit | Result |
|---|---|---|---|
| A vs B | 2.0135% | 2.4061% | pass |
| A vs C | 0.2960% | 2.1645% | pass |
| A vs D | 0.8084% | 2.1645% | pass |
| B vs C | 2.3095% | 2.4061% | pass |
| **B vs D** | **2.8218%** | **2.4061%** | **exceeds, by a factor of 1.17** |
| C vs D | 0.5124% | 2.0705% | pass |

### The one criterion that did not hold

The owner's instruction for the persisting run was that its ratio "must also agree with runs A
(1.3876038015371646) and B (1.3599431469328718) under the relative reading now authorized," and
that on any failed criterion the correct action is to stop and report. **Run D agrees with A
(0.8084%) but not with B (2.8218% against a 2.4061% limit).** So the mapping was **not committed**,
and `configs/platforms/aipc-c1.yaml` was restored to `verified: false` with null CPU lists pending
an owner ruling.

Three things about that number, none of which resolve it unilaterally:

1. **Five of six pairs pass.** The single exceedance is between the extreme low (B) and extreme high
   (D) of four runs. The rule was worded for *two* runs; applied pairwise to four it necessarily
   tests the extremes, which spread further as runs are added. Measured instead against the
   four-run mean of 1.384533×, every run is inside its own limit — B deviates 1.78%, D 1.04%.
2. **Part of the B–D gap is the identified charge-state effect,** not instrument instability: B sat
   under bulk charge, D near full. That confound was pre-registered, and it moved in the
   conservative direction.
3. **Nothing about the committed claim depends on it.** Membership is {0,1,2,3} / {4,5,6,7} in all
   four AC runs and in the battery run — five for five. The weakest ratio of the five, 1.3599×, is
   8.8% above the `min_cluster_separation_ratio` of 1.25 and 3.9% above the pre-registered
   1.30883×. The worst CV of the five is 2.41% against a 15% limit.

**No threshold was moved, no run was discarded, and no test was weakened to get past this.** It is
also true that run C happens to clear the B pair at 2.3095% where D does not — citing C for that
reason would be selecting a result by its agreement with a gate, so it is recorded as a fact and
explicitly not proposed. If a persisting run is cited, it should be the run that actually wrote the
file, decided on process grounds rather than on which number cooperates.

### Spec §10 open question 4 — **CLOSED**

**Does the Windows `EfficiencyClass` ordering match the empirically measured P/LP-E split? Yes, in
the documented direction.** On this platform **a higher `EfficiencyClass` value is the faster
core.**

Windows reports `EfficiencyClass` 1 for CPUs 0–3 and 0 for CPUs 4–7. Measurement independently
placed CPUs 0–3 in the fast cluster and 4–7 in the slow cluster, in **five for five** runs spanning
both power conditions and every session validity state:

| Run | Session | `efficiency_class_ordering_matched` | Direction | Partition matched |
|---|---|---|---|---|
| `0d7c607b-b80b-4563-a5cc-00fa34d51fd8` | battery, INVALID as a platform result | true | `higher_is_faster` | true |
| `3fb88dcd-35e7-4826-96b9-8a3edce2b341` | pinned AC | true | `higher_is_faster` | true |
| `963a849e-e8b3-4bde-83ac-2cc33add2f7e` | pinned AC | true | `higher_is_faster` | true |
| `855e3590-10af-4723-ab38-fb3ae0f16c86` | pinned AC | true | `higher_is_faster` | true |
| `7b5fc2e2-dc9d-4741-8e4b-8b6e64a37f5c` | pinned AC | true | `higher_is_faster` | true |

The comparison was computed by the harness and recorded in each manifest, not derived by hand from
console output, and the direction was never assumed: `_evaluate_efficiency_class_agreement` tests
both senses and reports the one observed. Spec §4's warning against trusting the ordering blindly
therefore stands as *methodology* — it was checked rather than assumed — while the answer for
Platform A is that the ordering can be trusted. **This closure does not license reading the mapping
from `EfficiencyClass` on any other platform**, and it does not remove the requirement that every
run assert the committed mapping.

### AF-005 — conditions satisfied, formal closure pending the mapping commit

AF-005 required AC power, the pinned plan, and `assert_power_pin.ps1` run as an aborting gate. All
four AC runs recorded `on_battery: false`, the pinned Best Performance plan, battery saver off, and
an **empty** `pinned_condition_deviations` list, with the pin asserted at exit 0 before measuring.
The finding's substance is discharged; the entry is left formally open only because its closure
belongs with the M1 acceptance commit, which is held.

### Explicit non-actions

- `configs/platforms/aipc-c1.yaml` restored to `verified: false`, null CPU lists. **The mapping is
  not committed.**
- The `test_committed_config_ships_unverified` tripwire is unchanged and still passing, which is
  what it is for: it failed loudly while the written config sat in the working tree.
- `verification.*` thresholds untouched: `min_cluster_separation_ratio` 1.25,
  `max_within_cluster_cv` 0.15, `require_expected_split` true.
- No M2 work. No `seam/telemetry/`, no energy, thermal, PDH, or LHM code. AM-002, AM-004 and the
  unused AM-011 identifier untouched.
- No sealed run modified; the five original `analysis/` probe artifacts untouched.

---

## 2026-07-30 — Pre-registration of the citing run; settled-charge comparator set (AM-013)

**Class:** pre-registration
**Milestone:** M1 — closing
**Authorized by:** Z. Johnson (Ruling 1, comparator set = AM-013; Ruling 2, pre-declare the citing
run)
**Status:** committed **BEFORE** the measurement it governs.

### Ruling 1 — agreement is assessed among settled-charge runs only

Recorded in full as `AMENDMENTS.md` **AM-013**, POST-DATA, authorized by Z. Johnson. In summary:
charge state is a **documented covariate** on this platform rather than noise, evidenced by the
monotone series 1.3599× (bulk, ~70%) → 1.3876× (bulk, ~69–70%) → 1.3917× (taper, ~87%) → 1.3989×
(settled, ~90%), which is the pre-registered P-core-turbo-headroom mechanism appearing as a
covariate. Runs taken under different charge conditions are therefore **not exchangeable**, and
pooling them for an agreement test conflates a real physical effect with sampling noise. The prior
pairwise rule was written for two runs; applied across four it necessarily tests the extremes, and
maximum pairwise spread **grows with n**, so the rule tightened as evidence accumulated. That is a
specification defect, **corrected, not loosened** — the numeric tolerance (the larger `cv_fast` of
the compared runs) is unchanged, and no run's individual verdict was reclassified. AM-012's
relative-reading clarification stands and is unaffected.

**Runs A `3fb88dcd` and B `963a849e` remain fully logged, citable, and NOT discarded.** No run is
deleted, hidden, or reclassified as invalid. Their status changes from **agreement comparators** to
**supporting evidence for the charge-state mechanism**, where they carry the low-charge end of the
monotone series above — evidence that could not be produced without them.

### Settled-charge determination for the comparator set

Definition applied: battery **> 85%** and **not under bulk charge**.

| Run | `battery_pct_start` → `end` | Δ over run | `charging` | Determination |
|---|---|---|---|---|
| C `855e3590` | 87.0 → 88.0 | +1 point | true | **qualifies** — above the constant-current knee; charge current tapering |
| D `7b5fc2e2` | 90.0 → 90.0 | 0 points | true | **qualifies** — above the knee, and no measurable state-of-charge movement across the run |

Both qualify, with one caveat stated rather than glossed: the manifests record a **boolean**
`charging` flag, and both runs read `true`, because a Li-ion pack continues taking a declining
top-off current well past 85%. No charge-*current* telemetry exists at M1, so "not under bulk charge"
is established from state of charge being above the typical constant-current → constant-voltage
transition (~80–85%) plus the per-run Δ as a proxy for current. Measuring adapter or pack current
directly is telemetry work and belongs to M2; it is deliberately not done here. On that evidence D is
the more settled of the two, and C sits in the taper.

Under AM-013 the comparator set is therefore **{C, D}**, which agree at **0.5124%** relative against
a limit of **2.0705%** (the larger `cv_fast` of the two, from C). Note the limit is C's `cv_fast`,
not the 2.41% quoted in the ruling, which was run B's — B is no longer in the comparator set.

### Ruling 2 — the citing run is pre-declared, and there is no re-rolling

**The next `python -m seam.topology verify --write` run conducted at settled charge (> 85%, not bulk
charging) IS the citing run for the committed mapping.** It will be evaluated **once** against the
criteria below. **If it fails any of them, the failure is reported and the mapping is not
committed.** It will not be re-run to obtain a better draw, and no later run may be substituted for
it. This paragraph is committed before the run exists, which is what makes that promise checkable.

Criteria, all of which must hold:

1. `assert_power_pin.ps1` exit 0; `on_battery: false`; Best Performance plan;
   `pinned_condition_deviations` empty.
2. Battery > 85% and not under bulk charge.
3. `separation_ratio` ≥ 1.25 **and** > 1.30883 (the original pre-registered prediction).
4. `cv_fast` and `cv_slow` ≤ 0.15.
5. Fast/slow membership exactly {0,1,2,3} / {4,5,6,7}. **A different membership contradicts five
   prior runs and the committed platform provenance — stop and report, do not write.**
6. `efficiency_class_ordering_matched: true`.
7. `integrity.self_check: pass`.
8. Relative agreement with the settled-charge comparator set {C, D} within the larger `cv_fast` of
   the compared runs.

### Host state recorded before the run

`assert_power_pin.ps1` exit **0** — `AC: online=True raw=1 battery%=98`, plan active and pinned both
`Best Performance (ec87a53a-19a6-4f4a-980f-ab27cc929b25)`, `acOk=True planOk=True`. Live capture:
`on_battery=False`, `battery_pct=98.0`, `charging=True` (top-off), `battery_saver=False`, effective
overlay `00000000-0000-0000-0000-000000000000`. At 98% the pack is far above the constant-current
knee, so this run will be the most settled of the series.

### Coordinator citation errors, per the owner

The owner confirms that the earlier task briefs' references to a blueprint **§16.9** and to an
**AM-011 (resolved)** were **coordinator errors propagated into task briefs**, not entries that ever
existed. Neither exists: the blueprint at the pinned SHA runs §16.1 → §16.6 plus appendices, and
`AMENDMENTS.md` ran AM-001 → AM-010. The identifiers were left unused rather than reassigned
(`AMENDMENTS.md` AM-011 records the deliberate gap). Recorded here so the phantom citations do not
recur in later milestones.

### One further gap found and being closed with this work

`raw/` has **never been committed**, despite `.gitignore` carrying an explicit note that it is
deliberately not ignored because blueprint §5.3 (write-once, checksummed) and §5.7 (artifact
"reusable" badge) require the raw data to be in the repository. Every `run_id` cited in this log so
far therefore resolves only on this host. The sealed run directories are committed alongside this
M1 closeout so that the cited measurements are verifiable by someone else, which is the entire point
of spec §9.2. `.gitattributes` already carries `raw/** -text`, so the committed bytes survive
checkout on any platform and `verify_sealed()` still passes. `raw/_blinding/salt.txt` stays ignored.

---

## 2026-07-30 — Citing run `fb5cd2d5`; mapping committed; AF-005 CLOSED; **M1 ACCEPTED**

**Class:** milestone acceptance
**Milestone:** M1 — **ACCEPTED**
**Citing run:** `fb5cd2d5-e850-4de1-9b90-d368b5aa9994` (run E), the run pre-declared in the entry
immediately above and committed as such in `282241a` **before it was taken**
**Citing commit:** `a3d23236998e00375c533f3e02561fbb6f457804`
**Evaluated:** **once.** No re-run, no substitution, no better draw sought.

### Result of the single pre-declared attempt

| Field | Value |
|---|---|
| `run_id` | `fb5cd2d5-e850-4de1-9b90-d368b5aa9994` |
| `verdict` | **pass**, `refusal_reasons: []` |
| `timestamp_utc` | 2026-07-30T23:57:04.876946+00:00 |
| fast / slow cluster | **[0, 1, 2, 3] / [4, 5, 6, 7]** |
| `cluster_separation_ratio` | **1.380460703128493** |
| `p_cluster_cv` (fast) | 0.024219564166094075 |
| `lpe_cluster_cv` (slow) | 0.005110664657290979 |
| `efficiency_class_map` | {0:1, 1:1, 2:1, 3:1, 4:0, 5:0, 6:0, 7:0} |
| `efficiency_class_ordering_matched` | **true** (`direction=higher_is_faster`, `partition_matched=true`) |
| scores (units/s) | 0: 14420532.531038996 · 1: 14711359.449755926 · 2: 13787043.488011707 · 3: 14105907.62464274 · 4: 10298410.165766643 · 5: 10256424.282289617 · 6: 10363233.045448476 · 7: 10390492.007114023 |
| kernel | `python_intfp_v1`, 6 000 000 work units, 7 repeats, 2 warmup, `min_elapsed_over_repeats` |
| `power_state` | `on_battery: false`, battery **99.0 → 99.0%**, `charging: true` (top-off), saver off, plan `Best Performance (ec87a53a-…)`, overlay `00000000-…` start and end |
| `pinned_condition_deviations` | **[]** (empty) |
| `integrity` | `self_check: pass`, `raw_sha256: 9505097e97dcfacb914e8bdc99134e423d7dd463c6838652cff75d851d64f464` |
| git | `282241a1c78390d780ec4e66b1de9515c4e9ed8c`, `git_dirty: true`, `allow_dirty: true`, branch `rev-c-p2` |
| `config_hash` | `1492611a666e397eba7cf0869ad9cc3a5bf63e6e9e420874ba247b600251072d` — identical to runs A–D |
| labels | `condition_label: topology_verify` → `blinded_label: cond_b836743d2f3b` |
| `elevated` | false |

`assert_power_pin.ps1` exit **0** immediately before the run: `AC: online=True raw=1 battery%=99`,
plan active and pinned both `Best Performance`, `acOk=True planOk=True`. Seal re-verified **after**
the commit: `raw integrity OK`.

### Every pre-declared criterion, checked

| # | Criterion | Result |
|---|---|---|
| 1 | pin exit 0, `on_battery: false`, Best Performance, deviations empty | **PASS** |
| 2 | battery > 85%, not bulk charge | **PASS** — 99%, no state-of-charge movement across the run |
| 3 | separation ≥ 1.25 **and** > 1.30883 | **PASS** — 1.380460703128493 |
| 4 | `cv_fast`, `cv_slow` ≤ 0.15 | **PASS** — 0.0242 / 0.0051 |
| 5 | membership exactly {0,1,2,3} / {4,5,6,7} | **PASS** — no stop condition triggered |
| 6 | `efficiency_class_ordering_matched` | **PASS** — true |
| 7 | `integrity.self_check` | **PASS** |
| 8 | relative agreement with settled-charge set {C, D} | **PASS** — see below |

Criterion 8, computed against the larger `cv_fast` of each pair per AM-012:

| Pair | Relative difference | Limit (larger `cv_fast`) | Verdict |
|---|---|---|---|
| E vs C `855e3590` | **0.8121%** | 2.4220% (E) | PASS |
| E vs D `7b5fc2e2` | **1.3245%** | 2.4220% (E) | PASS |

The prediction registered in `99da687` before any AC run said separation would exceed 1.30883× with
membership {0,1,2,3}/{4,5,6,7}. Five AC runs have now met it, this one included.

### The full series, all five AC runs, none discarded

| Run | `run_id` | Battery | Separation | `cv_fast` | `cv_slow` | Verdict | Role |
|---|---|---|---|---|---|---|---|
| B | `963a849e` | 70 → 71%, bulk | 1.3599431469328718 | 0.024061 | 0.008466 | pass | supporting evidence — charge-state mechanism |
| A | `3fb88dcd` | 69 → 70%, bulk | 1.3876038015371646 | 0.021645 | 0.009692 | pass | supporting evidence — charge-state mechanism |
| C | `855e3590` | 87 → 88%, taper | 1.3917174862228963 | 0.020705 | 0.002983 | pass | settled-charge comparator |
| D | `7b5fc2e2` | 90 → 90%, settled | 1.3988665756315648 | 0.019991 | 0.019731 | pass | settled-charge comparator |
| **E** | **`fb5cd2d5`** | **99 → 99%, settled** | **1.380460703128493** | **0.024220** | **0.005111** | **pass** | **citing run — committed** |

**Runs A and B are not discarded, hidden, or invalidated.** Both passed every §4 criterion on their
own and both remain fully citable. Under AM-013 their role is **supporting evidence for the
charge-state mechanism** rather than agreement comparators, and in that role they are the low-charge
end of the monotone series that demonstrates the covariate at all.

One honest observation about the series, recorded because it would be easy to omit: E at 99% is
**not** the highest ratio — it sits below C and D despite being the most settled. So the monotone
relationship in AM-013's Rationale 1 does not extend cleanly to the top of the charge curve, and the
four-point monotonicity is better read as *bulk charge depresses separation* than as *separation
tracks state of charge*. That does not affect any verdict: E clears every pre-declared criterion,
including agreement with both comparators, and the mechanism claim in AM-013 concerns bulk-charge
load specifically. But the covariate should be treated as **charging load**, not as charge level, and
a future M2 run that draws on this should say so.

### Verification of the config write

Only the `topology:` block changed — `git diff` on `configs/platforms/aipc-c1.yaml` touches nothing
else. Read back and diffed after the real write, the nulls that must stay null are **all intact**:
`bandwidth_gbps_measured`, `bandwidth_measured_by_run_id`, `achieved_tops_measured`,
`achieved_measured_by_run_id`, `turbo_sustainable_s`, `warmup_s`, `cooldown_ceiling_c`,
`throttle_threshold_pct`, `tjmax_c` — nine in total, spanning the memory, NPU, and thermal blocks.
They are written as explicit `null`, not blanked, which is what the two writer defects fixed in
`1ddc9eb` and `190904e` were about. `topology.verification` thresholds are byte-unchanged:
`min_cluster_separation_ratio: 1.25`, `max_within_cluster_cv: 0.15`, `require_expected_split: true`.

### The AM-008 tripwire: how its protective purpose survives

`test_committed_config_ships_unverified` asserted `verified: false`. That assertion cannot survive a
real measurement, but its *purpose* can, and the purpose was never "verified must be false" — it was
**"`verified: true` must not appear without a measurement behind it."** That is now enforced by three
tests instead of one:

1. `test_committed_config_carries_the_measured_mapping` pins the citing `run_id` **by name**. Changing
   the committed mapping therefore requires editing the test in the same commit — exactly the
   review-visibility mechanism the original tripwire relied on.
2. `test_committed_mapping_is_reproducible_from_its_own_recorded_scores` re-derives the split from the
   eight committed per-CPU scores using the **production** `_split_into_two_clusters`, checks the
   recorded separation ratio against those scores, checks it clears the config's own thresholds, and
   checks the `EfficiencyClass` map agrees with the split. Hand-flipping the flag now requires
   fabricating eight numbers that genuinely cluster — a far higher bar than typing `[0,1,2,3]`.
3. `test_committed_verification_thresholds_are_unchanged` pins 1.25 / 0.15 / true, closing the other
   route to a cheap pass: lowering a threshold instead of forging a measurement.

The three refusal tests (`load_verified_topology` and both `affinity_for` targets, including under
`allow_unverified`) were reading the **real** config and passing only because it happened to be
unverified. They would have silently stopped testing refusal the moment this commit landed. They now
run against an explicit `unverified_config` fixture, so spec §4's "refuse rather than guess"
guarantee is tested on purpose rather than by accident. No test was weakened, skipped, xfailed, or
deleted; the suite went from 189 to **191**.

### Toolchain

**191 passed** (was 189), **ruff clean**, **mypy clean** (21 source files). The writer-defect
regression tests pass, including the one asserting that everything outside the `topology:` block
round-trips byte-identically.

### AF-005 — **CLOSED**

AF-005 required AC power, the pinned plan, and `assert_power_pin.ps1` run as an aborting gate. All
five AC runs recorded `on_battery: false`, the pinned Best Performance plan, battery saver off, and an
empty `pinned_condition_deviations`, with the pin asserted at exit 0 before each measurement. The
citing run satisfies it. Its substance was discharged earlier; formal closure was held for the
acceptance commit, which is now `a3d2323`. **Closed.** The finding's forward-looking part is not
closed by this and is not claimed to be: a *gate that refuses to start* outside pinned conditions
remains M2 scope, as AF-005 itself states. What exists today records and reports deviations.

### Spec §10 open question 4 — **CLOSED**

Does Windows' `EfficiencyClass` agree with the measured P/LP-E split on Platform A? **Yes.** Across
all five AC runs — `3fb88dcd`, `963a849e`, `855e3590`, `7b5fc2e2`, `fb5cd2d5` —
`efficiency_class_ordering_matched: true`, with `direction: higher_is_faster` and
`partition_matched: true`: CPUs 0–3 report `EfficiencyClass 1` and are the fast cluster, CPUs 4–7
report `0` and are the slow cluster. The convention on this platform is therefore
**higher `EfficiencyClass` = faster core**.

**Scoped to Platform A only.** Windows does not define the numeric direction as a contract, and the
opposite convention is reported on other vendors' hybrid parts. This closure **does not** license
reading the mapping from `EfficiencyClass` on Platform B or any other machine, and it does not remove
the requirement that every run assert the committed mapping rather than infer one.

### M1 — **ACCEPTED**

Acceptance rests on: the P/LP-E mapping measured under pinned AC conditions and committed at
`a3d2323` citing `fb5cd2d5`; five independent AC runs agreeing on membership and all exceeding the
pre-registered prediction; AF-005 discharged; open question 4 closed; AM-008 resolved; the manifest,
schema, blinding, and write-once machinery green at 191 tests with ruff and mypy clean; and the raw
artifacts now committed so the citations resolve off this host.

**M2 was not started.** No `seam/telemetry/`, no energy, thermal, PDH, or LHM code was written. No
verification threshold was adjusted. No run was discarded. No sealed run was modified. The five
original `analysis/` probe artifacts are untouched. AM-002, AM-004, and AM-012 were not edited.

**`topology.verified: true` is now committed, which arms every downstream consumer.** `cpu-p` and
`cpu-lpe` resolve from this point on, and the first M2 code to call `affinity_for` will get a real
CPU list rather than a refusal. That is the intended effect, and it is also the reason the tripwire
was strengthened rather than merely retargeted.

---

## 2026-07-30 — M1 limitation: post-data agreement criterion

**This is the weakest link in the M1 evidence chain. It is stated plainly, not buried.**

### What was pre-registered vs what was not

- The charge-load **mechanism** was pre-registered in commit `99da687` **before** any AC topology
  measurement: charging draws adapter headroom and adds chassis heat; both depress P-core turbo
  more than LP-E turbo; therefore separation should widen on AC relative to the battery baseline
  `0d7c607b` (1.3088335685389512).
- The agreement **criterion** (relative difference of separation ratios vs the larger `cv_fast` of
  the pair) was formulated **POST-DATA** as AM-012, after runs A (`3fb88dcd`, 1.3876038015371646)
  and B (`963a849e`, 1.3599431469328718) exposed a units ambiguity in the stop-rule wording.
- The **comparator restriction** to settled-charge runs {C, D} was applied **POST-DATA** as
  AM-013, after the all-pairs matrix showed B vs D exceeding the limit — though AM-013 applies a
  pre-registered mechanism (charge load as covariate) to justify the restriction.

### The B-vs-D failure and how it was resolved

| Pair | Relative difference | Limit (larger cv_fast) | Result |
|---|---:|---:|---|
| B `963a849e` vs D `7b5fc2e2` | **2.8218%** | **2.4061%** | **FAIL (1.17× over)** |

**Therefore: the B-vs-D failure was resolved by a post-data criterion choice.** Those words are
deliberate. The mapping was not committed under the all-pairs rule; it was committed after the
comparator set was restricted to settled-charge runs {C `855e3590`, D `7b5fc2e2`}, which agree at
0.5124% against a 2.0705% limit, and after citing run E `fb5cd2d5` (1.380460703128493) agreed with
both under AM-012.

AM-012 and AM-013 remain labelled **POST-DATA**. They are not retroactively relabelled as
pre-data. M1 was not re-run to manufacture a cleaner history.

### Runs A and B

Runs A and B were **reclassified as supporting evidence** for the charge-load mechanism, **not
discarded**. Their numbers remain in this log and in `raw/`:

| Run | Ratio | Charge |
|---|---:|---|
| A `3fb88dcd` | 1.3876038015371646 | 69→70% bulk charging |
| B `963a849e` | 1.3599431469328718 | 70→71% bulk charging |

### Forward binding

From M2 onward, agreement and acceptance criteria are pre-registered before data collection for
that milestone (AM-015). M1 is the worked example of the cost of doing otherwise.

---

## 2026-07-30 — Charge-load effect size calibration (walk-back)

The pre-registration (`99da687`) and early narrative described a pass under charging as
**"conservative evidence."** That characterization is **an overstatement** given the measured
effect size.

| Set | Mean separation ratio | Runs |
|---|---:|---|
| Bulk-charge A/B | ~1.3738 | `3fb88dcd` (1.3876038015371646), `963a849e` (1.3599431469328718) |
| Settled C/D | ~1.3953 | `855e3590` (1.3917174862228963), `7b5fc2e2` (1.3988665756315648) |
| Citing E | 1.380460703128493 | `fb5cd2d5` at 99→99% |

**Effect size:** the bulk-vs-settled gap is on the order of **~1%**, against run-to-run variation on
the order of **~2%** (AM-012 relative spreads and within-cluster `cv_fast` values). The
charge-load effect is **real in direction** (bulk charge compresses separation relative to
settled C/D) but **not clearly separable from noise at this n**.

**"Conservative evidence" is walked back.** A pass under charging is not stronger evidence than a
pass at rest at the precision this instrument and this n provide.

### Preserved corrections (do not weaken)

1. The covariate is **charging LOAD**, not charge **LEVEL** (E at 99% sits **below** C and D in
   ratio; SOC monotonicity is **NOT established**).
2. Do **not** use the charge-load mechanism to justify any future comparator exclusion without
   first measuring the effect with adequate n.

---

## 2026-07-30 — Governance pass COMPLETED (Items 1–6)

| Item | Status |
|---|---|
| 1 Re-sync governing docs / close AM-002 | **DONE** — as-delivered blueprint `11da7b34…` / spec `5b0275da…` hash-verified; §16.1–16.9 confirmed; AM-002 RESOLVED citing as-delivered blueprint SHA |
| 2 AM-011 unused; AM-014 in blueprint | **DONE** — both blueprint AM-011 occurrences renumbered to AM-014 with threshold-based substance; blanket "NOT committed" ruling does not survive as policy; AM-011 remains deliberately unused in `AMENDMENTS.md` |
| 3 Post-data disclosure | **DONE** — subsection above; AM-015 forward-binding rule |
| 4 Charge-load calibration | **DONE** — ~1% vs ~2% noise; "conservative evidence" walked back |
| 5 Elevation requirement in spec §3 | **DONE** — §3.0 inserted; S2 bullet cross-references refusal pattern; **no telemetry code** |
| 6 Fence 1.38× ratio | **DONE** — YAML comment + `seam.mdc` + regression test |

### Document pin chain (standing = post-edit)

| Role | Blueprint SHA-256 | Spec SHA-256 |
|---|---|---|
| Standing (post-edit) | `ffe349804fa36de9ac94473ecd9372c6cc1234c91424242e5fc39040a67b1253` | `9a905a340c513b40cd26a7d381b7d8ba9a28be316eaab04126aeb65cd5e1ca5b` |
| As-delivered (superseded) | `11da7b34936522fc37531f1321d7150f7f3788da6de6cce0f7472e6a92ef4cfd` | `5b0275da53be54d382e1b67e28d71c8429d98b4c277c7362f58d0beaaf166ad2` |
| Prior restore (superseded) | `72d9b6a32ea40d07201d35e22cfc6db6c0f62311a40c15bc5ecf4f9c4567c878` | `f42fad5bdf7377393684483b1f36dcc2da99e4fca94e9dd79292dde356198148` |

**No M2 code.** No `seam/telemetry/`. No measurement runs. No M1 re-run.

---

## 2026-07-30 — AM-016: pinned profiles by measurement class (spec §3.7)

**PRE-DATA w.r.t. M2 · authorized by Z. Johnson.** Spec-only; no telemetry implementation.

Inserted Phase −1 spec **§3.7** defining `ac-pinned` and `battery-pinned`, with class→profile
mapping (topology/thermal → AC; M2.1 battery char → battery; M2.5 energy → battery **and**
elevated). Documents why SoC window alone is insufficient (M1 charge-**load** finding from
`fb5cd2d5` vs C/D), the M2.5 compound constraint, and the open thermal-constant transfer
question across profiles. M2.1/M2.3/M2.5 acceptance bullets updated. Standing spec pin:
`a102d201311405e2d921b4c71dcf79aff9b3fc9994e8a1f438a353945bc6d7f2` (32411 bytes). Prior
standing pin `89d8feef…` archived under AM-009.

---

## 2026-07-30 — M2.1 Step 2–4: profile pinning + S1 sampler (STOP before measure)

**Code landed; measurement NOT started.** Machine remains under M1 AC regime until the operator
confirms unplug + quiesce.

### Implementation

- `configs/platforms/aipc-c1.yaml`: `power.profiles` (`ac-pinned` / `battery-pinned` with
  `settle_s` / `soc_window_pct` **null**, `determined_by: M2.1`), `class_profile_map`,
  `s1_characterization` block.
- `seam/powerstate.py`: `assert_profile`, `profile_for_class`, `raise_if_profile_mismatch`,
  extended `manifest_power_state` (§3.7 fields).
- `seam/telemetry/s1_battery_char.py`: WMI/`BatteryStatus` 10 Hz sampler → `samples.ndjson`;
  pure analyzer for update period / quantum / min viable duration. Not the §3.6 unified sampler.
- Schema + tests for profile mismatch refusal and capacity-series analysis.
- **No RAPL / thermal / STREAM / M2.5 cross-validation code.**

### Pre-measure proposal (awaiting operator confirmation)

| Item | Proposal | Rationale |
|---|---|---|
| Duration | **≥1800 s** (30 min) continuous | Spec M2.1 acceptance; enough changes for ECDF/IQR |
| SoC window (proposed, not yet pinned) | **[40, 85]%** | Headroom above empty/protective cutback; below CV top-off region where charge-load effects dominated M1; hard assert remains **not charging + settled** |
| Synthetic load | `cpu_spin_all_logical` (YAML) | Constant load so DischargeRate / capacity deltas are interpretable |
| `settle_s` / `soc_window_pct` in profile | remain **null** until citing run | AM-006 discipline |

### Quiesce checklist (operator)

1. Power plan: **Best Performance** (`ec87a53a-19a6-4f4a-980f-ab27cc929b25`).
2. Display brightness: set to a **fixed** value and leave it; record the value (profile field null until measured).
3. WiFi: prefer **off** (or leave connected but record state); no downloads.
4. Windows Defender realtime: leave as-is but **record**; do not start a scan.
5. Windows Update: pause if possible; record whether paused.
6. Close: browsers with video, OneDrive/Dropbox sync storms, gaming overlays, Cursor/IDE heavy index if possible, any other background clients that spike CPU/disk.
7. **Unplug AC** and confirm **not charging** (System → Power, or battery icon). Wait out settle once `settle_s` is known; for the first characterization run, wait **≥5 min** after unplug before starting the 30 min sample (settle_s still TBD).
8. Confirm SoC is inside the proposed **40–85%** band before start.
9. Reply in-chat that the machine is **unplugged, not charging, and quiesced** — only then may measurement start.

### Document pins verified at this stop

| Document | Expected SHA-256 |
|---|---|
| `docs/SEAM_research_blueprint.md` | `ca5b0c44b3918acf454669aec5fa41c815acc6a76d4c83fc10a18b94792dfe8c` |
| `docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md` | `a102d201311405e2d921b4c71dcf79aff9b3fc9994e8a1f438a353945bc6d7f2` |

Task brief listed post-§3.0 pin `89d8feef…` for the spec; that hash is **superseded** by AM-016 §3.7 (`a102d201…`). Mismatch vs brief is expected and archived — not a STOP condition after Step 1.

---

## 2026-07-30 — M2.1 measurement + findings (AM-017)

**Operator confirmed unplugged.** Preflight: `on_battery=true`, `charging=false`, plan Best
Performance. SoC at start **99%** (outside the then-proposed 40–85 window; window was not yet
pinned). Run proceeded; SoC recorded as covariate.

### Discarded incomplete attempts (logged; not cited)

| run_id | Reason |
|---|---|
| `adbca28c-1f0d-43cf-9722-dfc12f05f740` | Aborted: samples were buffered until end; restarted with streaming writes |
| `5265bbb1-d611-495e-9004-80693980bd70` | Aborted: orphan spin workers + PowerShell-per-sample WMI (~375 ms/poll) starved 10 Hz |

Installed `WMI`+`pywin32` into `.venv-seam` (added to `seam/requirements.txt`) so a persistent
COM session sustains ~10 Hz (~12 ms/poll).

### Citing run

**`911965cf-257c-4276-954b-17611a5e75eb`** — sealed; `allow_dirty=true`; synthetic load
`cpu_spin_all_logical` on logical CPUs `[0..7]`; 17910 samples / 1799.85 s; SoC 99%→86%.
Full report: `derived/m2_1/911965cf-257c-4276-954b-17611a5e75eb_report.json`.

### (a)–(g) summary (distributions; see report JSON for ECDF / CIs)

| Item | Result |
|---|---|
| (a) Update period | median **19.7902616 s**; IQR **[7.3849894, 23.4181828]**; bootstrap CI95 for median **[15.9701433, 20.4923018]**; ECDF in report. Not a fixed period. |
| (b) Per-update energy increment | median **92 mWh**; IQR **[34, 126]**; CI95 for median **[81.0, 104.25]**; mean **95.30526315789474 mWh**. **Not a fixed counter quantum** — see closeout Item 1 (time-driven EC). Smallest observed increment **11 mWh**. |
| (c) Min observed increment | **11 mWh** (power-dependent floor in this run, not a device quantum) |
| (d) **MIN VIABLE ENERGY-RUN DURATION** | **395.805232 s** (numeric unchanged); CI95 **[319.402866, 409.846036]**. Justification corrected in closeout Item 1 (edge effect vs update period, not "≥20 quanta"). |
| (e) `settle_s` | **360 s** — three consecutive 60 s DischargeRate windows within **±5%** relative band |
| (f) SoC dependence | see closeout Item 4(a) — **not independent**; mean DischargeRate −13.2% high→lower half (CI95 below) |
| (g) EC smoothing | see closeout Item 4(b) — DischargeRate is EC-smoothed relative to Δcap; prefer Δcap (AM-018) |

### Profile bounds written (`configs/platforms/aipc-c1.yaml`)

- `settle_s: 360` · `soc_window_pct: [40, 85]` · `discharge_rate_stable_band_frac: 0.05`
- citing `settle_s_run_id` / `soc_window_run_id` = `911965cf-257c-4276-954b-17611a5e75eb`

### Spec / pin

- §10 OQ2 **CLOSED** (AM-017). Standing spec pin:
  `18cf9264cef0b08ea01c3d42d1d1d01389a296f6477aac96059816dcc2778328` (33236 bytes).
- Prior `a102d201…` archived. Blueprint pin unchanged (`ca5b0c44…`).

**No M2.2–M2.5 code.**

---

## 2026-07-30 — M2.1 closeout (Items 1–4)

Citing run unchanged: `911965cf-257c-4276-954b-17611a5e75eb`. No re-measure.

### Item 1 — Time-driven identity (VERIFIED)

| Quantity | Value |
|---|---:|
| Σ\|Δcap\| / changes (mean step) | 9054 / 95 = **95.30526315789474 mWh** |
| duration / changes (mean interval) | 1799.8530491 / 95 = **18.945821569473683 s** |
| mean_power × mean_interval | 18109.478446753492 mW × 18.945821569473683 s = **95.30526315789474 mWh** |
| Relative agreement | **0** (exact within float) |
| p10 cross-check | 2.6097349 s × 18.109478 kW → **13.128 mWh** vs observed min step **11 mWh** |

**Mechanism.** The EC updates `RemainingCapacity` on a roughly fixed ~19 s cadence; step size
varies because **power** varies, not because a device quantum varies.

**Minimum-duration justification (rewritten; numeric unchanged).** The analysis window must be
long relative to the **update period**. The dominant error is an **edge effect** (unknown phase
within the first and last intervals). Modelling two unknown half-period edges gives uncertainty
≈ `period / duration`. Requiring ≤5% yields `duration ≥ 20 × period`. With
`period_median = 19.7902616 s` this is still **`min_viable = 395.805232 s`** (CI95 via period
median bootstrap **[319.402866, 409.846036]**). This is **not** "≥20 energy quanta" — there is
no fixed quantum. Observed per-update mWh increments are **power-dependent**, not a counter
property.

Planning (config `s1_characterization`): floor **410 s**, adopted **480 s**, reserve p90
**713 s** only for single-conclusion points.

### Item 2 — AM-018 S1 estimator (PRE-DATA w.r.t. M2.5)

Locked: **`ΔRemainingCapacity` only** for all energy work / M2.5 regression. Rate vs Δcap
totals 9779.124 / 9054.0 mWh (**+8.0%**); integrated DischargeRate is **cross-check only**,
never substituted into the regression. See `AMENDMENTS.md` AM-018.

### Item 3 — Battery budget for §3.2 sweep (NO DECISION)

| Capacity field | mWh | Source |
|---|---:|---|
| Design | **68607** | `root\WMI` `BatteryStaticData.DesignedCapacity` (Win32 null) |
| Full charge | **69043** | `root\WMI` `BatteryFullChargedCapacity` (Win32 null) |
| Usable in SoC [40,85] | **31069.35** | 0.45 × 69043 |

Assumptions for cost model (explicit):
- 8 load levels linspace **15→55 W** (vendor `min_w`→`turbo_w`), **not** at the 18.1 W mean
- per-level load duration = adopted **480 s**
- one `settle_s` = **360 s** at 15 W
- inter-level cooldown: **illustrative 120 s × 7 at 15 W** (thermal constants still null —
  AM-006; labelled non-binding for M2.3)
- Scenario A = load + settle + illustrative cooldown
- Scenario B = A + §3.2 idle-load-idle brackets (`T_idle=180 s` each side × 8 levels at 15 W)

| Scenario | Energy (mWh) | vs usable 31069 |
|---|---:|---|
| Load only (8×480 s) | 37333.33 | **exceeds by 6264** |
| A (+settle+cool) | 42333.33 | **exceeds by 11264** |
| B (+idle brackets) | 54333.33 | **exceeds by 23264** |
| Turbo-alone share (55 W × 480 s) | 7333.33 | ~24% of usable by itself |

**Verdict: does NOT fit** inside ONE discharge within `soc_window_pct [40, 85]` under the
adopted 480 s planning duration.

**Options (owner decision — not chosen here):**
1. **Split across multiple discharge cycles** — declare cross-cycle comparability an open
   question (charge history, temperature, FCC drift).
2. **Widen `soc_window_pct`** — feasibility gated by Item 4(a); dependence was measured only
   over ~99→86% SoC, so widening below 40% or above 85% is **not** supported by present data.
3. **Reduce load levels below 8** — requires an amendment; §3.2 / AM-004 require ≥8.

Full arithmetic: `derived/m2_1/battery_budget_m25_sweep.json`.

### Item 4(a) — SoC dependence (5f), with CIs

Constant `cpu_spin_all_logical` load; split series at midpoint (high-SoC half vs lower-SoC half).
RemainingCapacity ranges: high **[63586, 68182]** mWh; lower **[59128, 63586]** mWh
(approx SoC ~99→86% over the run — **above** the pinned window floor).

| Segment | mean DischargeRate (mW) | bootstrap CI95 (mean) | median | IQR |
|---|---:|---|---:|---|
| High-SoC half | 20943.68 | [20843.49, 21044.81] | 18437 | [16647, 26254] |
| Lower-SoC half | 18174.76 | [18110.63, 18236.64] | 17198 | [16000, 19194] |

Relative change in **means**: **−13.22%** (bootstrap CI95 **[−13.76%, −12.69%]**).
Relative change in **medians**: **−6.72%**.

**Conclusion:** reported DischargeRate at this fixed load is **not independent of SoC**
(and/or time-on-load thermal settling — not separable in one run). Window **[40, 85]** remains
appropriate; **widening for Item 3 is not justified** by this dataset.

### Item 4(b) — EC smoothing (5g)

**Conclusion: yes — DischargeRate is EC-smoothed relative to ΔRemainingCapacity.**

Evidence (run `911965cf…`):
1. Integrated rate **9779.124 mWh** vs Σ\|Δcap\| **9054.0 mWh** → ratio **1.080** (systematic
   +8.0%, not zero-mean noise).
2. Capacity updates arrive as discrete steps on a ~19 s cadence (Item 1), while DischargeRate
   varies within intervals; the rate signal does not track step edges one-for-one.
3. Spec §3.2 already preferred Δcap to avoid EC smoothing; AM-018 locks that preference for
   M2.5.

### Capacities in config + schema

`power.battery.design_capacity_mwh` / `full_charge_capacity_mwh` written; manifest
`power_state` gains the same fields (nullable). Tests cover presence.

---

## 2026-08-02 — AM-019: dependency graph replaces linear milestone chain

**PRE-DATA w.r.t. H1–H4 and all figures except S3/S4 energy. Authorized by Z. Johnson.**

Defect: Phase −1 spec §7 "work strictly in order" serialized instrument work ahead of the
research question, conflicting with blueprint §16.7 (H1 priority). M2 and M3 have no mutual
dependency.

Correction landed:
- Spec §7 rewritten as parallel tracks I / A / L after M1; **M-SLICE** first-class
- **M2 re-scoped to CERTIFY RAPL** (Stage A = 5 levels/target gate; Stage B = ≥8 confirmatory /
  Paper 2)
- Energy beyond RAPL cert = Paper 2; S4 may ship tokens/sec first
- Controlling gate = H1 (G2), risk-based incompleteness allowed
- `seam.mdc` milestone section updated; blueprint §16.7 affirmed (not rewritten)

Standing spec pin: `9a905a340c513b40cd26a7d381b7d8ba9a28be316eaab04126aeb65cd5e1ca5b`
(35968 bytes). Prior `18cf9264…` archived.

**Blueprint §11 applied 2026-08-02 (same amendment).** Gates declared risk-based; **G0** energy
criterion becomes RAPL **certification** (Stage A, ≥5 levels/target + NPU coverage verdict); new
confirmatory **G0-B** carries the full ≥8-level AM-004 criterion to Phase 3 / Paper 2 and does not
block G1/G2; **G1** energy decomposition conditional on G0-B; §14.2 changelog row added. Standing
blueprint pin `ffe349804fa36de9ac94473ecd9372c6cc1234c91424242e5fc39040a67b1253` (64861 bytes);
prior `ca5b0c44…` archived. AM-004's physics is carried verbatim into G0-B — unchanged, only
re-timed.

**No measurement runs. No M2.2+ code.**

---

## 2026-08-02 — M-SLICE build landed; collection BLOCKED on two environmental faults

Instrument and pre-registration complete. **No data collected. No money spent
(`derived/budget/` ledger empty).** Recorded now so the pre-registration is provably prior to
any observation.

### Pre-registration (all PRE-DATA)

| Amendment | Substance |
|---|---|
| **AM-020** | Model pinning is "pinned identifier **in the provider's convention**", not "dated alias". `claude-sonnet-5` is dateless BY DESIGN and IS the pin; a constructed dated variant does not exist. Floating aliases (`-latest`) stay forbidden. Serving-stack drift under a fixed ID is documented by the provider, so the **daily canary is retained** and this is its justification. |
| **AM-021** | **Cross-model token deltas are not a valid behavioral metric.** Claude 4.7+ emits ~30% more tokens for identical text than earlier models; local models use unrelated tokenizers. A Δ-token comparison measures tokenizer disagreement plus behavior and cannot separate them — and the bias points *toward* H1 at roughly the magnitude of the ≥20% G2 threshold. Behavioral currency becomes **characters/bytes** (or re-tokenization under one declared reference tokenizer). Native counts retained for **cost only**. |
| **AM-022** | M-SLICE policy frozen: **predictive** (not preemptive) local-first routing; prefill included; deadline **advisory** with overrun rate reported as the predictor's error rate; isolation invariant asserted in code; pre-registered prediction that the two curves collapse under `escalation_lpe(D) ≈ escalation_p(D × R_p/R_lpe)`; preemptive semantics **deferred** as the H4 cascade axis. |

### Built (minimum viable subsets only)

`seam/budget.py` (durable ledger + structural ceiling), `seam/backends/` (protocol, OpenVINO CPU,
Anthropic w/ caching), `seam/agent/` (fixed scaffold, deterministic tool world, policy),
`seam/analysis/slice_stats.py` (bootstrap CIs, noise floor, A/A verdict, 2×CV null rule),
`seam/tools/` (scripted IR export, per-core affinity verifier, phase runner).
Configs: `configs/mslice.yaml`, `configs/pricing/anthropic.yaml` (dated table spanning the
2026-09-01 increase), `configs/tasks/bfcl_slice_v1.json` (20 tasks, frozen before collection).

Suite **240 passed**, ruff clean, mypy clean (45 files).

### BLOCKER 1 — local model weights unreachable from this network

`huggingface.co` resolves and completes TLS, and **small files download normally**, but every
**large weight file** gets `WinError 10054` (connection reset) on the `resolve` HEAD, or opens a
connection that transfers **zero bytes**. Reproduced on `Qwen/Qwen2.5-3B-Instruct`
(`aa8e7253…`, shard 1 of 2 — shard 2 *did* download, 2101 MB) and on
`Qwen/Qwen2.5-1.5B-Instruct` (`989aa798…`, `model.safetensors`), with and without
`HF_HUB_DISABLE_XET=1`. Consistent with a middlebox resetting large binary transfers.

**No third-party mirror was used.** `hf-mirror.com` is reachable, but pulling research weights
from an unofficial mirror would weaken the ModelSpec's provenance claim, which this project
cannot afford. Recorded as a deliberate refusal, not an oversight.

Consequence: step 1 (throughput baseline) cannot run, so `R_prefill`/`R_decode`,
the cpu-p/cpu-lpe ratio, `n_out_pred`, the frozen deadlines, and the **mandatory per-core
affinity verification** are all outstanding.

### BLOCKER 2 — `ANTHROPIC_API_KEY` absent from the environment

Not visible to the harness process. The cloud arm refuses to construct a client without it, by
design (the key is read from the environment only and is never logged or written to a manifest).
Checkpoint 1 (single key-validation call) therefore has not run.

### Spend

**USD 0.00.** Ledger `derived/budget/ledger.ndjson` does not exist because no paid call was ever
authorized. Slice ceiling 10.00, project ceiling 50.00 — both unconsumed.

---

## FINDING — OpenVINO PCORE_ONLY fall-through on Panther Lake (2026-08-02)

**Pre/post data:** PRE-DATA w.r.t. M-SLICE partition measurement. Evidence from throwaway
0.6B validator artifact derived/mslice/affinity_validation.json (not yet the quiesced A1–A6
matrix on the 4B).

**Observation.** With SCHEDULING_CORE_TYPE=PCORE_ONLY, ENABLE_CPU_PINNING=true,
INFERENCE_NUM_THREADS=4, mean per-CPU utilization during generate() was high on **all eight**
logical CPUs (approx 76–93%), including LP-E CPUs 4–7. M1-committed mapping expects P-cores
on 0–3 only. Verdict: refused; leaked onto [4,5,6,7].

**Asymmetry argument.** Under a working confinement, excluded cores bound background. On this
arm the excluded cluster ran at ~90% — far above an idle background bound — so the reading is
leakage, not noise. (A1–A6 will repeat with baseline-subtracted deltas on a quiesced machine;
watcher processes are now on the quiesce forbidden list.)

**ECORE_ONLY** on the same artifact largely loaded 4–7 (with a possible leak onto CPU 3 in the
absolute-util reading). A2 (ENABLE_CPU_PINNING explicit vs default) is the load-bearing test
that distinguishes a configuration miss from an OpenVINO defect.

**Adopted mechanism.** Not yet written. DEFERRED-BY-DEPENDENCY on A1–A6. Isolation invariant
requires one symmetric mechanism for both arms.

**Upstream.** Draft only — docs/upstream/openvino_pcore_only_panther_lake_DRAFT.md. Not submitted.

**C9.** Accrues as a client-platform measurement pathology: a competitor measuring P-vs-LP-E with
OpenVINO on Panther Lake can have leaking affinity and not know it.

---

## Phase E post-verification record-keeping (2026-08-02) — PRE-DATA w.r.t. A0–A6 / H1

### Ledger externally verified

Independent recompute of all **11** `derived/budget/ledger.ndjson` rows against
`configs/pricing/anthropic.yaml` tier `introductory` (effective through 2026-08-31):
**11/11 exact matches, zero mismatches.** Total actual spend **USD 0.147928**
(E1 0.001044 + E2 0.146884). Pricing version `2026-08-02.1`.

### 0.1 — Proportion CI method (project-wide)

**Chosen method: Wilson score interval** (`seam.analysis.proportions.PROPORTION_CI_METHOD =
"wilson_score"`).

The E2 failure-rate interval reported as “[0, 27.8%]” matches **Wilson** for 0/10
(upper 27.75%), **not** Agresti–Coull (upper 32.09%). Rule of three for 0/n is 3/n
(= 30.0% at n=10) and may be cited as a bound in prose, but every reported proportion
interval in this project uses Wilson. Label corrected in `seam/tools/phase_e_cloud.py`
and enforced by `tests/test_proportions.py`.

### 0.2 — Do NOT recalibrate the projector on Phase E data

Verified separately: the Phase E synthetic payload tokenizes at **exactly 1.000000
tokens/byte** (incremental slope over 8000 bytes) with a **constant 452-token intercept**.
Real content runs ~3–4 bytes/token. Back-solving the Phase E projections shows the
estimator assumed ~2.95 bytes/token, which is **correct for realistic text**.

The 92–176% under-projection on E2 calls 1–3 is therefore an **artifact of the synthetic
1-tok/byte test payload**, not a defect in the projector. Recalibrating the byte→token
slope against Phase E would break the projector for the workload it will actually serve
(BFCL / prose prompts). **Do not “fix” this.**

### 0.3 — Genuine projector gap: cache state

Cache-read calls over-projected by ~67% because estimates assumed worst-case cache-write
on every call. Safe for the authorization bound; useless as a calibration estimate.

**Implemented:** `BudgetGuard.projected_call_usd(..., cache_state={"cold","warm","unknown"})`.
Authorization still always uses `worst_case_call_usd` (= cold/write).
`AnthropicBackend` tracks `_cache_prefix_written` and passes `warm` on subsequent cached
calls. Tests: `tests/test_budget_cache_projection.py`.

### 0.4 — Cloud round-trip for the deadline grid

Measured wall-clock on E2 (10 sequential long POSTs): **min 1.226 s, max 5.370 s,
mean 2.469 s**. This is the escalation cost input to the deadline grid.

Rate limits observed at E1 (10k req, 10M input tok, 2M output tok, 12M aggregate tok)
are far above H1 needs — **throughput/rate-limit question CLOSED**. Binding H1 constraint
is tokens (and cost), not request rate.

### Code changes from response shapes (cross-ref)

- `claude-sonnet-5` rejects `temperature` (400) — omitted in `cloud_anthropic.py`.
- Usage fields include nested `cache_creation.{ephemeral_5m,ephemeral_1h}_input_tokens`;
  flat `cache_creation_input_tokens` matched 5m counts in E2.

### A0–A6 / Phase D status at this entry

Matrix harness upgraded (default **5 blocks**, A0 required, per-gen ≥10 s baseline,
prefill/decode separate, PDH frequency sampler, Wilson CI module, AC hard-refuse).
**Measurement not yet run:** machine was **on battery** at the attempt; quiesce requires
AC. STOP — not a workaround.

---

## INTERRUPTED — A0–A6 matrix mid-run (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Incomplete run is not a confinement result.

**What ran.** Full matrix launched on AC at 2026-08-02T23:59:30Z
(`--blocks 5 --seed 20260802 --cooldown-s 30`). Blocks 1–3 completed with every cell
`ok=True`. Block 4 completed A3, A4, A0 successfully; **A2 child exited 4294967295**
(unsigned -1; process killed — consistent with sleep / AC loss / OOM). Parent/shell then
exited with the same code at 2026-08-03T13:20:00Z (~13.3 h wall, including overnight).
**No `affinity_matrix.json` was written** — results were only flushed at end.

**Quiesce at resume (2026-08-03 morning).** AC **disconnected** again (`on_battery=true`,
SoC ~62%, charging=false). Protocol STOP. Not resumed with `--allow-battery`.

**Log-only decode tok/s breadcrumbs** (not classification; not for adoption) show the
expected P vs LP-E throughput split (~15–17 vs ~7–10 tok/s decode) across successful
cells. Without per-core baseline-subtracted deltas and full 5 blocks, A2 verdict and
mechanism adoption are **unavailable**.

**Harness fix applied before next attempt.** Per-cell durable checkpoint
(`*.partial.json`), mid-matrix AC re-check, and STOP-on-child-killed. Next run must be
a **full** 5-block matrix on sustained AC — incomplete blocks are not patched with log
crumbs.

**Phase D.** Not started (blocked on A.8 adoption).

**Artifact.** `derived/mslice/affinity_matrix_interrupted_20260803.json`

## 2026-08-03 09:21 — affinity_matrix stopped (AC loss)

- A0–A6 affinity matrix stopped after AC loss (Windows kill mid block 4 / A2; exit 4294967295).
- Partial cells not publishable; no `affinity_matrix.json` / `phase_d` sealed.
- Marker: `derived/mslice/affinity_matrix_stopped_battery.json` (reason `ac_lost_mid_run`; ok=True count=24).
- Full AC re-run required from scratch; do not resume on battery.

---

## FINDING — A0–A6 matrix complete on AC; A0 sanity FAILED; mechanism not adopted (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Sealed matrix exists; adoption gate failed.

### Quiesce (recorded in artifact)

| Field | Value |
|---|---|
| on_battery | false (mains) |
| charging | true |
| battery_pct start → end | 63.0 → 99.0 |
| power plan | Best Performance / `ec87a53a-19a6-4f4a-980f-ab27cc929b25` |
| overlay GUID | `00000000-0000-0000-0000-000000000000` |
| display_brightness | 100.0 |
| defender_realtime | enabled |
| ambient_c | null (`unavailable_pending_M2.3_LHM`) |
| package_temp_c | null |
| thermal.regime | confound |
| hard forbidden hits | none (OneDrive.exe soft-recorded) |
| threads | 4 (`INFERENCE_NUM_THREADS`) |

### Citing artifact (no sealed `raw/` run_id — harness gap)

- Path: `derived/mslice/affinity_matrix.json`
- SHA-256: `d02a14cbb40e29269e5163df4bd418dda83ad6646564672e365573e1be20ef27`
- Bytes: 240868
- Wall: 2026-08-03T09:22:03 → 10:46:17 local (AC online throughout)
- Log: `derived/mslice/affinity_matrix_run2.log` (tee of the successful AC re-run; prior interrupted attempt remains in `affinity_matrix_run.log`)
- Command: `python -u -m seam.tools.affinity_matrix --blocks 5 --seed 20260802 --cooldown-s 30 --out derived\mslice\affinity_matrix.json`
- OpenVINO 2026.2.1 / GenAI 2026.2.1.0; model `Qwen3-4B-int4-ov`; prompt_sha256 `f1f2eddead735a108a9d6b4a083a7696d1d27ff1de303d7635aa9af8e8ac91fa`
- **Manifest gap:** affinity_matrix does not emit a sealed `raw/<run_id>/manifest.json`. Citation is path + SHA-256 + timestamp above until that is wired.

### Noise band

`NOISE_BAND = 2 * mean(per-core CV of pooled idle baseline means) = **1.4096`**
(pooled n=70 baseline means per core 0–7).

### Prefill sampling failure (blocks all confinement verdicts)

**70/70 scored generations have empty `prefill_mean_pct_per_cpu`.** Prefill deltas are therefore baseline-subtracted against missing phase samples and land negative on every core; `r_prefill_tok_s` is null everywhere. Every cell is **INVALID on prefill**. Decode util sampling worked. This is a harness/measurement defect, not a silicon result. Do not adopt from decode-only.

### Per-core mean Δ% tables (baseline-subtracted)

CPU order: 0,1,2,3 (P) | 4,5,6,7 (LP-E). Values are mean across 5 blocks × scored gens.

#### Prefill Δ% (unusable — empty phase samples)

| Cell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | pref. verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A0 | -16.83 | -12.98 | -10.99 | -26.85 | -18.34 | -18.29 | -19.62 | -23.31 | N/A |
| A1 | -12.01 | -7.64 | -6.88 | -20.91 | -16.57 | -17.54 | -16.80 | -20.65 | INVALID |
| A2 | -15.34 | -10.90 | -9.69 | -22.41 | -13.62 | -14.00 | -15.32 | -17.37 | INVALID |
| A3 | -18.38 | -13.70 | -10.99 | -27.43 | -19.23 | -19.13 | -22.56 | -23.79 | INVALID |
| A4 | -12.85 | -7.50 | -6.45 | -20.17 | -14.49 | -17.43 | -17.07 | -21.03 | INVALID |
| A5 | -19.46 | -14.36 | -12.52 | -29.80 | -16.13 | -16.87 | -17.18 | -21.56 | INVALID |
| A6 | -17.00 | -10.74 | -9.37 | -22.76 | -12.00 | -10.74 | -11.23 | -14.56 | INVALID |

#### Decode Δ% (sampled; not adoptible while A0/prefill gates fail)

| Cell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | decode states (0–7) | decode verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| A0 | 78.06 | 80.55 | 82.72 | 67.83 | 4.42 | 4.98 | 2.63 | 0.86 | L L L L A A A Q | N/A (sanity) |
| A1 | 82.81 | 85.10 | 86.93 | 74.00 | 5.68 | 6.01 | 6.68 | 4.65 | L L L L A A A A | UNCLEAR |
| A2 | 82.26 | 77.41 | 77.96 | 69.44 | 3.10 | 3.07 | 2.57 | 2.13 | L L L L A A A A | UNCLEAR |
| A3 | 1.84 | 3.22 | 2.78 | 2.64 | 74.40 | 74.40 | 72.03 | 71.98 | A A A A L L L L | UNCLEAR |
| A4 | -0.09 | -0.24 | -0.85 | 1.01 | 84.80 | 68.53 | 70.48 | 66.66 | Q Q Q Q L L L L | CONFINED |
| A5 | 76.56 | 81.59 | 83.30 | 67.52 | 1.43 | 0.38 | 1.13 | -1.35 | L L L L A Q Q Q | UNCLEAR |
| A6 | -5.93 | -3.18 | -2.88 | -3.72 | 83.70 | 84.96 | 85.13 | 82.81 | Q Q Q Q L L L L | CONFINED |

L=LOADED, Q=QUIET, A=AMBIGUOUS. Overall cell verdict = INVALID for A1–A6 (prefill INVALID).

### Mask readback

| Cell | process affinity mask | OpenVINO properties |
|---|---|---|
| A0–A4 | {0–7} | A1/A2: PCORE_ONLY (±pinning); A3/A4: ECORE_ONLY (±pinning); A0: threads only |
| A5 | {0–3} | threads only |
| A6 | {4–7} | threads only |

### Decode tok/s (5-block means; bootstrap CI on block means)

| Cell | mean | CI lo | CI hi |
|---|---:|---:|---:|
| A0 | 15.16 | 13.45 | 16.76 |
| A1 | 15.22 | 13.31 | 16.54 |
| A2 | 14.12 | 12.14 | 15.84 |
| A3 | 6.86 | 5.75 | 7.65 |
| A4 | 7.14 | 5.70 | 7.97 |
| A5 | 15.05 | 13.02 | 16.78 |
| A6 | 8.32 | 7.41 | 9.23 |

Prefill tok/s: **null** (not emitted by GenAI path in these runs).

### A0 sanity gate — FAILED

Decode loaded **4/8** CPUs (0–3 LOADED; 4–6 AMBIGUOUS; 7 QUIET). `all_cpus_loaded=false`.
With `INFERENCE_NUM_THREADS=4`, unconfined work saturates the P-cluster and does not load LP-E.
Harness sets `adopted_mechanism=none` and STOP. Cannot distinguish leakage from unsaturated workload.

### A2 verdict — inconclusive

A1 decode UNCLEAR + overall INVALID; A2 decode UNCLEAR + overall INVALID. Label **inconclusive** (not configuration / not defect / not non-reproduction). Upstream draft must not claim a settled PCORE_ONLY defect from this run.

### A3-vs-A6 (decode tok/s only; prefill null)

- A3 mean 6.863 vs A6 mean 8.322; ratio A3/A6 = 0.8247; relative Δ = 0.1753
- within-cell CV: A3=0.2051, A6=0.1447; material threshold 2×CV = 0.4102
- **material = false** at that threshold. Symmetry remains required on isolation-invariant grounds regardless.

### Throttle detectors

1. **PDH frequency:** methods `win32pdh`; n_min_pct_observations=320; global_min_pct_of_max=**19.0** → flagged `frequency_dip_below_80pct_of_max`
2. **Within-cell decode drift:** 35 pairs; **10** flagged with |g2−g1|/g1 > 15% (largest: A1 block3 +78.3%, A3 block2 −35.9%, A5 block2 +34.1%)
3. **Block-position regression:** slope_decode_tok_s_per_block = **+0.444** (throughput rose across blocks; not a decaying thermal collapse signature)
- `excluded_cells`: [] (flags recorded; no operator exclusion applied)
- Cooldown remains time-based / unvalidated (`thermal.regime=confound`)

### Adoption decision tree — STOP

1. Zero mechanisms CONFINED in **both** prefill and decode → `adopted_mechanism: none`
2. A0 sanity FAILED reinforces STOP
3. **Not written** to `configs/mslice.yaml` / `configs/project_state.yaml` confinement fields (remain null / DEFERRED-BY-DEPENDENCY)
4. Phase D **not started**
5. Adding blocks alone does not repair empty prefill samples or 4-thread A0 non-saturation — next work must fix those gates, not re-roll the same matrix

### Decision recorded by harness

```
adopted mechanism: none
reason: A0 sanity FAILED: not all CPUs LOADED in the unconfined reference.
a0_sanity_gate: FAILED
```


## FINDING — TTFT=0 root cause (GenAI plain-str return); streamer fix; A0 threads (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Supersedes the interpretation that empty prefill
samples in `affinity_matrix_ttft0_invalid_20260803.json` (sha256 `d02a14cb…`, formerly
`derived/mslice/affinity_matrix.json`) were an unexplained harness quirk.

### Root cause

OpenVINO GenAI **2026.2.1** `LLMPipeline.generate()` returns a plain `str` with **no**
`perf_metrics` attribute. `LocalOpenVinoBackend.generate` then set `ttft_ns=None`, and
`affinity_matrix._phase_means` treated that as `ttft=0`, so every util sample was classified as
decode. Prefill windows were empty (70/70); prefill deltas were baseline-subtracted noise
(negative everywhere); `r_prefill_tok_s` was null. **Not a silicon result.**

Probe (same IR / GenAI): `result_type <class 'str'>`, `has_perf False`.

### Fix (code)

1. `seam/backends/local_openvino.py`: always pass a `StreamerBase` that timestamps the first
   token; prefer `perf_metrics` TTFT when present, else `streamer_first_token`; **refuse**
   (raise `BackendError`) if TTFT remains unavailable — never emit silent zero.
2. `seam/tools/affinity_matrix.py`: missing/zero TTFT no longer collapses to decode-only;
   scored generations raise if TTFT is missing; default `--threads` **8** (Platform A logical
   CPU count) so A0 can saturate all cores (prior default 4 made `all_cpus_loaded` structurally
   impossible under OpenVINO's 4-thread P-preferring placement).
3. Unit tests: `tests/test_ttft_resolve.py`.

Live smoke after fix: `ttft_source=streamer_first_token`, `ttft_ms≈9324`, `wall_ms≈13282`.

### Side observation (Phase D relevance — not acted on here)

With `enable_thinking=False`, the chat template still opens an empty `<think>` and greedy
decode emitted real thinking text. Investigate before Phase D Arm 1; do not start Phase D
until a mechanism is adopted under valid prefill+decode.

### Artifact disposition

- Invalid TTFT=0 matrix preserved at
  `derived/mslice/affinity_matrix_ttft0_invalid_20260803.json` (do not adopt).
- Re-run of full 7×5 matrix on AC with TTFT fix + `--threads 8` is the next measurement.

### Spend

$0.00 (local only).


## FINDING — affinity_matrix sealed-manifest gap (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Instrumentation gap, not a silicon result.

**Observation.** The 2026-08-03 AC matrix cited at
`derived/mslice/affinity_matrix_ttft0_invalid_20260803.json` (sha256 `d02a14cb…`; formerly
`derived/mslice/affinity_matrix.json`) completed without emitting a sealed
`raw/<run_id>/manifest.json`. Citation was path + SHA-256 + timestamp only. Under blueprint
§5.2 / Phase −1 §0, every emitted number must trace to a run_id manifest — this run violated
that invariant.

**Disposition.** Gap closed in harness: `seam.tools.affinity_matrix` now calls
`seam.manifest.emit` for matrix/verification runs (`workload.kind=mslice_affinity_matrix`)
and writes `affinity_matrix.json` into the sealed run directory. Prior artifact remains
INVALID and must not be adopted. Do not backfill a fake run_id onto the invalid matrix.

**Spend.** $0.00.

---

## FINDING — OpenVINO PCORE_ONLY fall-through SUPERSEDED-PENDING-REMEASUREMENT (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Supersedes the 2026-08-02 FINDING
"OpenVINO PCORE_ONLY fall-through on Panther Lake" pending a clean dual-phase matrix.

**Why superseded (not retracted as false).** The 2026-08-02 throwaway 0.6B validator that
drove the upstream draft observed ~90% utilization on LP-E cores under `PCORE_ONLY`. That
reading was taken beside a multi-gigabyte download; absolute utilization (not
baseline-subtracted deltas) charged background load to the pipeline. On the later
baseline-subtracted AC matrix (invalid for other gates; sha256 `d02a14cb…`), A1 decode
excluded LP-E from LOADED and left ~5.8% AMBIGUOUS on outside cores — directional A1 vs A2
signal is preserved for a clean re-measure, but the original "90% leakage = defect" claim
does not survive baseline subtraction.

**Status.** `SUPERSEDED-PENDING-REMEASUREMENT`. Upstream draft
`docs/upstream/openvino_pcore_only_panther_lake_DRAFT.md` is **HOLD — do not submit**.
Re-evaluate A2 verdict tree (configuration / defect / non-reproduction / original finding
does not reproduce) only after a matrix with non-empty prefill+decode windows, A0a/A0b
references, global LOADED_THRESHOLD from A0a, and ac-pinned charging-complete.

**Spend.** $0.00.

---

## NOTE — affinity matrix harness repairs before re-measure (2026-08-03)

Part-1 fixes landed before verification/full matrix:

1. Fail-loud: empty/zero-duration util windows raise immediately; `ok=True` requires both
   phase windows non-empty with positive duration.
2. Prefill sampling: continuous util sampler across `generate()`; prefill/decode split
   post-hoc from first-token timestamp (never gated on phase-end). TTFT=0 root cause was
   GenAI plain-str return (prior FINDING); streamer path retained.
3. A0 → A0a (threads=8 saturation) + A0b (threads=4 default placement); both exempt from
   loaded-cores sanity. `LOADED_THRESHOLD = 0.5 * median(A0a per-core decode delta)` applied
   identically to every cell both phases. `NOISE_BAND = 2 * pooled idle per-core CV`.
4. ac-pinned: `require_charging=false`, ChargeRate max, brightness target 50 (not 100);
   abort if charging resumes mid-run. Empirically on aipc-c1: BatteryStatus reports
   `Charging=false`, `ChargeRate=0` when settled on AC at 100% SoC.
5. Sealed `raw/<run_id>/` manifest emit for matrix runs.
6. PCORE_ONLY FINDING marked SUPERSEDED-PENDING-REMEASUREMENT; upstream HOLD.

Invalid 2026-08-03 matrix (`d02a14cb…`) is diagnostic evidence only — not for adoption.


## FINDING — A0a threads=8 does not load LP-E; Part 2 verification STOP (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Verification block sealed; full 8×10 matrix NOT started.

**Citing run.** `run_id=fc262806-debf-4905-828b-2b8061dc0333`
(`raw/fc262806-debf-4905-828b-2b8061dc0333/`, derived `affinity_matrix_verify.json`).
`--blocks 1 --seed 20260803 --cooldown-s 60`. Spend $0.00.

**What passed.**
- Prefill windows: all scored gens n_prefill>=14, n_decode>=456, positive duration
- Prefill deltas positive on loaded cores
- charging==false entire block; brightness target=actual=50
- Sealed manifest emitted
- LOADED_THRESHOLD=21.8912 (= 0.5 * median(A0a decode deltas)); NOISE_BAND=1.3581

**What failed (STOP — gates never descope).**
- A0a with INFERENCE_NUM_THREADS=8 loaded exactly 4 cores (P 0–3). LP-E decode deltas
  1.7–6.4% (AMBIGUOUS under threshold 21.89). Does not meet "loads substantially more than
  4 cores." OpenVINO unconfined placement prefers the P-cluster even at threads=8; pool size
  alone does not engage LP-E.

**Sampler note.** Prefill TTFT on this IR is ~0.21–0.62 s (`perf_metrics` ≈ streamer).
100 Hz util sampling is required for >=10 prefill samples; 10 Hz structurally cannot.

**Disposition.** Part 3 full matrix and Part 5 Phase D not started. Mechanism not adopted.
Additive follow-up (not started): whether any OpenVINO property/thread setting engages LP-E
without process affinity — feeds the same confinement main-line if it varies a design-space
coordinate; otherwise record as displacing per blueprint §12.4.

---

## FINDING — OpenVINO default placement is P-cores; A0a demoted from saturation gate (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Instrumentation confirmed by verification
`run_id=fc262806-debf-4905-828b-2b8061dc0333` (do not re-run Part 2 verification). Invalid
2026-08-03 matrix `d02a14cb…` is not adopted from.

**Finding.** OpenVINO default placement selects the four P-cores (logical 0–3) regardless of
`INFERENCE_NUM_THREADS`. With threads=8, the pool oversubscribes those P-cores rather than
engaging LP-E (4–7). This is consistent runtime behavior, not a harness defect.
`SCHEDULING_CORE_TYPE` exists because the default is not "use everything."

**Spec corrections applied (harness).**
1. **A0a demoted.** A0a remains in the matrix as the oversubscription arm of the A0a-vs-A0b
   pair (threads=8 vs 4 on the same four P-cores OpenVINO chooses by default). No gate
   requires A0a to load substantially more than 4 cores / saturate all 8.
2. **Per-core LOADED threshold (two-pass).** Replaced global
   `LOADED_THRESHOLD = 0.5 * median(A0a decode deltas)` with
   `threshold(c) = 0.5 * delta(c)` from the cell that deliberately targets `c`
   (P-cores 0–3 from A5 decode; LP-E 4–7 from A6 decode), applied to both phases.
   `NOISE_BAND` unchanged (`2 * pooled idle per-core CV`). Analysis collects all cells first,
   then classifies — never during collection. Excluded cores of a cell are judged against a
   different cell's reference; included cores against their own = sanity check.

**Spend.** $0.00.

---

## INCIDENT — full affinity matrix ABORT: AC lost mid-run (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Partial matrix is NOT sealed for adoption.

**Run parameters.** `--blocks 10 --seed 20260803 --cooldown-s 120`
`--out derived/mslice/affinity_matrix.json`. Workload: 4B IR (sha256 074214fa…),
reasoning OFF, prompt sha256 `f1f2eddead735a10…` (2093 tokens), 128 greedy
`ignore_eos`, 3 gens (1 warmup + 2 scored), 100 Hz util sampling, ac-pinned.

**Progress at abort.** 37/80 cells completed (all `ok=True`); A1 at block 4 had not
started (no incomplete block to discard). Per-cell counts:
A0a=4, A0b=5, A1=4, A2=4, A3=5, A4=5, A5=5, A6=5.
Prefill sample counts across scored gens: min=13, median=19, max=78 (n=74).
Checkpoint: `derived/mslice/affinity_matrix.partial.json` (+ interrupted twin).

**Abort.** Harness STOP at 14:31 local: `ac_lost_mid_matrix` before cell A1 of block 4.
`battery_pct` reported 100→99 with `charging=False`, `power_online=False`. Confirmed still
on battery 10+ minutes later (SoC 99→97). Did **not** resume on battery. Did **not**
adopt. Did **not** analyze partial matrix for confinement verdicts.

**Disposition.** Parts 3–5 blocked. Resume only after AC restored + charging-complete
quiesce, via `--resume` on the same seed/cooldown/schedule (protocol continuation, not
salvage). Instrumentation citation remains
`run_id=fc262806-debf-4905-828b-2b8061dc0333`. Invalid matrix `d02a14cb…` still not
adopted from.

**Spend.** $0.00.

---

## STOP — affinity matrix resume blocked: still on battery (2026-08-03 ~14:46 local)

**Pre/post data:** PRE-DATA w.r.t. adoption. No measurement attempted.

**Power check (harness).** on_battery=true, charging=false, SoC **97%**.
BatteryStatus WMI: PowerOnline=false, Discharging=true, ChargeRate=0,
DischargeRate=19437 mW. is_charging_complete returns true via charging_false,
but **settled ac-pinned resume requires AC connected** — gate fails.

**Disposition.** STOP waiting for AC. Checkpoint
derived/mslice/affinity_matrix.partial.json (37/80) left untouched. Marker:
derived/mslice/affinity_matrix_resume_waiting_ac.json. Did **not** resume,
analyze, or measure on battery. Part 1 / c262806 not re-touched.

**Spend.** \.00.


---

## FINDING — AC 8x10 affinity matrix sealed; dual-phase UNCLEAR; mechanism not adopted (2026-08-03)

**Pre/post data:** PRE-DATA w.r.t. adoption. Sealed matrix exists; adoption gate failed (no CONFINED candidate).

### Recovery / resume chain

Prior sole --resume was killed by mistaken "duplicate" cleanup (Windows .venv-seam re-execs into a system/venv python child — one runner, not two). Checkpoint at 75/80 (interrupted mid block 10 A0a) parsed OK. Exactly one official --resume after AC settled (charging=false, SoC 100%). Incomplete block discarded by harness skip logic; five remaining cells of block 10 re-run. Log: derived/mslice/affinity_matrix_run_resume2.log.

### Run parameters

- Command: .\.venv-seam\Scripts\python.exe -u -m seam.tools.affinity_matrix --blocks 10 --seed 20260803 --cooldown-s 120 --out derived/mslice/affinity_matrix.json --allow-dirty --resume
- Workload: Qwen3-4B-int4-ov; reasoning OFF; prompt_sha256 1f2eddead735a108a9d6b4a083a7696d1d27ff1de303d7635aa9af8e8ac91fa; 128 greedy ignore_eos; 3 gens (1 warmup + 2 scored); 100 Hz util sampling; ac-pinned
- OpenVINO 2026.2.1 / GenAI 2026.2.1.0
- Exit code 1 is harness convention when dopted_mechanism=none (not a crash)

### Citing artifact (sealed)

| Field | Value |
|---|---|
| run_id | 5eb09eba-b321-4b7e-b7df-e9b01194d388 |
| sealed | 
aw/5eb09eba-b321-4b7e-b7df-e9b01194d388/ (manifest + affinity_matrix.json + summary.json) |
| derived | derived/mslice/affinity_matrix.json |
| SHA-256 | 63d525b8e7300be20ff54925bd2409c1b5463971e14731be94fea0966de5af00 |
| bytes | 701505 |
| resumed_from | derived/mslice/affinity_matrix.partial.json |
| n_ok | 10/10 blocks x 8 configs |

Invalid prior TTFT=0 matrix d02a14cb… remains not adopted from.

### Quiesce

| Field | Value |
|---|---|
| pinned_profile | ac-pinned |
| on_battery | false |
| charging | false |
| charging_complete | true |
| battery_pct | 100.0 (start=end) |
| power plan | Best Performance |
| display_brightness | 50.0 (target 50) |
| defender_realtime | enabled |
| thermal.regime | confound |

### Verification gates

pass=true, failures=[]. Prefill windows OK. A0a saturation demoted to diagnostic-only (loaded_core_count=4). Min phase samples >=10. Charging complete throughout.

### Two-pass LOADED thresholds (A5/A6 decode deltas)

Formula: 	hreshold(c) = 0.5 * delta(c) — P-cores from A5 decode; LP-E from A6 decode. Applied to every cell, both phases (never during collection).

| Core | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| threshold | 42.706 | 44.009 | 44.617 | 40.643 | 43.503 | 43.720 | 44.369 | 43.946 |

NOISE_BAND = 2 * mean(per-core CV of pooled idle baseline means) = **1.1792** (pooled n=160 baseline means per core).

### Prefill mean delta % (10-block; baseline-subtracted)

CPU order: 0,1,2,3 (P) | 4,5,6,7 (LP-E). L=LOADED, Q=QUIET, A=AMBIGUOUS.

| Cell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | states | pref. verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| A0a | 68.09 | 69.89 | 68.48 | 60.61 | 11.69 | 10.75 | 9.34 | 13.41 | L L L L A A A A | N/A |
| A0b | 67.17 | 71.18 | 69.35 | 64.24 | 9.29 | 8.63 | 8.97 | 8.96 | L L L L A A A A | N/A |
| A1 | 71.40 | 72.65 | 72.89 | 68.90 | 6.88 | 7.15 | 6.90 | 5.90 | L L L L A A A A | UNCLEAR |
| A2 | 78.91 | 68.53 | 68.69 | 62.06 | 6.29 | 8.20 | 4.97 | 6.55 | L L L L A A A A | UNCLEAR |
| A3 | 6.35 | 4.17 | 4.50 | 8.03 | 81.56 | 82.29 | 83.38 | 82.42 | A A A A L L L L | UNCLEAR |
| A4 | 2.75 | 2.51 | -0.38 | 2.97 | 82.51 | 75.84 | 77.06 | 75.37 | A A Q A L L L L | UNCLEAR |
| A5 | 71.49 | 76.42 | 78.71 | 70.44 | 5.14 | 3.30 | 1.80 | 1.18 | L L L L A A A A | UNCLEAR |
| A6 | 1.74 | 1.35 | 0.17 | 4.33 | 77.75 | 78.35 | 80.35 | 81.09 | A A Q A L L L L | UNCLEAR |

### Decode mean delta % (10-block; baseline-subtracted)

| Cell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | states | decode verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| A0a | 81.07 | 82.33 | 83.03 | 73.29 | 7.88 | 7.05 | 8.09 | 7.27 | L L L L A A A A | N/A |
| A0b | 87.12 | 88.70 | 89.69 | 80.73 | 6.01 | 6.53 | 6.60 | 5.18 | L L L L A A A A | N/A |
| A1 | 88.48 | 89.53 | 90.63 | 83.46 | 4.06 | 3.66 | 4.06 | 2.74 | L L L L A A A A | UNCLEAR |
| A2 | 90.46 | 84.12 | 85.40 | 77.54 | 4.52 | 3.60 | 5.05 | 4.04 | L L L L A A A A | UNCLEAR |
| A3 | 2.07 | 1.66 | 1.15 | 3.97 | 88.35 | 88.18 | 88.75 | 87.82 | A A Q A L L L L | UNCLEAR |
| A4 | 1.52 | 1.03 | 0.54 | 1.68 | 91.98 | 83.90 | 85.59 | 82.99 | A Q Q A L L L L | UNCLEAR |
| A5 | 85.41 | 88.02 | 89.23 | 81.29 | 3.99 | 3.19 | 3.34 | 3.89 | L L L L A A A A | UNCLEAR |
| A6 | 3.27 | 2.52 | 2.56 | 6.57 | 87.01 | 87.44 | 88.74 | 87.89 | A A A A L L L L | UNCLEAR |

Overall cell verdict = UNCLEAR for A1–A6 (neither phase clears QUIET on excluded cores). Included-cluster LOADED holds for deliberate targets.

### Throughput (10-block means; bootstrap CI on block means)

| Cell | pref mean | CI lo | CI hi | dec mean | CI lo | CI hi |
|---|---:|---:|---:|---:|---:|---:|
| A0a | 6488.07 | 5802.49 | 7114.68 | 11.754 | 11.297 | 12.237 |
| A0b | 8244.31 | 7573.86 | 8837.81 | 15.825 | 15.049 | 16.613 |
| A1 | 8412.82 | 8051.14 | 8758.16 | 16.294 | 15.485 | 16.981 |
| A2 | 8391.18 | 7670.20 | 9080.84 | 15.662 | 14.788 | 16.502 |
| A3 | 4189.83 | 3785.11 | 4566.52 | 8.611 | 8.144 | 9.045 |
| A4 | 4376.30 | 4126.92 | 4617.12 | 8.600 | 8.040 | 9.115 |
| A5 | 8633.82 | 7917.74 | 9359.68 | 15.801 | 15.133 | 16.425 |
| A6 | 4410.25 | 4145.75 | 4639.21 | 8.401 | 8.032 | 8.772 |

A0a vs A0b decode: oversubscription cost on the same four P-cores OpenVINO selects by default (11.75 vs 15.83 tok/s).

### A2 verdict — inconclusive

A1 and A2 both UNCLEAR in prefill and decode. Label **inconclusive**. Upstream draft remains HOLD — do not submit.

### A3-vs-A6 (decode tok/s)

- A3 mean 8.611 vs A6 mean 8.401; ratio A3/A6 = 1.025; relative delta = 0.025
- within-cell CV: A3=0.1028, A6=0.0879; material threshold 2xCV = 0.2056
- **material = false**. Symmetry remains required on isolation-invariant grounds.

### Throttle detectors

1. **PDH frequency:** n_min_pct_observations=1280; global_min_pct_of_max=**19.0** → flagged requency_dip_below_80pct_of_max
2. **Within-cell decode drift:** 80 pairs; **8** flagged |g2-g1|/g1 > 15%
3. **Block-position regression:** slope_decode_tok_s_per_block = **-0.068** (mild; not a collapsing thermal signature)
- excluded_cells: [] (flags recorded; no operator exclusion)
- Cooldown remains time-based / unvalidated (	hermal.regime=confound)

### Adoption decision tree — STOP

1. Zero mechanisms CONFINED in **both** prefill and decode → dopted_mechanism: none
2. Reason: outside-cluster residual util is AMBIGUOUS (above NOISE_BAND, below per-core LOADED threshold), so QUIET never clears on excluded cores
3. **Not written** as adopted into configs/mslice.yaml / configs/project_state.yaml confinement fields (dopted_mechanism / citing_run_id remain null)
4. Config notes + yield-queue blocker updated to cite 
un_id=5eb09eba-… / sha256 63d525b8…
5. Phase D **not started** (blocked on adoption)
6. Upstream draft updated to cite this sealed run; **no upstream submit**

### Decision recorded by harness

`
adopted mechanism: none
reason: Zero mechanisms confined BOTH clusters in BOTH prefill and decode. STOP.
verification_gates: pass=true
run_id=5eb09eba-b321-4b7e-b7df-e9b01194d388
`

### Spend

.00 (local only; unpaid).

---

## FINDING — E-FILTER Stage 1 sealed; filter operates in a 0.77 s band above a constant decode floor; throughput detector proven blind (2026-08-03)

Track: **E-FILTER** (docs/EXPERIMENT_escalation_filter.md, Stage 1; CS-01 / CS-19). Written to this
track only. Nothing here amends a hypothesis, threshold or prediction — those are frozen and are
the human's to change.

**Pre/post data:** POST-DATA. Two sealed runs exist. The pre-registered predictions were frozen
before collection; the verdicts below are as computed by the analysis, not as chosen after seeing
them.

### What was built

| Component | Purpose |
|---|---|
| `StepRecord` extension | `prompt_tokens_proxy`, `context_tokens_total`, `prompt_tokens_new`, `cache_instrumented`, `cache_evicted`, `evicted_bytes`, `kv_bytes_per_token`, `kv_bytes_resident_before`, `kv_bytes_resident`, `peak_rss_bytes`, `rss_bytes_end`, `t_pred_prefill/decode/total_s`, `ttft_ns` |
| `seam/kvmath.py` | Analytic KV constant, device-readback of KV precision |
| `seam/telemetry/rss.py` | Per-step process RSS high-water sampler |
| `seam/agent/steplog.py` | NDJSON writer/reader, `allow_nan=False` both directions |
| `seam/backends/refusing_cloud.py` | Raises `EscalationRefusedError` — deliberately **not** a `BackendError`, which the harness would absorb as a transient cloud failure and silently fall back to local |
| `policy.DEADLINE_DISABLED_S` = 1e9 | Finite sentinel; `float('inf')` refused because `json.dumps` emits bare `Infinity` |
| `policy.assert_escalation_disabled` | Per-step readback of the sentinel and its headroom |
| `seam/analysis/efilter.py` | Offline counterfactual replay, envelope curve, bootstrap, proxy regression, figure |

Arm L required **no new routing code path**: the sentinel deadline keeps every step local through
exactly the harness a hybrid run uses. The replay **imports** `policy.decide` rather than
reimplementing it (`rule_source` records this), so the counterfactual is evaluated by the same rule
the run applied.

### Citing artifacts (sealed)

| Field | Pilot | Full |
|---|---|---|
| run_id | d8f0875b-dfc5-473f-8260-8c8827d18295 | 1a0166b9-cbaf-43f4-8d76-bcd7c01841e0 |
| workload.kind | efilter_pilot | efilter_stage1 |
| tasks / steps | 3 / 12 | 20 / 51 |
| success rate | 0.667 | 0.950 |
| wall | 236.9 s | 1812.4 s |
| integrity_verified | — | true |

Derived: `derived/efilter/envelope_vs_deadline.json` + `.png`, `full_report.json`,
`pilot_report.json`. Analysis reads sealed `raw/` only; nothing under `raw/` was modified.

### Quiesce (both runs, recorded by value and read back)

| Field | Value |
|---|---|
| on_battery | false |
| charging / charging_complete | false / true |
| battery_pct | 100.0 (start = end) |
| power plan | Best Performance |
| display_brightness | 50.0 |
| defender_realtime | enabled |
| package_temp_c | null — `MSAcpi_ThermalZoneTemperature` returns "Not supported" (evidence recorded in manifest) |
| thermal.regime | confound |
| deviations | [] |
| cloud credential present | false, by direct `os.environ` read (`load_dotenv` deliberately **not** called, since calling it would load the credential the check exists to rule out) |

`charging_complete` is qualified locally as `is_charging_complete() AND on_battery is False`: the
shared helper returns True for `charging is False`, which is also true of a **discharging** machine.
Its other callers gate AC separately, so the helper is right for them and would have been misleading
recorded raw in an E-FILTER manifest.

### Escalation disabled — verified, not asserted

| Field | Pilot | Full |
|---|---|---|
| deadline_s | 1e9 (finite sentinel) | 1e9 |
| max observed t_pred | 3.403 s | 14.096 s |
| headroom factor | 2.94e8 | 7.09e7 |
| escalated steps / cloud attempts | 0 / 0 | 0 / 0 |

`replay_self_check`: 51/51 steps reproduce their logged decision and `t_pred` at `rel_tol=1e-9`, and
the logged prefill/decode terms sum to the logged total. Zero mismatches.

### Cache instrumentation — NOT instrumented, and no reuse observed

`cache_instrumented = false`. OpenVINO GenAI's `LLMPipeline` exposes no `cache_read` /
`cache_creation` counters, so `cached_prompt_tokens` is a **structural zero, not a measurement**. The
guard therefore fires: every metric derived from `prompt_tokens_new` is labelled an **upper bound**,
and the §6 caching fork is recorded as `UNDETERMINED_FROM_COUNTERS`.

An independent behavioural probe was run instead. **The two runs used different probe designs and
their results must not be quoted interchangeably:**

| | Pilot (d8f0875b) | Full (1a0166b9) |
|---|---|---|
| design | 2 calls: first, byte-identical repeat | 3 calls: first, byte-identical repeat, length-matched **distinct** control |
| prompt_tokens | 655, 655 | 655, 655, 654 |
| ttft (s) | — | 0.47226, 0.80658, 2.47228 |
| ttft(repeat)/ttft(first) | **0.9936** | **1.7079** |
| ttft(repeat)/ttft(control) | — | **0.3262** |
| criterion | ratio < 0.5 | ratio < 0.5 against **both** first and control |
| reuse_observed | false | false (fails on the first term) |

`fraction_steps_cache_evicted` = 0.608, inferred and an upper bound by construction.

**The full run's probe is internally inconsistent and underpowered, and is recorded as such.** The
byte-identical repeat was *slower* than the first call (1.71x), which is incompatible with reuse; but
it was 3x *faster* than a distinct prompt of the same length (0.33x), which is the signature of
reuse. With n = 1 per condition and a 0.47-2.47 s spread across same-length prompts, TTFT noise
exceeds the effect the probe is trying to resolve. The pilot's cleaner 2-call probe (0.9936, i.e. no
difference) is the better behavioural evidence, and the **structural** fact is independent of both
probes: the runtime exposes no counter, so the fork cannot be settled from this run either way.

`peak_kv_bytes_resident` — the primary endpoint — is analytic from `context_tokens_total` and the KV
constant, and is **independent of the cache counter**, which is why the primary endpoint survives the
instrumentation gap.

KV geometry, read back from the device rather than assumed: `2 * 36 layers * 8 kv_heads * 128
head_dim * 1 byte` = **73,728 bytes/token**, `kv_dtype=u8` via `device_readback` (the config's
assumed `f16` was **not** used; had it been, every KV figure would be 2x too large).

### Proxy error — bias 77%, boundary reported as an interval

The router prices a step before it renders, so it consumes a `chars // 4` transcript proxy, not the
tokenizer. Regression of native on proxy across all 51 steps:

| Quantity | Value |
|---|---|
| model | `native ~ a + b * proxy` |
| slope | 0.9594 |
| intercept | 637.13 tokens |
| R² | 0.9983 |
| residual SD / max abs | 11.93 / 48.53 tokens |
| mean relative bias (proxy-native)/native | **-0.7737** |
| threshold | 0.15 |

The proxy is almost perfectly **linear** in the true count but badly **scaled**: it recovers 25% of
the true token count (mean 252 vs 879). Bias far exceeds 0.15, so per the guard the filter boundary
is reported as an **interval** between the proxy-driven and tokenizer-driven replays, not a line.

### The envelope curve — the deliverable

Full run, D grid log-spaced over the observed t_pred distribution (40 points, 10.67-17.62 s).
`over_provisioning(D) = envelope_unfiltered / envelope_filtered(D)`, paired bootstrap over the 20
tasks (10,000 resamples). Every figure is a mean of per-task peaks with a CI; no single max is
reported as a headline, and P95 of per-step context is carried as the stable companion.

| D (s) | escalation | surviving steps | OP peak KV | 95% CI | material (>=1.2x) | OP peak context |
|---:|---:|---:|---:|---|---|---:|
| <= 13.279 | 100% | 0 | — | — | — | — |
| **13.451** | **51.0%** | 25 | **1.243** | **1.115 - 1.409** | **true** | 1.377 |
| 13.625 | 13.7% | 44 | 1.060 | 1.000 - 1.153 | false | 1.087 |
| 13.802 | 9.8% | 46 | 1.043 | 1.000 - 1.102 | false | 1.067 |
| 13.980 | 5.9% | 48 | 1.026 | 1.000 - 1.060 | false | 1.027 |
| >= 14.161 | 0% | 51 | 1.000 | 1.000 - 1.000 | false | 1.000 |

**The entire filter lives in a 0.77 s band.** `t_pred = prompt_tokens_proxy / 1601.5 + n_out_pred /
10.651`. The decode term is a **constant per step type** — 142 / 10.651 = **13.332 s** for
`tool_call_synthesis` — and prefill contributes only 0.001-0.054 of `t_pred` at the observed context
lengths. So `t_pred` spans [13.33, 14.10] s: below the floor everything escalates, above the ceiling
nothing does. Prefill would not dominate until **21,352** context tokens for `tool_call_synthesis`;
observed peak is **1,826**. The context-selective regime §6 describes is never entered.

Proxy-vs-native interval on the boundary: the tokenizer-driven replay puts the material point at
**D = 13.802 s, OP = 1.314**; the proxy-driven replay puts it at **D = 13.451 s, OP = 1.243**. The
boundary is the interval **[13.451, 13.802] s**, over-provisioning **1.24x - 1.31x**.

### Pre-registered predictions — as computed

| | Verdict | Basis |
|---|---|---|
| P1 | UNDETERMINED at the headline D | at D = 8 s no task retains a surviving step, so no paired ratio exists. **The curve's maximum KV over-provisioning is 1.243x (CI 1.115-1.409) at D = 13.451 s**, above the 1.2x line but with a CI straddling it |
| P2 | UNDETERMINED | premise not satisfiable — see below |
| P3 | UNDETERMINED | no paired arithmetic-intensity ratio at the headline D |
| P4 | PARTIAL | prefill share of t_pred rises monotonically with step_idx (0.105% -> 5.42%, slope +0.0072/step), so the **basis** of selection does shift toward context; but escalation-rate slope vs step_idx is 0.0, so the shift never changes **what is filtered** |
| P5 | out of scope | requires Stage 2 |

**P2's premise is not satisfiable on this workload.** No deadline on the grid delivers p95 realized
step latency <= 8 s: the best achievable is p95 = 21.41 s at D = 13.451 s (unfiltered p95 = 23.52 s).
Escalation triggers on *predicted* latency, and the predictor's output-length term is a per-step-type
median, so the filter does not order steps by realized latency. This is a finding about the
escalation mechanism, reported as one rather than worked around.

**P1's deadline is unspecified in the pre-registration.** Evaluating it at the headline D (where the
premise fails) yields UNDETERMINED; evaluating it as "at some deadline on the grid" yields a material
1.243x. That choice changes a pre-registered verdict and is **flagged for the human**, not resolved
here.

### FINDING — the same machine ran 1.98x slower in the full run than in the pilot

Identical config, identical prompt, 23 minutes apart, both quiesce-clean at AC / 100% / charging
complete:

| | Pilot (d8f0875b) | Full (1a0166b9) | ratio |
|---|---:|---:|---:|
| R_prefill tok/s | 3174.55 | 1601.50 | 1.983 |
| R_decode tok/s | 21.21 | 10.651 | 1.992 |
| steady-state wall / warmup gen | ~5.4 s | ~10.8 s | 2.00 |
| warmup prefill CV | 0.194 | 0.036 | — |

Both are **stable plateaus**, not noise: the full run held 10.6-10.8 tok/s across 8 scored warmup
generations at CV 0.036. A uniform ~2x on *both* phases points at a clock/power operating point, not
at contention on one phase.

This is first-order for the result: throughput sets the entire deadline grid. At the pilot's
21.21 tok/s the decode floor would be 142 / 21.21 = **6.70 s**, and the 8 s target — infeasible above
— **would have been satisfiable**. P2's feasibility verdict therefore depends on an uncontrolled
variable. Cause undetermined; `thermal.regime = confound` is declared for exactly this reason, and
no temperature source exists on this platform to test it.

### FINDING — PDH frequency throttle detection is blind on this platform

Frequency-based throttle detection was authorized 2026-08-02 as the substitute for the unavailable
package temperature. Measured directly today:

| Condition | per-CPU MHz | % of Maximum Frequency | measured util |
|---|---|---|---|
| idle | [2100 x4, 1600 x4] | 100.0 (all) | LP-E ~20-35% |
| 4-process CPU burn | [2100 x4, 1600 x4] | 100.0 (all) | 100% on all 8 |

`\Processor Information(*)\Processor Frequency` returns **fixed nominal values** — exactly 2100.0 on
the P-cores and 1600.0 on the LP-E cores, zero variance, unchanged between idle and saturation — and
`% of Maximum Frequency` is pinned at 100.0 in both. (mslice's matrix did observe dips to 19%, which
appear to track parked/deep-idle cores rather than throttling of an active one.) The counter cannot
detect a sustained throughput reduction of an *active* core: both E-FILTER runs report 100% of max on
all 8 CPUs while differing 1.98x in delivered throughput.

Consequence: detector (a) of the three authorized throttle detectors is **inert on Platform A**.
Detectors (b) within-cell drift and (c) block-position regression are within-run and did not fire —
the 2x shift is *between* runs. Anything relying on frequency-based throttle detection should be
re-read in this light; that includes other tracks, whose sections are not edited here.

Secondary defect: `FrequencySampler.summary()` **samples** `mhz_per_cpu` and then discards it,
retaining only the percentage. The 2026-08-02 authorization named both counters. The MHz series for
both sealed runs is unrecoverable (sealed runs are write-once and were not modified).

### FINDING — quiesce verifies a process-name allowlist, not measured idle

`quiesce.forbidden_processes` lists four specific module names. It does **not** measure CPU load. At
19:58:46, 17 s after E-FILTER collection ended, `seam.bench.attrib runtime-pilot` (another track)
started and held 314% CPU / 3.85 GB RSS on the P-cores. It did not overlap this run, but nothing in
the gate would have detected it if it had: the run would have recorded "deviations: []" while sharing
the four P-cores OpenVINO selects by default. Not fixed here (it would change a gate mid-track);
recorded as a defect in the quiescence check.

### Limitations recorded with the result

1. **Capacity regime not reached.** Context grows monotonically and linearly (~164 tokens/step, 655
   -> 1826, ratio 2.79, no plateau) but is truncated by `max_steps = 8`. Peak KV is ~135 MB, ~1% of
   the 12.5 GB budget. The §9 gate as written ("if context plateaus early") passes, but the memory
   claim is being evaluated far from the regime it concerns. Changing `max_steps` or the task set is
   the human's call.
2. **`step_type` is hardcoded.** The router priced all 51 steps as `tool_call_synthesis`; the harness
   rewrites the label to `answer_synthesis` **after** the routing decision (realized counts 32/19).
   The replay uses `routing.step_type` — the label the router actually consumed — because using the
   realized label would reprice every terminal step and the counterfactual would silently differ from
   the rule the run applied. Taxonomy **not** expanded (that is its own amendment). Stratified by
   `step_idx` instead, per AM-025.
3. **`p95_required_decode_rate_tok_s` in the top-level `unfiltered_envelope` block is degenerate by
   construction** (~1.9e-7 tok/s): that block is computed at `DEADLINE_DISABLED_S`, so the required
   rate is ~0. Within each curve point the unfiltered side is recomputed at the same D as the filtered
   side, so the ratios are sound; the top-level figure is not a quantity to quote.
4. **n = 20 tasks / 51 steps.** Only 2 tasks exceeded 3 steps, so the deep-context strata rest on
   n = 1-2.

### Verification

429 tests pass. ruff and mypy clean on all E-FILTER modules; the 7 ruff and 5 mypy errors remaining
in the repo are all in `seam/tools/phase_e_cloud.py` (Phase E track, untouched here).

### Spend

$0.00 (local only; unpaid). No cloud call was made; no credential was loaded.

---

## C2b — context-ratio gate + memory fixes (2026-08-04) — PRE-DATA w.r.t. re-pilot

Track: `agent`. Attrib frozen. Spec in force: `docs/CURSOR_PROMPT_C2b.md`.

### Already landed (verified, not re-done)

- **AM-032** present and RESOLVED: 8 s headline withdrawn; `configs/efilter.yaml`
  `p95_step_target_s: null` / `p95_step_target_status: withdrawn_AM-032`.
- **Router proxy** `chars // 4 + 621` scaffold already in config and harness
  (`prompt_token_source: chars_div_4_plus_scaffold`).

### C2b implementation (this session)

- Replaced pilot **20k peak** gate with median per-task **`C_max/C_min ≥ 3.0`**
  (`max/min` of `context_tokens_by_step`); absolute peak reported only.
- `workload.context_cap_tokens: 7000` → harness terminates with `terminated_reason=context_cap`.
- `max_tokens: 128`; constrained tool-call decoding via OpenVINO GenAI
  `StructuredOutputConfig.Tag("<tool_call>", JSONSchema(...), "</tool_call>")`.
- `n_out_pred` held **constant across step types**; freeze from measured median after re-pilot.
- Analysis reports `context_ceiling` alongside over-provisioning; P6 falsifies if OP lands in
  Stage-1 CI `[1.115, 1.409]` despite much higher ceiling (baseline run_id `1a0166b9…`).
- C9 note: `derived/efilter/c9_practical_ceiling_note.json` citing
  `0fe5e4c7-bb38-4666-826b-2c512b17a969` (partial; not mutated).

### Launch (not executed by the agent)

Detached: `tools/launch_efilter_c2_pilot.ps1` (5 tasks) and `tools/launch_efilter_c2_full.ps1`.

## 2026-08-10 — AF-036 — Promote-time power_state leaked into retro-sealed ceiling_a manifests

**Class:** provenance / sealed metadata
**Found:** 2026-08-10
**Milestone:** Phase -1 / ceiling_a promote
**Blueprint reference:** §5.2 (run manifest); §6.3 (raw write-once); AMENDMENTS.md AM-036

### Found

`seam.manifest.emit()` accepts a `power_state` block that callers typically fill from
`capture_power_state()` at emit time. For runs sealed during measurement this is correct. For
retro-sealed / raw-promoted runs it records **promote-time** host state as if it were
**measurement-time** environment.

Three ceiling_a manifests promoted 2026-08-10T13:05Z from session `ad7b9288-…` (measured
2026-08-06 on AC) sealed with:

| run_id | role | sealed `power_state.on_battery` | sealed `battery_pct_start` |
|---|---|---|---|
| `b5ce21e5-9f29-46f4-8319-f74adcdeb628` | arm A | `true` | `88.0` |
| `64e525e7-37df-4a7a-91e5-21419acf5dd2` | arm A_prime | `true` | `88.0` |
| `404dc3d0-1760-41a8-b9c5-d0d439b1a1fe` | verdict | `true` | `88.0` |

Those values match the promote-time machine state, not the measurement day. Control
`693b44d2-8234-453c-bc8d-107a9ff259a0` (self-sealed during run) correctly records
`on_battery=false`, `battery_pct_start=100.0`. Delta-prefill promotes `d5c98342` /
`9f38eb15` already had null measurement power and are unaffected.

### Blast radius

Any reader of `raw/<run_id>/manifest.json` `power_state` for the three IDs would mis-attribute
battery vs AC for the measurement. **Measurements themselves are unaffected** — this is
provenance metadata only. `integrity.raw_sha256` covers data outputs excluding the manifest.

### Correction (protocol path; raw/ not mutated)

`seam.rawstore.RunDir` refuses writes and re-seal on sealed runs ("emit a NEW run and record
the supersession"). No prior sealed-metadata amend-in-place exists. Per AM-036:

1. Schema separates measurement `power_state` from optional `promote_time_power_state` and
   `power_state_note`; emit stamps `retro_seal` / `measurement_power_from_records`.
2. `emit(..., retro_seal=True)` refuses non-null measurement `power_state` unless
   `measurement_power_from_records=True`.
3. Retro-seal tools updated so they cannot reintroduce the leak.
4. `derived/manifest_corrections/registry.json` registers the three AF-036 digests as
   explicit amendments; `load_run_manifest` also applies a **structural** promote-time leak
   rule (retro_seal / summary `promotion: post_hoc*` + populated measurement power + absent
   `promote_time_power_state`) so future leaks do not require adding run_ids. Sealed tree
   hashes unchanged and still verify.

Sealed tree sha256 at correction time:

| run_id | `.sealed.raw_sha256` |
|---|---|
| b5ce21e5… | `6647a2fe589263ab0e8cd8362887752837529509590d1cce4383162ca37e560d` |
| 64e525e7… | `9d479c4c3aef09bb4aab9d7a9a15b089008e1461ae3b328822fe4b0b01c68381` |
| 404dc3d0… | `6cab6b79e5cd7571dea5bd09e49955b31c49fc986da01af82a8f4139ebe0cd30` |

### Blocker / dual-truth note

Direct reads of `raw/*/manifest.json` still show the leaked values until a future authorized
seal-marker supersession (not performed here). Analysis and MCP-style loaders must use
`load_run_manifest`. Do not backfill measurement power from memory.

---

## 2026-08-24 — PRE-DATA — Qwen3-8B-int4 gpu_only predictions frozen (M1–M6)

**Class:** pre-registration (AM-015)  
**Found:** 2026-08-24, before any Qwen3-8B-int4 transfer, load, or generate  
**Milestone:** model capability rung (blueprint §2.1); not a named M0–M6 instrument milestone  
**Blueprint reference:** §1.2 additive filter; §2.1 workload coordinate `model capability rung`; AM-015

### Frozen

Operator-stated predictions for **Qwen3-8B-int4 on `gpu_only`**, derived from Qwen3-4B-int4
constants attributed to session `41e419bd-f3e9-43b1-8364-0ebd89fa086b`
(intercept 3.08 GB, f16 slope 234,827 B/tok, decode 19.85 tok/s).

Write-once artifacts (do not edit after 8B measurement starts):

| path | role |
|---|---|
| `derived/qwen3_8b/PREDICTION_BEFORE_RUN.md` | human freeze |
| `derived/qwen3_8b/predictions.json` | machine freeze |

`PREDICTION_BEFORE_RUN.md` sha256
`af593d4f7aac0a7c4e2a19c3b389df5b309400a0b9a5d1740df9a3de2a9e2891` (3060 bytes).

| id | claim | falsifier | this gate |
|---|---|---|---|
| M1 | loads at n=2000 without `CL_OUT_OF_RESOURCES` | load or first generate fails | yes |
| M2 | peak_ws intercept 4.8–6.0 GB | outside band | yes |
| M3 | TTFT n=5000 f16 in 4–7 s (USER_FACING 10 s) | >10 s or <3 s | yes |
| M4 | decode 8–12 tok/s (floor 6 tok/s) | <6 tok/s | yes |
| M5 | f16 resident slope within 10% of 234,827 B/tok | outside 10% (voids capacity extrapolations) | yes |
| M6 | cpu-p does not fit at n=12000 | — | **no** (recorded for later) |

**Filter:** additive (capability rung). Not a §12.4 displacing arm.

**Pre/post data:** PRE-DATA. No 8B IR, load, or generate has been started in this session.
A criterion written after seeing 8B numbers is not a substitute for this freeze.

