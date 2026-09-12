# Cursor dispatch — E-ATTRIB, the sweep

Track: `attrib`. The `agent` track (E-FILTER) is live on the same machine and repository.

---

## Orientation

Call `seam_status()`, `seam_pins()`, `seam_platform()`. Read `docs/EXPERIMENT_attrib_spec.md` —
**§7 "Established facts" and the amended §3 grid are new since your last pass.** They record the
spike outcome and the KV derivation as settled; do not re-test or re-derive either.

## What is settled

- **The seated route is dead.** Spike `6b40e3fe`: token IDs identical, greedy bytes identical,
  `TTFT_seated/TTFT_cold` median 1.0274. Chat mode re-ingests. Interaction route only.
- **KV is 73,728 bytes/token**, u8, sealed as `1fd81d2a`. Dtype explains the 2× against 144 KiB.
- **INT8 IR is absent, and that is fine.** The `d0` split is not one of the three §0 claims.
  Quantization is dropped from the grid. **Do not export a model to recover it.**

Your prior work stands — the centered interaction route, the fitter, the dashboard, the rotation
calculation, the rank-deficiency refusal, 427 tests. This is a continuation, not a redo.

## 1. Runtime pilot — before anything else

With no prefix reuse every cell re-prefills `P` in full, so the top `P` levels may dominate the
schedule and I do not know by how much.

Time the four corner cells — `(P=512, n_out=8)`, `(512, 256)`, `(32768, 8)`, `(32768, 256)` —
under the machine lock. Extrapolate total sweep wall time across 35 cells × 7 repeats, **including
cooldowns and warmup**, and report the estimate.

**If the projection exceeds one overnight run, stop and report.** Reducing `P` levels is not an
available fix: seven levels are the minimum for the second-stage slope-vs-`P` regression to have
leverage. The schedule is the human's to authorize, not yours to trim.

## 2. The sweep

```
P (total prompt)   {  512, 1024, 2048, 4096, 8192, 16384, 32768 }   7 levels, log-spaced
n_out              {    8,   32,   64,  128,  256 }                 5 levels
quantization       INT4        fixed
execution_target   cpu-p       fixed
```

35 cells × **≥7 repeats**, randomized order. Plus **6 held-out cells** at off-grid `(P, n_out)`.

Log spacing on `P` is deliberate — `d1` comes from curvature in the slope-vs-`P` line, and even
spacing wastes resolution at the short end where `a` dominates. Do not regularize it.

Thermal steady state, cooldown between blocks, AC power with **charging complete**, machine lock
held for every timed block and released before analysis. Seal the run, emit a manifest.

## 3. The fit

Centered interaction route, as already implemented:

```
t = a + P/R_prefill + n_out·d0 + (n_out × P)·d1
```

Two-stage identification for the report: at each `P`, regress `t` on `n_out` — the slope is
`d0 + d1·P`. Then regress those seven slopes against `P`. Slope gives `d1`, intercept gives `d0`.
Report this **alongside** the joint fit; if the two disagree outside CI, that is a finding about
model form and it goes in the report, not into a tuning loop.

## 4. Dashboard changes

- **A6 is not evaluable** — the seated route is gone. Report the row as such; do not silently drop
  it.
- **A6′ split-half agreement is now mandatory.** Partition the design into two halves balanced on
  `P` and `n_out`, fit independently, require overlapping 95% CIs on all four parameters. With one
  route left this is the only independent-replication check you have, so it is not optional.
- **A7 synthetic recovery** is promoted from a test to a reported gate.
- **D3 is DEFERRED**, INT8 absent. Say so in the table rather than omitting the row.

Everything else in §4 stands. **Report every gate every run, passing or not.**

## 5. Then the agent-step validation

Take E-FILTER's sealed local-only step logs, **read-only**, predict each step's wall time from the
fitted model, and report **B3 — agent-step MAPE**, gate ≤ 25%.

This is the number that decides whether the model describes agents or only microbenchmarks. If it
fails, that is a real result about the transferability of synthetic latency models and it gets
reported as one. Do not fit to the agent logs to make it pass.

## 6. Then the rotation

D5, per §4's explicit calculation. Three sensitivity curves — compute, bandwidth, floor — against
E-FILTER's deadline grid. **The claim holds only if argmax changes.** If it does not, report the
null plainly: the ranking of hardware upgrades is deadline-invariant for this workload.

Do not soften a null here. A deadline-invariant ranking is a clean negative that saves the field
effort and it is worth reporting well.

## 7. Standing constraints — unchanged

Own: `seam/bench/**`, `seam/analysis/attrib_fit.py`, `derived/attrib/**`, `configs/attrib.yaml`,
`AUDIT_LOG_attrib.md`, `tests/test_attrib_*.py`, `docs/EXPERIMENT_attrib_results.md`.

Read-only: `seam/backends/**`, `seam/manifest.py`, `seam/rawstore.py`, `seam/locks.py`,
`seam/kvmath.py`, `seam/powerstate.py`, and **E-FILTER's sealed run data**.

Forbidden: `seam/agent/**`, `seam/tools/efilter_run.py`, `AUDIT_LOG.md`, every pinned governing
document, and the meeting brief / pitch / email that carry the stale 144 KB figure — **those
corrections are the human's, not this track's.**

Machine lock on every timed block, released before analysis. If the other track holds it, wait.

## 8. Report back

In this order: runtime projection, then the dashboard table in full, then coefficients with CIs,
then B3, then the rotation. Lead with any gate that failed.

If the runtime projection is the only thing you produce this pass because it came back too large,
that is a complete and correct result — report it and stop.
