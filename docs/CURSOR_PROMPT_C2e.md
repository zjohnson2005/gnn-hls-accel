# Cursor dispatch — C2e: fix the dry-run properly, scope the gate per-endpoint, seal

Track: `agent`. Attrib frozen. Everything in C2b–C2d not restated here still stands.

---

## Where `e66701aa` got to

```
encoding probe          PASSED — → and α printed
median context ratio    7.12  ≥ 3.0
paging windows          recorded per task
timed-block invalid.    2 — C2T13 (3 samples), C2T10 (4 samples)
seal                    FAILED — ManifestValidationError: outputs rejects property `tasks`
```

## 1. The dry-run has now missed three seal failures. Fix the reason, not the instance.

```
cb0ed2e3   circular reference at manifest emit
a161f89e   UnicodeEncodeError printing →
e66701aa   ManifestValidationError on outputs.tasks
```

Three completed runs, three write-path deaths, one countermeasure that failed every time.

**The cause: the dry-run validates a hand-constructed synthetic object rather than the real one.**
A synthetic summary that omits `tasks` from `outputs` cannot possibly catch a schema violation on
`tasks`. Every field added to the real summary is invisible to the guard until it breaks a run.

**Do not add `tasks` to the synthetic.** That fixes one instance and leaves the class intact.

**Required fix:** the dry-run must construct its object by calling the **same builder function the
real run calls**, with stub records and a stub manifest. Shape parity then holds structurally, and
every future field is covered without anyone remembering to update a fixture.

```
    now:   synthetic = { ...hand-written... }        →  emit  →  validate
    want:  synthetic = build_summary(stub_records)   →  emit  →  validate
                       └── the real builder
```

Add a test asserting the dry-run object and a real summary have **identical key sets** at every
level of nesting. That test is what prevents the fourth occurrence.

Then resolve the immediate bug: either `outputs` gains `tasks` in
`seam/schemas/run_manifest.schema.json`, or the emitter stops putting it there. Decide which is
correct and say why — a schema that rejects a field the code emits means one of the two is wrong,
and silently permitting it would be the worse fix.

**Record in C9.** Three runs lost to write-path defects surfacing only after the measurement was
spent, with a guard that was structurally incapable of catching any of them.

## 2. Scope the paging gate per-endpoint, not per-block

Two blocks tripped with 3 and 4 samples against an idle baseline where 1.7% of samples are
non-zero. Two of five is well above chance, so **treat it as real paging during long-context
generation** — consistent with the capacity story and worth recording as such.

But examine what it contaminates.

```
peak resident KV  =  context × 73,728        ← arithmetic from token counts. Paging cannot touch it.
t_pred            =  ThroughputModel(fixed R) ← per-baseline, not per-block. Unaffected.
t_actual, deadline_overrun, actual_wall_s     ← timing. Genuinely contaminated.
```

**E-FILTER Stage 1's primary endpoint does not depend on the quantity being gated.** The gate is
currently discarding whole blocks from an analysis that is immune to the contamination.

**Required change:** tag each block `paging_admissible: bool` with its reasons, and have the
analysis apply it **per endpoint**:

- **Envelope endpoints** — peak resident KV, peak context, max single-step prefill tokens,
  arithmetic intensity — computed over **all** blocks. Report the paging-admissible subset alongside
  as a robustness check.
- **Timing endpoints** — anything derived from `t_actual`, `deadline_overrun`, `actual_wall_s`,
  realized JCT — computed over **admissible blocks only.**

Report both, and state the admissible fraction next to every number so a reader can see which basis
each rests on. **Blocks are never dropped from the record** — only from specific analyses, with the
reason attached.

This is not loosening the threshold. The threshold is correct; it was being applied to endpoints it
does not govern.

## 3. Re-pilot and seal

≥5 tasks. Pass conditions:

- median per-task context ratio ≥ 3.0
- **the run seals**, confirmed by `verify_sealed`
- paging invalidations recorded per block, not treated as run-fatal

**Sealing is the deliverable.** It has failed three times and is now the only thing standing between
this project and its first real E-FILTER result.

## 4. Then the full run

As C2b §6: deadline grid derived from the measured `t_pred` distribution with ≥8 points spanning its
range, amendment withdrawing the pre-registered 8 s deadline, corrected proxy per AM-027,
exclusionary paging gate scoped per §2, cloud backend that raises, P1–P6 at materiality 1.2×, and
the computed ceiling `C_max/C_min` reported alongside the measured over-provisioning.

## Report, in order

1. The dry-run rebuilt on the real builder, plus the key-set-parity test passing.
2. Which side of the `outputs.tasks` mismatch was wrong — schema or emitter — and why.
3. Re-pilot: ratios, per-block paging admissibility, and **`verify_sealed` result.**
4. Then the full run, with the admissible fraction stated next to every timing-derived number.

## Standing constraints

Machine lock every timed block, canary either side, detached launch. No commit, push, raw mutation,
cloud call, or credential load. Thresholds do not move. Every number carries its run_id per
AM-027(b).
