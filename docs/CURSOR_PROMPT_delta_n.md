# Cursor dispatch — ΔN: does enabling a backend cost context?

Track: `agent`. **One measurement. Nothing else.**

---

## Scope

E-FILTER, E-ATTRIB, E-CAP, E-NET and the A2/A3/A4 throughput chain are **closed**. Do not reference,
extend, or resume them. Their infrastructure — run lifecycle, sealing, paging telemetry, canary,
machine lock — is retained and used here.

`docs/EXPERIMENT_toggle.md` is a **draft, not a registration.** This prompt measures the one
quantity that decides whether it is worth registering at all.

## The question

> **Does enabling a compute backend reduce the maximum context the device can hold?**

If yes and the reduction is material, hardware state is a routing variable. If no, the line ends
here.

## What to measure

```
config A    cpu-p only
config B    cpu-p + igpu
config A′   cpu-p only, run again as a separate arm     ← the A/A
```

**iGPU, not NPU.** The NPU path requires `NPUW_LLM_PREFILL_CHUNK_SIZE` to work around
openvino#34617, so an NPU configuration bounds prefill activation memory by construction while
cpu-p may not. That difference sits inside the comparison at the magnitude being detected. The iGPU
has no equivalent forced workaround. **NPU is a follow-up, not part of this run.**

For each configuration, find the maximum context `N` that completes:

- Synthetic prompt of exactly `N` tokens, one generation of fixed short length. **No agent harness,
  no tools, no trajectories.**
- Ascending ladder, then bisect between the last success and first failure.
- **≥3 repeats per rung.** Teardown and memory-recovery wait between rungs, per the E1 protocol
  already implemented.
- Per rung record: `N`, peak process RSS, minimum free MB, hard page-read rate, completed y/n, and
  the failure mode at the boundary.

Also record, per configuration, **memory resident before any inference runs** — the standing
reservation.

## The A/A

`A` and `A′` are the same configuration measured as independent arms. **Their agreement is the
noise floor for this measurement.** Report the ceiling difference between them.

Gate: **if |ceiling(A) − ceiling(A′)| exceeds half of |ceiling(A) − ceiling(B)|, the effect is not
separable from measurement noise** and the result is reported as null regardless of the point
estimate.

## Controls

- `aihost` and `aicontext` quiesced identically across all configurations. Record their state and
  resident memory at the start of each. **A control, not a factor** — do not vary them.
- Machine lock every timed block. Canary either side. Detached launch.
- Paging telemetry recorded; the gate applies to admissibility of individual rungs, not to the
  ceiling determination itself — a rung that pages is still a rung that completed or did not.

## Report

1. `ceiling(A)`, `ceiling(B)`, `ceiling(A′)` in **tokens**, each with its repeat spread.
2. **ΔN = ceiling(A) − ceiling(B)**, in tokens, with the A/A spread beside it.
3. Standing reservation in MB for each configuration, measured before inference.
4. Failure mode at each boundary.
5. One line: **material, immaterial, or not separable from noise.**

## What counts as material

State this before running: **ΔN ≥ 1,000 tokens** against a ceiling near 9,000. Below 500 tokens the
line is dead. Between the two, report as inconclusive and state what would resolve it.

## Not in scope

No mechanism attribution — linear versus superlinear, activation versus KV. That explains why ΔN is
what it is; it does not change the measurement. No NPU. No policy comparison. No trajectories. No
new hypotheses registered until ΔN is known.

## Standing constraints

No commit, push, raw mutation, cloud call, or credential load. Every number carries its run_id per
AM-027(b). The `AMENDMENTS.md` / blueprint §14 dual-definition collision is resolved
(AMENDMENTS-side content reissued as AM-033 / AM-034; Blueprint retains AM-025 / AM-027).
