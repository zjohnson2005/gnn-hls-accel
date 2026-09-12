# Cursor dispatch — E-ATTRIB, resume at the mechanism spike

Track: `attrib`. The `agent` track (E-FILTER) is live on the same machine and repository.

---

## Orientation

Call `seam_status()`, `seam_pins()`, `seam_platform()`. Read `docs/EXPERIMENT_attrib_spec.md` in
full — it is the pre-registration and this prompt amends it in four specific places, listed in §4.
Do not treat any hash or state quoted anywhere as current; read it live.

## State of play — what is already established

- The IR is **stateful** (56 Assign sinks). `start_chat()` / `finish_chat()` exist on the pipeline.
- E-FILTER's cache probe measured a TTFT ratio of **0.9936** on a byte-identical repeated prompt —
  but it exercised only the **stateless** path. That result says nothing about the chat path.
- **Correction to the record:** the earlier conclusion "caching is not happening" was drawn from
  the wrong path and does not hold. Whether KV is reused is a **calling convention**, not a
  property of the runtime.
- `max_position_embeddings = 40960` on both models. The spec's top context cell of 49152 is
  invalid.
- KV cache measured at **73,728 bytes/token**. Other project documents carry 144 KB/token. These
  differ by exactly 2× and the discrepancy is unresolved.

## 1. The mechanism spike — do this first, nothing else until it reports

Determine whether seating context through chat mode is **computationally equivalent** to
cold-ingesting the same context, and whether it actually reuses KV.

### Pre-check — rule out templating before anything else

Chat mode applies the chat template per turn. A stateless `generate()` on a concatenated string
may render a **different token sequence**. If you skip this, a mismatch in output looks like a KV
defect when it is a templating difference.

Render both paths and assert the **token ID sequences are identical** before comparing anything
else. If they differ, fix the rendering (use the tokenizer's `apply_chat_template` for the
stateless path) until they match, and report what it took.

### The two paths

```
PATH A (seated)      start_chat()
                     r = generate(C)            # long context, capture the response
                     generate(N)                # short new prompt  ← measure TTFT here
                     finish_chat()

PATH B (cold)        generate(render(C, r, N))  # stateless, full ingest  ← measure TTFT here
```

Greedy decoding on both — sampling disabled, temperature 0, fixed seed. Use the existing
`resolve_ttft_ns` and `_make_ttft_streamer` in `seam/backends/local_openvino.py`; do not write new
timing code.

Suggested sizes: `C ≈ 8000` tokens, `N ≈ 64` tokens, `n_out = 64`. Repeat **≥ 5 times**, randomized
order, machine lock held, warmed to steady state.

### Pass criteria — both required

| Test | Reported value | Pass |
|:--|:--|:--|
| **Token pre-check** | rendered token IDs, A vs B | **identical** |
| **Correctness** | greedy output bytes, A vs B | **byte-identical** |
| **Reuse** | `TTFT_seated / TTFT_cold`, median + 95% CI over repeats | **< 0.5** (expect ≈ N/(C+N), far lower) |

A ratio near 1.0 means chat mode is not reusing. Byte divergence under greedy decoding means the
seated state is not equivalent to the ingested one — either way the mechanism is unusable and you
take the fallback.

## 2. The fork

**Spike passes** → both identification routes are available. Implement **both**:

- **Route 1 (seated):** the spec's design as written — context and new-prompt varied independently
  via chat-mode seating.
- **Route 2 (interaction):** no cache required. With `P` = total prompt tokens,

  ```
  t = a + P/R_prefill + n_out·d0 + (n_out × P)·d1
  ```

  Sweep `n_out` at several fixed `P`; the decode-slope at each `P` is `(d0 + d1·P)`; regress those
  slopes against `P` — slope gives `d1`, intercept gives `d0`. **Center `P` and `n_out` before
  fitting** or the interaction term destroys the condition number.

**Spike fails** → Route 2 only. Report the failure and its mode plainly; do not attempt to repair
the seating mechanism without authorization.

## 3. Why both routes, when one would do

Two independent identifications of the same four parameters, agreeing, is stronger evidence than
either fit's R². Goodness-of-fit cannot detect model misspecification; disagreement between routes
can. This becomes gate **A6**.

## 4. Spec amendments — apply these to `docs/EXPERIMENT_attrib_spec.md`

1. **Grid:** top context cell `49152 → 32768`. Reason: `max_position_embeddings = 40960`; 32768 +
   256 output leaves headroom.
2. **New gate A6 — dual-route agreement.** Fit both routes on the same hardware. Pass = 95% CIs
   overlap on **all four** parameters (`a`, `R_prefill`, `d0`, `d1`). Failure is a finding, not a
   bug to tune away — report both fits.
3. **A5 conditional.** If the spike passes, A5 stands as written. If it fails, A5 is replaced by:
   `P` and `n_out` each have ≥3 levels, and the interaction term's VIF < 5.
4. **Record the correction.** Note in the spec that §6's "caching resolved" conclusion was drawn
   from the stateless path and is withdrawn.

## 5. Also report, in the same pass

The **model config fields** behind `73,728 bytes/token` — layers, KV heads, head dim, dtype, and
whether K and V are both counted. Another project document says 144 KB/token and the difference is
exactly 2×, which points at the KV head count. This is blocking an external communication, so
report the derivation, not just the number.

## 6. Standing constraints — unchanged

Own: `seam/bench/**`, `seam/analysis/attrib_fit.py`, `derived/attrib/**`, `configs/attrib.yaml`,
`AUDIT_LOG_attrib.md`, `tests/test_attrib_*.py`.

Read-only: `seam/backends/**`, `seam/manifest.py`, `seam/rawstore.py`, `seam/locks.py`,
`seam/kvmath.py`, `seam/powerstate.py`.

Forbidden: `seam/agent/**`, `seam/tools/efilter_run.py`, `AUDIT_LOG.md`, and every pinned governing
document. If you need a change in a read-only module, **stop and report** rather than editing.

Every timed block wraps in `seam.locks.exclusive(repo_root / ".locks" / "machine")`. Acquire,
measure, release — never held across analysis or code generation. Record acquire/release timestamps
in the manifest. If the lock is held by the other track, wait.

AC power with **charging complete**, not merely connected. Warm to steady state, cool between
blocks, randomize order. Seal every run and emit a manifest.

## 7. Report back

Lead with the spike table — the three reported values and their pass/fail. Then which route or
routes you implemented, the KV config derivation, and the spec amendments applied. If the spike
failed, say so first and do not bury it under what you built afterward.
