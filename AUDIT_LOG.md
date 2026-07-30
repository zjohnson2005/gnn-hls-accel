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
