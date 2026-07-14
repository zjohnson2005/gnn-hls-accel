# Stable vs in flux

For collaborators building framework adapters or tail-latency instrumentation.
Match STABLE mechanisms for compatibility. Do not hard-wire against IN FLUX
category boundaries without checking for updates.

## STABLE (safe to build against)

- **Audit / residual gating.** Invariant: process CPU = tagged categories +
  residual. Per-session residual-provenance gate threshold is 15% (batch-level
  gate at c>1). Failures are recorded; do not weaken the gate in adapters.
- **Exclusive-nesting timer discipline.** Region timers use exclusive
  `thread_time()` on the entering thread; nested regions do not double-count.
- **General taxonomy structure.** Categories exist, are session-scoped, and
  (under full / measured modes) are booked per-thread via schedstat. The set of
  category names and the residual bucket are the stable contract; exact
  FRAMEWORK vs THREADPOOL membership is not (see IN FLUX).
- **Task suite existence and structure.** Fourteen tasks in the main pool
  (SH-01, SH-02, CH-01, CH-02, RH-01, RH-02, RE-01, RE-02, LH-01, LH-02, FO-01,
  CN-01, SW-01, SO-01), mixed profile, stable task IDs. AH-01 and MX-01 exist
  but are excluded from the main pool.

## IN FLUX (do not assume final)

- **THREADPOOL and FRAMEWORK category boundaries.** Redefined across
  instr_version generations. Under full sampling at high thread counts the mock
  arm showed a large observer effect (py-spy: `thread_identity.register` /
  `sample_and_book` dominating; ~93% tax at c=100 full vs stripped). Throttle
  residual tax ~9.6% at c=100 vs stripped. Treat share curves that depend on
  these boundaries as provisional until re-checked under the active
  `instr_mode`.
- **Retrieve-locality correction to the process-CPU band.** Latest promotion
  report (`out/latency_collapse_promo_report.md`): primary process band at c=1
  with local retrieve is ~10.2-16.0 ms/turn; corrected process band after
  remote-retrieve substitution is ~4.2-11.9 ms/turn. Strict lower bound is
  largely unaffected. Do not naively subtract the pooled matched-pair delta
  from the band (see report note).
- **`instr_mode` (full / throttle / stripped)** is an active experimental axis.
  Category attribution reliability and observer tax change with mode; promotion
  runs use throttle. Stripped drops mid-session per-thread schedstat.

## Recommendation

Implement adapters against the STABLE audit invariant, exclusive nesting, and
task IDs. Re-read `METHODOLOGY.md` and the latest promo report before locking
any FRAMEWORK/THREADPOOL split or process-band number into a second framework.
