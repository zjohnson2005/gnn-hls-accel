# Cursor dispatch -- BFCL accuracy on the routed subset

Track: `agent`. This is the first test after the reconciliation failure. Read all of it before
starting; the design point in section 2 is the whole experiment and it is easy to get wrong.

---

## 0. Why this run exists

The cost table claims 42% of agentic work runs locally at `$130.33` against a `$154.42` default.
That claim has a quality condition underneath it that has never been measured: the 42% has to be
done *acceptably*, not just done. Right now it is an assumption.

This run is chosen ahead of the instrument work for one reason. Under greedy decoding the output
tokens are a property of the weights and the prompt, not of the machine's timing. The contention
problem that has blocked ten pilots does not apply to an accuracy endpoint. Every other item in the
queue is a timing measurement and inherits the `13.8 -> 6.065` reconciliation failure.

## 1. What is being measured

Accuracy of Qwen3-4B, `gpu_only` + `RESIDENT`, on BFCL v4 single-turn AST categories, sliced by
whether the deadline-aware local-first policy would have routed each item to the device.

## 2. The design point: partition, do not aggregate

**Do not report aggregate BFCL accuracy.** It answers a question nobody asked.

The policy routes by predicted latency, so the local subset is not a random sample of the benchmark.
It concentrates short-context, short-output items, which are also the easy ones. Aggregate accuracy
mixes those with items that would never have run locally, and the result is uninterpretable.

The quantity of interest is accuracy on **exactly the items the policy would route local**, against
the cloud model on those same items.

### 2.1 Two partitions, primary and secondary

