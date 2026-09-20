# Dual-residency finding — Q-8B on Platform A iGPU

**Status:** finding (not a sealed quality result)  
**Citing void session:** `b1a291f0`  
**Session dir:** `derived/q8b/q8b_b1a291f0-d7a4-48f3-b4fd-154290a9d5c5/`  
**Do not seal** `b1a291f0`.

## What was tried

Q-8B launched with **dual-resident** pipelines: both `int4_4B` and `int4_8B`
`LLMPipeline` objects held in-process on `gpu_only_f16` (KV f16 pinned), so
per-entry arm shuffle could run without reload. `reload_events.json` shows two
initial loads only (`dual_resident_initial`); Available at start was ~10.8 GB
(above the old 10 GB floor).

## Failure signature

Not 100% emission failure. From the incomplete matrix (45/400 cells):

| phase | observation |
|---|---|
| early | 3 cells `emission_ok` (both arms on `multi_turn_base_0`; 8B on `base_1`) |
| then | unbroken streak of **42** cells with **zero** `n_decoded_steps` on every turn |
| generate | exact **`max_new_tokens=512`** burns (decode yields nothing parseable) |
| arms | **both** 4B and 8B lock into the same failure — not an 8B-only defect |
| contrast | Q-KV / W-3 no-emission fails are short EOS / prose, not 512-cap burns |

Reasoning / `<think>` was **not** implicated (extra context flag is sent via
`ChatGenerationConfig` / chat history path as in Q-KV; W-3 sealed scan had
0/1528 `<think>` gens).

**Artifact gap that delayed diagnosis:** `_quality_row` dropped
`model_result_raw`. Fixed permanently in Q8B-FIX via
`tools/quality_row_persist.py` → `model_result_raw_per_turn`.

## Implication

On this iGPU, **holding two tier IRs dual-resident corrupts shared pipeline
state** after a few successful cells. A local model ladder that needs both
tiers in one interleaved session therefore **costs a reload per arm switch**
(single-pipe block interleave). Reload wall is recorded in
`reload_events.json` with `excluded_from_decode_metrics=true`; cell TTFT /
decode timers start only after the active pipe is ready.

Dual residency remains behind an **explicit** flag
(`--allow-dual-resident` / `-AllowDualResident`), documented **known-broken**
citing `b1a291f0`. Default Q-8B is single-pipe block interleave.

## Related

- Reload smoke (switch costs only): `derived/q8b/RELOAD_FINDING.md`
- Degenerate refuse threshold (derived from this signature):
  `derived/q8b/DEGENERATE_GUARD.json`
