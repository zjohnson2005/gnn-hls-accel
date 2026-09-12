# DRAFT — do NOT submit

**Title:** `SCHEDULING_CORE_TYPE=PCORE_ONLY` confinement on Panther Lake (4P+4LP-E) — **unsettled**

**Status:** DRAFT / HOLD. Not filed upstream. AC 8×10 dual-phase matrix on Qwen3-4B-int4-ov
completed 2026-08-03 (`run_id=5eb09eba-b321-4b7e-b7df-e9b01194d388`); **no mechanism adopted**.
Do not treat throwaway 0.6B absolute-util evidence or the invalid TTFT=0 matrix as a settled
defect report.

## Environment

- Platform: Dell XPS 16 DA16260 / Intel Core Ultra 5 325 (Panther Lake)
- Topology (M1-committed, run `fb5cd2d5-e850-4de1-9b90-d368b5aa9994`): P-cores = CPUs 0–3; LP-E = CPUs 4–7; 8 logical CPUs, no SMT
- OS: Windows 11 build 26200
- OpenVINO / GenAI: 2026.2.1 / 2026.2.1.0 (recorded in matrix artifact)
- Matrix model: `OpenVINO/Qwen3-4B-int4-ov` (verified IR)
- Citing run: `5eb09eba-b321-4b7e-b7df-e9b01194d388`
- Citing artifact: `derived/mslice/affinity_matrix.json`
  SHA-256 `63d525b8e7300be20ff54925bd2409c1b5463971e14731be94fea0966de5af00`

## Matrix outcome (governing)

| Gate | Result |
|---|---|
| Quiesce (AC settled, charging=false, brightness 50, plan, Defender) | held |
| Prefill util samples | non-empty (min ≥10 per scored gen); `prefill_windows_ok=true` |
| Verification gates | **pass** |
| A0a/A0b | diagnostic only (exempt); both load P 0–3 LOADED, LP-E AMBIGUOUS |
| Per-core LOADED thresholds (two-pass A5/A6 decode) | applied to both phases |
| Adopted mechanism | **none** — zero A1–A6 CONFINED in both prefill and decode |
| A1–A6 overall | **UNCLEAR** (included cores LOADED; excluded cores AMBIGUOUS, not QUIET) |
| A2 label | **inconclusive** |

Outside-cluster residual decode Δ% (~2–8%) sits above `NOISE_BAND=1.1792` and below
per-core LOADED thresholds (~40–44), so confinement cannot clear QUIET on excluded cores.
A3-vs-A6 decode throughput ratio 1.025 is not material at >2× within-cell CV. Full tables
are in `AUDIT_LOG.md` FINDING 2026-08-03 (8×10 sealed matrix).

## Minimal repro (still the question to ask later)

```python
# SCHEDULING_CORE_TYPE=PCORE_ONLY, ENABLE_CPU_PINNING=YES, INFERENCE_NUM_THREADS=4
# Run a short generate(); sample per-CPU utilization during inference.
# Expected: load only on CPUs 0–3 (excluded cores QUIET under protocol thresholds).
# Status: A1/A2 overall UNCLEAR under baseline-subtracted dual-phase protocol —
#         excluded cores are AMBIGUOUS, not a settled leak/defect claim.
```

## Preliminary evidence (throwaway 0.6B; absolute util, not baseline-subtracted)

| Config | Expected | Observed loaded | Verdict |
|---|---|---|---|
| PCORE_ONLY | 0–3 | 0–7 | refused (leak 4–7) — superseded as publishable claim |
| ECORE_ONLY | 4–7 | 3–7 | refused (leak 3) — see note |

Retained only as historical motivation. The sealed 4B 8×10 matrix supersedes these numbers
for any upstream ask.

## What we are NOT claiming

- That `PCORE_ONLY` is a confirmed OpenVINO defect on Panther Lake.
- That `ENABLE_CPU_PINNING` is the missing configuration (A2 inconclusive).
- That process-affinity is adopted (blocked on dual-phase CONFINED).
- That AMBIGUOUS outside-core residual authorizes a mechanism or an upstream bug filing.

## Ask (deferred until a mechanism confines both phases)

Confirm whether `PCORE_ONLY` is expected to bind on a part with P + LP-E and **no** standard
E-cores, and whether `ENABLE_CPU_PINNING` changes that binding — **after** excluded cores
classify QUIET (or a protocol-strengthened noise/threshold revision is adopted first).
