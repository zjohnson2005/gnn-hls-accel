# Cursor dispatch — E-FILTER Stage 1

Paste the block below into Cursor. It is written against the interfaces that exist in the repo as
of this writing; it does not assume anything not already on disk.

---

## Orientation — do this first, before writing any code

1. Call `seam_status()`, `seam_pins()`, and `seam_platform()` from the project-state MCP. Do not
   trust any hash, milestone, or gate state quoted in this prompt or in any other document —
   read it live.
2. Read `docs/SEAM_research_blueprint.md` §0 (operating mode R1–R4), §5 (hypotheses), §6 (audit
   standard), §11 (studies), Appendix A.2 (AUDIT-001 and the absence-claim rule).
3. Read `docs/EXPERIMENT_escalation_filter.md` in full. That is the pre-registration. This prompt
   implements it and does not supersede it.
4. Read `docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md` §6.2 (step record), §9 (sealing), and the
   manifest requirements.

If anything in this prompt contradicts a governing document, **stop and report the conflict.** Do
not resolve it yourself. Amendments are authorized by the human, not by an agent.

## What you are building

**E-FILTER Stage 1.** Run an agent workload with escalation disabled, log everything the router
consumes, then replay the routing rule offline across a deadline grid to determine which steps
*would have* escalated. Report the local resource envelope of the surviving steps as a function of
deadline.

No cloud calls. No confinement mechanism. No second platform. No NPU. This experiment is
deliberately routed around `mslice-a1a6`, which is blocked.

## Three things already true in the code — use them, do not rebuild them

**`policy.decide()` is already a pure function** of `(throughput, deadline_s, prompt_tokens,
step_type, n_out_pred_tokens)`. Offline replay is re-calling it with logged inputs and a different
deadline. **Do not write a second implementation of the routing rule.** Import and call the real
one, or the replay tests a rule that is not the rule.

**Arm L requires no new code path.** Escalation is `t_pred > deadline_s`. Set the deadline to a
sentinel far above any achievable `t_pred` and every step stays local, through exactly the same
code as a hybrid run. This preserves the isolation invariant by construction.

> **Do not use `float('inf')`.** `json.dumps` emits bare `Infinity`, which is not valid strict
> JSON, and it will silently poison every downstream reader. Define
> `DEADLINE_DISABLED_S: Final[float] = 1e9` in `seam/agent/policy.py`, assert at use that the
> observed `t_pred` is at least 1e6× below it, and record the sentinel explicitly in the manifest
> so a reader can tell "escalation disabled" from "deadline happened to be loose."

**`StepRecord` already carries** `prompt_tokens`, `cached_prompt_tokens`, `completion_tokens`,
`completion_chars`, `completion_bytes`, `routing`, `actual_wall_s`, and `deadline_overrun`. Extend
it; do not replace it.

## Phase 1 — instrumentation

Add to `StepRecord`, and to the JSONL writer:

```
prompt_tokens_new        int    # tokens actually processed this step, post-cache
kv_bytes_resident        int    # analytic: context_tokens * kv_bytes_per_token
kv_bytes_per_token       int    # model constant, from config, recorded in the manifest
peak_rss_bytes           int    # process RSS high-water for the step
cache_evicted            bool
evicted_bytes            int
context_tokens_total     int    # cumulative context presented, pre-cache
prompt_tokens_proxy      int    # what _estimate_prompt_tokens returned (router input)
```

`prompt_tokens_proxy` must be logged **separately** from the native `prompt_tokens`. The router
consumes the proxy; the analysis needs to know how wrong the proxy is. See the guards.

`kv_bytes_resident` is analytic — derive it from the model config as
`layers × kv_heads × head_dim × 2 × dtype_bytes` per token, compute the constant once, assert it
against the value already used elsewhere in the project, and record it in the manifest. Log
`peak_rss_bytes` alongside it so that analytic and observed can be compared rather than conflated.

## Phase 2 — the run

- Local backend only. `cloud_backend` is still a required argument to `run_task`; pass a backend
  that **raises** on `generate()` rather than a no-op stub. If escalation ever fires in Arm L, the
  run must die loudly, not silently produce a hybrid trajectory labelled local-only.
