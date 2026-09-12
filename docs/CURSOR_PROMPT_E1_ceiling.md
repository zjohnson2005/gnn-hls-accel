# Cursor dispatch — E1: measure the context ceiling. The constraint is the finding.

Track: `agent`. Attrib frozen. **This supersedes the C2 pilot sequence as the immediate priority.**
E-FILTER is not cancelled; see §5.

---

## Why this changes priority

Ten pilots have failed on memory. That is not an obstacle to the research — **it is a measured
property of the platform, and it is the strongest claim currently available.**

```
architectural limit    40,960 tokens   max_position_embeddings
practical limit        ~7,000–9,100    memory exhaustion
                       4.5–5.9× below
```

At 9,114 tokens the KV cache is **672 MB** against a 2.6 GB model with ~2.6 GB free. **KV is not the
binding resource.** There is no cross-call prefix reuse, so every step re-prefills the full context
and prefill activation memory scales with context on every step.

The hybrid-execution consequence is binary and no policy recovers it:

> **A step needing more than ~9,000 tokens of context cannot run locally at any latency budget.
> Hardware does not shift the routing decision — it removes the option.**

## 1. Bracket the ceiling properly

Stop inferring it from crashes. Measure it.

**Design.** A synthetic driver — not the agent harness — that constructs a prompt of exactly `N`
tokens, runs one generation of fixed short length, and records peak process RSS, minimum free
memory, and whether it completed.

```
N ladder    2,000  4,000  6,000  8,000  10,000  12,000  16,000  24,000  32,000  40,000
repeats     ≥3 per rung, ascending, with teardown and memory-recovery wait between
stop        first rung that fails, then bisect between it and the last success
```

Report per rung: `N`, peak RSS, minimum free MB, page-read rate during generation, completed y/n.

**The headline output is `peak_RSS ~ f(N)`.** Fit it and report the form:

- **Linear** → KV plus a constant. The ceiling is predictable and scales with available memory.
- **Superlinear** → attention activations scaling with context². The ceiling is much harder than the
  KV arithmetic implies, and this is the sharper finding.

Report the fitted coefficients and the extrapolated N at which peak RSS exceeds total machine
memory. That number, with its mechanism, is the result.

## 2. Measure what the platform reserves for itself

`aihost` and `aicontext` are Windows' own on-device AI stack, running on the same silicon.

**2.1** — At idle, quiesced: their resident memory and CPU. Report both, sampled over ≥60 s.

**2.2** — Re-run the §1 ladder with those services stopped, and again with them running. Report the
ceiling in each condition.

> **The delta is the number: how many tokens of usable agent context the platform's own AI services
> cost you.**

Nobody publishes that, and it directly reduces the usable budget the meeting brief currently assumes
from the spec sheet.

**Record the stop/start as a deliberate deviation from deployment conditions in the manifest.** A
real AI PC ships with these running; a measurement with them stopped describes a machine nobody has.
Both conditions are needed precisely because the difference is the finding.

Restore the original service state and startup type afterward. Record what it was before changing
it.

## 3. Determine whether chunked prefill exists on the CPU path

If §1 shows superlinear growth, capping context treats a symptom.

Chunked prefill processes the prompt in fixed segments, bounding activation memory **independently
of context length**. OpenVINO exposes `NPUW_LLM_PREFILL_CHUNK_SIZE` on the NPU path. Determine
whether a CPU equivalent exists — plugin property, config key, or pipeline option.

**If it exists:** enable it, record the chunk size, re-measure the §1 relationship. That would lift
the ceiling for every future run and change the finding from a hard limit to a configuration
choice — which is a *better* result, because it becomes a design knob rather than a wall.

**If it does not:** report that plainly. The ceiling is a platform property and the finding stands
as stated.

## 4. Audit before claiming

`2603.04428` reports edge KV budget forcing re-prefill on an M4 Pro. **Adjacent but not the same** —
their framing is KV eviction under capacity pressure; ours is prefill *activation* memory bounding
context far below both the KV budget and the architectural limit.

Search that distinction specifically before any absence claim enters a brief or abstract, per the
Appendix A.2 standing rule. Record the search there.

## 5. E-FILTER is unblocked separately, off this machine

The over-provisioning replay is **offline arithmetic over a logged trajectory**. The trajectory is
deterministic given the model, the prompts and greedy decoding, so it need not be generated on the
machine whose throughput is applied to it.

**Proposed, pending human authorization — do not start without it:**

- Generate long trajectories on a machine with adequate memory, same model IR, same prompts, greedy.
- Measure `R_prefill` and `R_decode` on this laptop with a microbenchmark that never approaches the
  memory wall.
- Combine offline: apply the laptop's `R` to the externally generated trajectories.
- **Verify** by running three short tasks on both machines and confirming **byte-identical**
  transcripts. That closes the objection that the trajectory is not the one the laptop would
  produce.

Report what a suitable machine would require — memory, CPU, OpenVINO availability — so the human can
decide between Platform B's arrival and a cloud instance.

## Report, in order

1. `peak_RSS ~ f(N)` with fitted form and coefficients. Linear or superlinear.
2. The bracketed ceiling, with the failure mode at the boundary.
3. `aihost`/`aicontext` idle footprint, and the ceiling delta with them stopped versus running.
4. Chunked prefill: available or not, and its effect if so.
5. The audit result on `2603.04428` and the activation-memory distinction.
6. Requirements for external trajectory generation.

## Standing constraints

Machine lock every timed block, detached launch. No commit, push, raw mutation, cloud call, or
credential load. Service state changes are recorded before and restored after. Every number carries
its run_id per AM-027(b).
