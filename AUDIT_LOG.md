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
