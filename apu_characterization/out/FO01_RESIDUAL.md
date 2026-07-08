# FO-01 residual chase (v3.1 replication)

**Task:** FO-01 — 9-way search fan-out in one LLM turn (dispatch burst).  
**Sweep relevance:** Fan-out at batch scale is what concurrency multiplies; FO-01 is the canary.

## Finding: bounded, fan-out-specific, below audit gate

| Seed | Host CPU | Residual | % host | Trim | 9× search |
|------|----------|----------|--------|------|-----------|
| 1 | 137 ms | 9.1 ms | 6.6% | 0 | yes |
| 2 | 352 ms | 23.9 ms | 6.8% | 0 | yes |
| 3 | 131 ms | 14.1 ms | 10.7% | 0 | yes |
| 4 | 125 ms | 11.2 ms | 9.0% | 0 | yes |

**Median residual: 7.9% of host CPU** (batch aggregate). Per-session gate is 15% — all FO-01 sessions **PASS**.

## Where the unattributed CPU lives

All residual is booked as `RESIDUAL_UNATTRIBUTED` at **session end** (`provenance=residual`), not mid-stream ORCH reconcile:

- `parallel_cpu_trim_ns = 0` on every FO-01 session — this is **not** category over-sum trim.
- Residual mass is **9–24 ms** per session: short-lived executor/HTTP threads finishing after the last `sample_session_threads` burst.
- Dominant attributed categories on FO-01: **THREADPOOL** (~38–47 ms), **ORCH** (~20–35 ms), **FRAMEWORK** (~20–27 ms). Search body is remote (zero TOOL by design).

**Per-step shape:** 11 stream turns; 9 `search` calls land in one fan-out batch (`llm_step` 0–8 permuted by seed). LLM wait ~9–10 s; mock search I/O wall ~11–14 s concurrent with session clock.

## Resolution

1. **Code fix (v3.1.1):** second `sample_session_threads(burst=True)` **after** the tools-node message loop (not only at chunk entry), so fan-out pool threads finalize before session-end gap booking.
2. **Sweep policy:** FO-01 residual is **fan-out-specific** and **bounded <11%** at c=1. Concurrency sweep adds a **per-level residual check** with FO-01 (or any session with ≥4 parallel tool calls) as canary; gate remains 15% per session, with **12% warning** on fan-out sessions at workers>1 (see `audit.py`).

## Quotable claim

At c=1, FO-01 fan-out does **not** block the sweep: residual stays under the 15% audit gate. Attribution strain under parallel fan-out is real (~8% session-end gap) but **measured and bounded**, not the v2-era opaque reconcile mass.

Regenerate: `python apu_characterization/tools/_fo01_residual_chase.py`