**Primary -- oracle partition.** Every item is run locally, so `t_local` is measured, not predicted.
Route local iff `t_local <= D`. This isolates the scientific question ("is the latency-feasible set
also quality-feasible?") by removing predictor error as a confound.

**Secondary -- policy partition.** Route local iff `t_pred <= D`, where
`t_pred = prompt_tokens / R_prefill + n_out_pred / R_decode`. Report it, but the headline claim rests
on the oracle partition.

Report both. If they disagree materially, that disagreement is itself a result about the predictor
and must be stated, not smoothed.

### 2.2 Sweep the deadline; do not fix it

`D` is not 10 s. Sweep `D` over `{2, 4, 6, 8, 10, 15, 20, 30, inf}` seconds and report
`accuracy_local(routed(D))` as a function of `D`.

The curve is the deliverable, not a point. As `D` tightens the routed set shrinks toward easy items
and accuracy should rise. A curve that is flat, non-monotone, or falling is a stronger finding than
one that behaves.

## 3. Arms

| arm | model | config | items |
| --- | --- | --- | --- |
| LOCAL | Qwen3-4B INT4 | `gpu_only` + `RESIDENT` | all in-scope items |
| LOCAL_CTRL | Qwen3-4B INT4 | default config | all in-scope items |
| CLOUD | reference model | n/a | routed(D=10) plus a stratified sample of the escalated set |

`LOCAL_CTRL` exists so that any accuracy difference between configurations is detected. Placement and
residency should not change output tokens. **If they do, that is a defect and it outranks everything
else in this spec** -- stop and report it, because it would mean every configuration comparison in
the project has an unmeasured quality axis.

Cloud is not run on every item. Run it on the full `routed(D=10)` set and on a stratified sample of
the escalated set (stratify by category and by context length quartile, minimum 40 per stratum).

## 4. Registered predictions -- write these to disk before launching

Emit `derived/bfcl_routed/PREDICTION_BEFORE_RUN.json` with a timestamp and the run plan hash, before
any generation. The file is part of the result.

- **P1.** `accuracy_local(routed(D))` is monotone non-increasing in `D`.
- **P2.** At `D = 10`, `accuracy_local(routed)` exceeds `accuracy_local(all)` by at least 5 points.
- **P3.** At `D = 10`, `accuracy_cloud(routed) - accuracy_local(routed)` is strictly smaller than
  `accuracy_cloud(escalated) - accuracy_local(escalated)`.
- **P4.** `LOCAL_CTRL` and `LOCAL` produce identical outputs on at least 99% of items.

P3 is the routing claim: escalation sends work to the cloud that the device would have got wrong.
If P3 fails, the policy is escalating by choice rather than by necessity and the cost saving is
available at a quality cost that has not been priced.

## 5. Determinism, and the one way contention can reach this endpoint

Accuracy is *mostly* immune to machine state, not perfectly. Variable thread count changes GEMM
reduction order, which can flip an argmax at a near-tie.

Requirements:

- **Pin the thread count explicitly** and record it in the manifest. Do not let the runtime choose.
- **Determinism probe.** Run 24 items twice, same config, same pinned threads, 20 minutes apart.
  Assert byte-identical outputs. Report the divergence rate. If it is nonzero, the accuracy number
  is a distribution and must be reported with the observed spread, not as a point.
- Greedy decoding, temperature 0, fixed seed. Record all three.

## 6. Isolation and the partition-robustness check

Declare `isolation_mode: local`. The primary endpoint is accuracy, so measurement mode is not
required.

But the oracle partition is built from measured timings, and those timings are contended. Handle it
empirically rather than by blocking:

- Tag every timing field emitted by this run `partition_only: true`. **These timings are not
  poolable with any other timing result in the project** and must not be cited as throughput.
- **Partition-robustness check.** Recompute the partition with `t_local` scaled by 0.7 and by 1.3
  uniformly. Report, for each `D`, the Jaccard similarity of the routed set against the unscaled
  partition, and whether the sign of the P2 and P3 comparisons changes.

If the conclusions survive +/-30% uniform scaling, contention did not reach this endpoint and you can
say so with evidence. If they do not survive, this run needs measurement mode and you have learned
that cheaply.

## 7. Stratification (AM-025)

Report accuracy by BFCL category, and separately by step type. Aggregate-only reporting is not
acceptable. Include per-cell `n`; mark any cell with `n < 20` as unstable and exclude it from
headline statements.

Record the prompt-format divergence per category as a covariate. It is already measured
(+198.4 / +208.6 / +3575.3 tokens). It feeds context length, which feeds prefill, which feeds the
partition, so it must stay recoverable.

## 8. Preflight gates -- all must pass before generation

1. **AST gold selftest** 10/10.
2. **Memory gate.** The earlier `DryRunGate` refusal was `available 5913 MB < 7000 MB`. Close Cursor
   and confirm headroom before launching. This is a real requirement, not contention hygiene.
3. **Write-path dry run.** Three prior runs died at the write path *after* measurement completed
   (circular reference in `validity.timed_measurement`; `UnicodeEncodeError` on a non-ASCII glyph
   under cp1252; `ManifestValidationError: outputs rejects property tasks`). Root cause each time was
   a startup dry run that validated a hand-built synthetic instead of the real builder.
   - Build the manifest **through the real builder** on a 2-item run and write it to disk.
   - Open every output file with `encoding="utf-8"` explicitly.
   - Emit no non-ASCII characters into any written string.
   - Do not proceed until a real 2-item result has been written and re-read successfully.
4. **Cloud cost estimate.** Compute projected spend from dry-run token counts before any paid call.
   Hard cap `$8.00`. Halt and report if the estimate exceeds it. Record provider, model id, pricing
   table version and caching state in the manifest. Never log, print, hash or commit key material.

## 9. Reported values that decide validity

Report every one of these. A missing value makes the run inconclusive rather than negative.

| value | makes the run |
| --- | --- |
| AST selftest 10/10 | valid, else void |
| determinism divergence rate | point estimate if 0, distribution otherwise |
| `LOCAL` vs `LOCAL_CTRL` output agreement | valid if >= 99%, else escalate as defect |
| routed-set size at each `D` | interpretable; `n < 50` at a given `D` means no claim at that `D` |
| Jaccard similarity under +/-30% scaling | contention-immune if >= 0.9 and signs hold |
| per-category `n` | headline permitted only on cells with `n >= 20` |
| cloud spend actual vs estimate | budget honest |

## 10. Out of scope

Multi-turn categories. The u4 ceiling. Any throughput or ceiling claim. NPU. Instrument
reproducibility work. Do not register new hypotheses until this returns.

## 11. Standing constraints

No commit, no push, no raw mutation. Every number carries its `run_id` per AM-027(b). Cloud calls are
authorized in this run only, under the section 8.4 cap. Record the pre-run system state. Machine lock
around any timed block and a canary either side, even though timing is secondary here.

Narrative gate: the report states what was measured and what the numbers are. It does not supply a
mechanism for why accuracy behaves as it does. Mechanism is a separate run.
