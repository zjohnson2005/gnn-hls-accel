# CAP-01 pre-registered expectations

Freeze point: before P0 pool outcomes and before any timed harness run.

These are directional expectations, not acceptance criteria. Gates and the
single primary test remain unchanged when expectations fail.

| Model-latency median | Expected paired solve-rate pattern |
|---|---|
| 4000 ms | LangGraph approximately equals Rust approximately equals raw Python. This is the positive-control null. |
| 1000 ms | Approximately null; any material separation is investigated as a confound. |
| 100 ms | Small or absent separation; descriptive only. |
| 20 ms | Separation may begin as the turn-path floor enters the crossover band. |
| 10 ms | Ordered differences expected: raw Python at least Rust at least LangGraph. |
| 5 ms | Largest expected floor-driven difference; the pooled five-domain LangGraph-versus-Rust SCALING test at each domain's primary tier is the sole primary test. |

Budget interaction expectation:

- The 10 s tier may expose a larger candidate-count difference where the pool
  solve curve is still climbing; D1/D5 nevertheless retain 2 s as their
  industry-relevant primary tier.
- A Holm-corrected gap confined to selected domains, off-tier cells, or raw
  Python maps to claim Rung 2, not Rung 1.
- If throughput consistency passes but no capability cell separates, claim
  Rung 3 is reported with the same prominence as a positive result.

Population expectation:

- SATURATED and DEAD tasks dilute candidate-count sensitivity and are excluded
  from the headline by the frozen calibration rule.
- Their all-task results remain visible as secondary context.

No expectation in this file applies to Tier D. The 10 to 50 microsecond point
is a projection from the measured three-point relationship and is never a
measured CAP-01 arm.
