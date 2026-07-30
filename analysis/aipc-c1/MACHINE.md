# MACHINE.md — C1 interference characterization host

**Recorded:** 2026-07-28  
**Provenance note:** Values below were read on this date from `systeminfo`, CIM/WMI, `pnputil`, and `powercfg`. Re-verify drivers before quoting results if Windows Update runs.

## Identity

| Field | Value |
|-------|-------|
| Chassis | Dell XPS 16 DA16260 |
| Manufacturer | Dell Inc. |
| CPU | Intel(R) Core(TM) Ultra 5 325 (**Panther Lake**) |
| Logical processors used for CPU backend | 8 (all) |
| Hostname | computadora |

> **Corrected 2026-07-29 — audit finding AF-001.** This row previously read "(Lunar Lake)."
> The part is **Panther Lake**. See [Platform identification evidence](#platform-identification-evidence-af-001)
> below for the discriminating evidence and for which parts of it are load-bearing.

## Memory (UMA)

| Field | Value |
|-------|-------|
| Total RAM | 16 GB (reported 15,976 MB) |
| Topology (CIM) | 8 × 2 GiB soldered (`DeviceLocator=Motherboard`) |
| SPD Speed field | 9600 (MT/s class; LPDDR5X-9600 reporting) |
| ConfiguredClockSpeed (CIM) | 7467 |
| Channel config | On-package LPDDR5X (**Panther Lake** memory-side cache / UMA); treat as multi-channel SoC DRAM, not discrete DIMMs |
| Part number / vendor via CIM | **null** (soldered; not exposed) |

Exact JEDEC channel count is not visible via `Win32_PhysicalMemory` on this SKU; do not invent a dual/quad-channel label beyond the 8×2 GiB CIM banks.

## Platform identification evidence (AF-001)

Recorded 2026-07-29 as part of the AF-001 correction. This section exists so the platform
identification is **auditable rather than asserted**: MACHINE.md is the provenance source for
the `platform` block of every run manifest (blueprint §5.2), so a wrong identity here
propagates into every number the project produces.

Evidence is split by whether it is **independently attested by a committed probe artifact** or
**inferred by a human during identification**. Inferred evidence cannot corroborate the
conclusion it was derived from.

### Load-bearing evidence (probe-attested, independent)

| # | Discriminator | Panther Lake | Lunar Lake would be | Source artifact | Verbatim |
|---|---|---|---|---|---|
| E1 | **SKU number.** `Core Ultra 5 325` is a 3xx part → Core Ultra Series 3 → Panther Lake | `3xx` | `2xxV` (e.g. Core Ultra 5 228V) | `analysis/_c1_machine_probe.txt` line 17 | `Intel(R) Core(TM) Ultra 5 325` |
| E2 | **Graphics PCI device ID.** `DEV_B090` is in the Xe3 range | `B090` | `64A0` (Xe2) | `analysis/_c1_drivers_probe.txt` line 4 | `PCI\VEN_8086&DEV_B090&SUBSYS_0DBA1028&REV_00\3&11583659&0&10` |

**E1 and E2 alone are sufficient and are mutually independent** — one is a CPU brand string
from `systeminfo`/CIM, the other is a PCI enumeration from `pnputil`. They come from different
subsystems and agree. The identification rests on these two rows.

### NON-INDEPENDENT evidence (human inference — must not be cited as corroboration)

| # | Claim | Status | Why |
|---|---|---|---|
| E3 | Core names **Cougar Cove** (P) / **Darkmont** (LP-E) — Lunar Lake is Lion Cove / Skymont | **INFERRED — NOT probe-reported** | The strings `Cougar`, `Darkmont`, `Lion Cove`, and `Skymont` appear in **none** of `_c1_probe.txt`, `_c1_machine_probe.txt`, `_c1_drivers_probe.txt`, `_c1_mem_probe.txt`, `_c1_tools_probe.txt`. Windows exposes no microarchitecture code-name field. These names were supplied from vendor documentation *after* concluding "Panther Lake" from E1. Citing them as evidence **for** Panther Lake is circular. |
| E4 | iGPU is **Xe3** | **INFERRED** from E2 | `Xe3` appears in no probe artifact. It is a vendor mapping of DID `B090`. E2 (the raw DID) is the evidence; "Xe3" is its interpretation. |
| E5 | `Panther Lake` as a literal string | **INFERRED** | Appears in no probe artifact. It is the conclusion, not an input. |

### Explicitly NON-DISCRIMINATING (does not distinguish the two candidates)

**The 4 P-core + 4 LP-E-core, 8C/8T, no-SMT topology does NOT discriminate Panther Lake from
Lunar Lake.** Lunar Lake has the identical signature: 4 Lion Cove P-cores + 4 Skymont LP-E
cores, 8C/8T, no SMT. Any argument of the form "it has 4+4/8T, therefore Panther Lake" is
**invalid** and must not appear in a manifest, figure caption, or paper.

Note further that the 4+4 split is itself **not attested by any committed probe artifact** —
no artifact records core counts, `EfficiencyClass`, or a P/LP-E partition. `MACHINE.md` line 13
("Logical processors used for CPU backend | 8 (all)") is a *harness configuration choice*, not a
topology measurement. The P/LP-E mapping is therefore **unverified as of this correction** and is
verified empirically by `seam/topology.py` (spec §4 / M1), which writes the measured mapping to
`configs/platforms/aipc-c1.yaml`.

### Provenance gaps found while auditing (recorded, not fixed here)

These are `analysis/` artifacts and are read-only under spec §9.1; they are recorded for the
audit trail rather than corrected.

1. **`_c1_mem_probe.txt` is effectively empty.** It contains only a `wmic` SPD header that
   returned no rows, plus an AC-status line. The memory table above (8 × 2 GiB banks,
   `ConfiguredClockSpeed=7467`, SPD field 9600) is therefore **not attested by any committed
   artifact** — it was read live on 2026-07-28 and transcribed. Re-capture under AF-002.
2. **`_c1_probe.txt` carries no hardware content** — three lines: a timestamp, the hostname,
   and `done`.
3. **Internal inconsistency in `_c1_machine_probe.txt`:** line 3 reports
   `Microsoft Windows 11 Home` while line 19 reports `Windows 10 Home 25H2 build 26200.8875`.
   The latter is the well-known stale registry `ProductName` value and is a reporting artifact,
   not a second OS. Recorded because blueprint AF-002 rests partly on "internal agreement
   across four artifacts," and that agreement is weaker than stated.
4. **No CPU microarchitecture, core-topology, microcode, or `EfficiencyClass` field is captured
   by any probe.** The manifest emitter must not claim these as probe-sourced.
5. **NPU model (`NPU 5` / `NPU 5010`) and its 50 TOPS figure are not probe-attested.** The
   drivers probe attests only `Device Description: Intel(R) NPU`, `Class Name:
   ComputeAccelerator`, and driver INF `oem127.inf`/`npu.inf`. 50 TOPS is a vendor **peak INT8**
   figure and must never be reported as achieved throughput.

## Display (foreground QoS context)

| Field | Value |
|-------|-------|
| Panel EDID instance | `DISPLAY\LGD07C7\...` |
| Active mode | 1920×1200 @ **120 Hz** (`Win32_VideoController.CurrentRefreshRate=120`) |
| Nominal frame interval | **8.333 ms** (not 16.7 ms; this is a 120 Hz laptop panel) |

## Firmware / OS

| Field | Value |
|-------|-------|
| BIOS | Dell Inc. **1.8.2** (reported 2026-05-22) |
| OS | Windows 11 Home 25H2 |
| Build | **26200.8875** |

## Drivers (compute)

| Device | INF / notes | Version |
|--------|-------------|---------|
| Intel(R) Graphics (iGPU) | `oem32.inf` ← `iigd_dch.inf` | **32.0.101.8622** (2026-02-19) |
| Intel(R) NPU | `oem127.inf` ← `npu.inf` (+ `oem66.inf` extension) | **32.0.100.4724** (2026-03-19) |

## Pinned run conditions (MANDATORY)

Sessions that violate these are **INVALID**, not noisy.

- **AC power:** required (`ACLineStatus=1`). Lid open. Same physical location.
- **Pinned power plan name:** `Best Performance`
- **Pinned power plan GUID:** `ec87a53a-19a6-4f4a-980f-ab27cc929b25`  
  (duplicated from Windows `SCHEME_MIN` / High performance `8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c`, then renamed; may be omitted from `powercfg /list` on this SKU — activate by GUID)
- **Assert script:** `analysis/aipc-c1/scripts/assert_power_pin.ps1` — abort if AC or plan differs.
- **Ambient:** log at run start when a sensor is available; otherwise record `ambient=unavailable` (no calibrated ambient logger on this box at Item 0).

### Item 0 snapshot (NOT a valid measurement session)

At tooling validation wall-clock (2026-07-28 ~16:55 local):

- AC: **OFFLINE** (`ACLineStatus=0`, battery ~88%)
- Active plan: **Balanced** `381b4222-f694-41f0-9685-ff5bb260df2e` (pinned plan exists but was **not** activated)

## Engines / binaries (paths as of Item 0)

| Engine | Binary / stack | Notes |
|--------|----------------|-------|
| CPU | `C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-bench.exe` | SHA256 `7F0A0303F5CEDA29B22BA4A17A8D17C8125ADBF298D179F27F4EA1A691354479`; source tree HEAD `91f8c9c5fb038c086e13e9cd823c29b33b07ba54` |
| iGPU | **TBD** after 30-min SYCL/Vulkan vs ipex-llm smoke (Item 0 did not select) | — |
| NPU | OpenVINO GenAI (`openvino_genai`) | **Not installed** in Python 3.11/3.14 at Item 0 |

## Power metering

- `Win32_PowerMeter` previously returned null on this box (July characterization) — do not rely on it.
- HWiNFO / Intel Power Gadget successor: **not validated** at Item 0.
- Sustained clock proxy that works: `% Processor Performance` via `Get-Counter` / elevated `typeperf`.
