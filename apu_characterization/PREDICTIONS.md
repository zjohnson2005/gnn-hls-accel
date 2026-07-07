# Pre-registered predictions (file before Linux sweep runs)

Predictions recorded **2026-07-07** before the Linux replication sweep.
Do not edit after data collection; add a dated addendum instead.

## Deployment model

1. **Remote search** moves search body cost off the host CPU axis (TOOL_COMPUTE → HTTP I/O wait). Pooled TOOL_COMPUTE median will fall below **15%** across seeds with remote search vs **>80%** with local search on the same suite.

2. **Harness APU share** (ORCH + TOKEN + SERIAL pooled CPU) will be **>50%** with remote search at c=1, reconciling the agent breakdown with Phase 0's orchestration-dominant framing.

3. **HTTP_CLIENT envelope** (LLM + remote tool round trips) will hold at **~20–35%** pooled host CPU at c=1 — envelope work, not body compute.

## Concurrency (Phase 0 extension — to test on Linux sweep)

4. **ORCH_DISPATCH** remains the largest single host category as concurrency **c** increases.

5. **Harness share rises with c** as dispatch and tokenization multiply across concurrent sessions.

## Behavioral buckets (not task labels)

6. Sessions bucketed by **realized tool mix** will show amenability spread driven by **code_exec burst** and **retrieve-heavy** buckets, not by SH/RH task labels.

7. **Search-only behavioral bucket** (B1) will show **<5%** host CPU % of wall under remote search.

## Instrumentation cross-check

8. **py-spy** sampling at c=100 mixed will agree with category timers within **10 pp** for categories holding **≥5%** pooled CPU.

9. **Timer overhead** (APU_NOINSTR comparison) stays below **3%** of instrumented CPU on Linux.

## Resolution

10. **test_resolution** PASS on Linux (±10% on 80 ms calibrated spins); Windows runs remain footnote-only below 200 ms/session.

## Non-predictions (explicitly out of scope)

- Absolute host CPU capacity claims (denominators: batch ms, c, seed count, wall % always reported).
- Pattern-match accelerator need (depends on tool locality; remote search default makes it out of scope).