- `deadline_s = DEADLINE_DISABLED_S`.
- Thermal confound regime: warm to steady state, cool between tasks, randomize task order, record
  package temperature and frequency throughout. Declare the regime in the manifest.
- AC power, **charging complete** — not merely AC connected. A charging taper previously produced
  a +0.444 tok/s block-position slope that looked like a thermal effect and was not.
- Enough tasks that per-task peaks form a distribution. State N before running.
- Trajectories must be long enough for context growth to reach the regime of interest. **Verify
  the context growth curve on a pilot of 2–3 tasks before committing to the full run.** If context
  plateaus early, the study measures nothing and the task set must change first.
- Seal the run. Emit the manifest. Nothing is analyzed from an unsealed run.

## Phase 3 — offline replay

New module `seam/analysis/efilter.py`:

1. Load sealed step records.
2. For each deadline `D` in a grid spanning the observed `t_pred` distribution, call
   `policy.decide()` on every step's **logged router inputs** and mark it escalated or surviving.
3. Compute the envelope over surviving steps per task: peak `kv_bytes_resident`, peak
   `context_tokens_total`, max single-step `prompt_tokens_new`, P95 sustained decode demand, peak
   `peak_rss_bytes`, and the arithmetic-intensity distribution.
4. `over_provisioning(D) = envelope_unfiltered / envelope_filtered(D)`.
5. Bootstrap CI over tasks. Report per-task peaks and their distribution **plus** P95 of per-step
   context as the stable companion. **Never report a single max as the headline.**
6. Stratify by `step_idx` and by `step_type`, per AM-025.

Output: `derived/efilter/envelope_vs_deadline.json` and a figure. The deliverable is the **curve**,
not a number.

## Guards — each of these silently invalidates the result if unhandled

**`cached_prompt_tokens` reading zero is ambiguous** between "no caching occurred" and "not
instrumented," and the entire caching fork in §6 of the pre-registration is unanswerable if you
cannot tell them apart. Determine whether the OpenVINO path reports cache reuse. If it does not,
record `cache_instrumented: false` in the manifest and **fail the analysis loudly** rather than
treating zero as a measurement.

**The router consumes a `chars // 4` proxy, not the tokenizer.** The counterfactual escalation set
is therefore built on an estimate. Quantify it: regress `prompt_tokens_proxy` against native
`prompt_tokens` across all steps, report slope, intercept and residual spread, and propagate that
error into the deadline grid. If the proxy is biased more than 15%, report the filter boundary as
an interval rather than a line.

**`step_type` is currently hardcoded** to `"tool_call_synthesis"` in `run_task`, and `StepType`
admits only two values. Do not expand the taxonomy in this experiment — that is scope creep and it
belongs in its own amendment. Stratify by `step_idx` instead, and record the limitation
explicitly in the results.

**Setting a property is not evidence it took effect.** Verify power state, thermal regime, and the
escalation-disabled sentinel by reading them back, not by having set them.

**No secrets.** No API key material is printed, logged, hashed, or committed — not the value, not
a prefix. This experiment makes no cloud calls, so no credential should be loaded at all; if one
is, that is a defect worth reporting.

## Deliverables

1. `StepRecord` extension + writer, with tests.
2. `DEADLINE_DISABLED_S` and the assertion that `t_pred` stays far below it.
3. A cloud backend stub that raises, wired into the Arm L run.
4. Pilot run (2–3 tasks) with the context growth curve, reported **before** the full run.
5. Sealed full run + manifest.
6. `seam/analysis/efilter.py` + `derived/efilter/envelope_vs_deadline.json` + figure.
7. The proxy-error regression and the `cache_instrumented` determination, both reported whether or
   not they are favourable.
8. An `AUDIT_LOG.md` entry. One track only — do not write to any other track's section.

## Explicitly not in scope

Stage 2 (live hybrid arm). Cloud calls. Expanding the step-type taxonomy. Touching the confinement
mechanism or anything under `mslice-a1a6`. NPU or iGPU bring-up. Changing any hypothesis,
threshold, or prediction in the pre-registration — those are frozen and amendments are the human's
to authorize.

## Report back

State plainly: what you built, what the pilot context curve showed, whether caching is
instrumented, the proxy error, and the envelope curve. If any guard tripped, lead with that. A
result that cannot be interpreted is worth more reported than shipped.
