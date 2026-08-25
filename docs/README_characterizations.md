# Hardware configuration characterizations

**What this answers:** on a 16 GB unified-memory consumer device, which hardware
configuration choices change what an agentic workload can execute locally, and by
how much?

Device: Dell XPS 16, Intel Core Ultra 5 325 (Panther Lake), 16 GB soldered
unified memory, 4 P-cores + 4 LP-E cores. Model: Qwen3-4B-int4-ov, OpenVINO
GenAI 2026.2.1, `max_position_embeddings` 40,960.

Four axes. Three characterized, one gated on a mechanism now resolved.

---

## Axis 1 — Device placement

`cpu-p` vs `cpu-p + igpu` vs `gpu_only`. NPU deferred by decision (its path
requires `NPUW_LLM_PREFILL_CHUNK_SIZE`, which bounds prefill activation memory by
construction, so that difference would sit inside any placement comparison at the
magnitude being detected).

Clean same-session reference at n = 12,000:

| | cpu-p | gpu_only (warm) |
|---|---|---|
| prefill | 227.95 s (CV 0.73%) | 13.59 s |
| decode | 6.240 tok/s | 19.85 tok/s |
| peak working set | 9.46–10.70 GB | 5.12 GB |

**16.8x prefill warm, 14.8x including the cold first turn, 3.18x decode.**
The iGPU carries a 40.6% warm-up penalty on turn 1 (19.11 s to 13.59 s), fully
amortised by turn 2 — a cost session residency removes.

## Axis 2 — Session residency

Whether session KV survives between turns. Measured across all 48
(arm x n_cached x delta) groups of the precision matrix:

**RESIDENT / NON_RESIDENT turn-2 ratios span 0.079 to 0.469. Retention holds in
every group.**

Combined with placement, on real BFCL multi-turn against the pre-registered SLO
(TTFT <= 10 s and decode >= 6 tok/s on user-facing turns):

| configuration | turns meeting SLO | session latency |
|---|---|---|
| cpu-p, no residency (default) | 0% | 9,630 s |
| cpu-p + residency | 72.9% | 1,888 s |
| gpu_only, no residency | 95.7% | 1,162 s |
| gpu_only + residency | **100%** | **544 s** |

The two axes interact **2.4x super-additively** on latency, from measured
medians rather than fits.

## Axis 3 — KV cache precision

`KV_CACHE_PRECISION` in f16 / u8 / u4, enforced by readback — a cell whose
readback disagrees with its request is failed, not measured.

288 cells: 3 arms x n_cached {2000, 4000, 8000, 12000} x delta {50, 150, 400,
1000} x {RESIDENT, NON_RESIDENT} x 3 repeats, Fisher-Yates interleaved, with a
canary every 12 cells whose drift threshold is derived in-run.

**Finding 1 — resident memory is a fixed workspace plus KV bytes, additive.**

| arm | measured B/token | nominal KV | residual |
|---|---|---|---|
| f16 | 234,827 | 147,456 | 87,371 |
| u8 | 171,532 | 73,728 | 97,804 |
| u4 | ~135,000 | 36,864 | ~98,100 |

The residual holds near 95 KB/token while the ratio to nominal swings 1.6x to
3.7x. Precision scales the KV term only; roughly 95 KB/token of workspace is
fixed. Any "amplification factor" expressed as a multiplier is an additive term
written as a ratio at one precision.

**Finding 2 — quantization costs prefill latency rather than saving it.**
At n >= 8,000 and delta = 1000, f16 is 15–27% *faster* than u8 and u4. Prefill is
compute-bound and precision-independent (turn-1 times agree within 1% across
arms); the quantized arms pay dequantization on top. Precision buys capacity, not
speed — the two trade against each other.

**Finding 3 — delta prefill is context-dominated, not delta-dominated.**
A purely delta-driven cost would give a d1000/d50 ratio of 20 at every context.
Observed: 0.74 at n = 2,000 rising to 3.0 at n = 12,000. The multiplicative form
`turn2 = C * d * n_cached` is falsified.

## Axis 4 — Attention window

Gated, and the gate passed. `SchedulerConfig.use_cache_eviction` plus
`CacheEvictionConfig` (`start_size` = attention sink, `recent_size` = sliding
window, `max_cache_size` = cap). No plugin-level `ATTENTION_SINK` or
`SLIDING_WINDOW` property exists on this build, so this is the only path.

**Zero cells measured.** The mechanism it was waiting on is now resolved: since
the ~95 KB/token workspace is additive and dtype-independent, the axis asks one
sharp question — does narrowing the window reduce that residual, or is it fixed?

Note a confound before measuring it: the eviction path runs through
`ContinuousBatchingPipeline`, while every timing cell to date uses plain
`LLMPipeline`. Enabling eviction changes the execution path, not just the window.
An equivalence probe (CB with eviction disabled against plain `LLMPipeline`) is
required before window results can be compared to the existing corpus.

---

## Open, and load-bearing

**No f16 ceiling exists.** The arm previously labelled f16 never requested
`KV_CACHE_PRECISION` and reads back `dynamic`. An interleaved equivalence probe
shows it matches a pinned u8 arm within 0.1% on working set at three depths,
while diverging up to 1 GB from pinned f16. The 36,500-token
`CL_OUT_OF_RESOURCES` ceiling is therefore a **u8** measurement. A pinned
`gpu_only_f16` arm now exists; its ceiling has not been run.

**Two u8 ceilings disagree** — 36,500 memory-walled against >= 40,000
position-limited. Same configuration, different outcomes. Available memory on
this device has ranged 1,203 to 10,290 MB across a week depending on uptime and
background services, which is the leading candidate and is not yet tested.

**Instrument reproducibility is a standing FAIL.** Two orchestrated pairs give
sigma 0.145 and 0.159 against a pass rule of sigma <= 0.10.
`free_physical_bytes_at_peak` varies 1.47x between arms while `peak_working_set`
agrees to 1.0002x — consumption reproduces, headroom does not, and a ceiling
measurement is a headroom measurement.

**Uptime is a controlled variable, discovered late.** Identical cells, same
prompt hashes, roughly 1 hour post-boot against roughly 22 hours: turn-1 prefill
moved 1.097 to 2.393 s at n = 2,000 and 7.090 to 18.137 s at n = 8,000 — up to
2.56x — while available memory was *higher* on the slow day. Any comparison
spanning a reboot or a physical relocation is invalid.

**The 288-cell matrix is not yet sealed.** The existing sealer expects a 2-cell
session shape and finds 313 files.

---

## Environment control

Every run records `available_mb`, `process_count`, `sum_private_mb`, pool and
committed bytes, and `uptime_s`, at cell start and at peak. Runs refuse below
`pre_run_available_mb_min` 7,000 MB or with tier-1 operator-controlled software
resident. Reaching that floor on this device requires setting Dell and McAfee
services to Manual and terminating the Copilot+ `WorkloadsSessionHost`
processes — stock, a cold boot idles at 5,001 MB available; cleaned, 10,047 MB.

Detached execution uses `tools/spawn_detached.ps1` (WMI-spawned), because
`Start-Process` children die with the SSH session under the Win32-OpenSSH job
object.
