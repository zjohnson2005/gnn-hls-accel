# N-1 - CB equivalence probe (PRE-RUN registration)

**Session kind:** 
1_cb_equivalence
**Corpus match:** 41e419bd-f3e9-43b1-8364-0ebd89fa086b (n_cached in {2000,4000,12000}, delta=400, arm=gpu_only_u8, int4)
**Question:** Does ContinuousBatchingPipeline with use_cache_eviction=False match plain LLMPipeline on delta-prefill timing closely enough that attention-window (axis 5) cells on the CB path can be compared to the existing corpus?

## Prediction (directional claim)

**No significant difference** between CB-with-eviction-off and plain LLMPipeline.

**Significant** means: for a depth, the absolute relative difference between the two pipeline types (median turn-1 or turn-2 prefill) exceeds the session's own canary early_max on that turn (i.e. the instrument noise floor measured in-session before the matrix). Thresholds follow docs/CANARY_PROTOCOL.md: after calibration, 	hreshold = max(2 * early_max, rel_drift_floor); the equivalence gate uses early_max itself as the same-instrument bound for CB-vs-llm, and reports both.

Report **per-depth ratios** (cb / llm) with **spread** across the two repeats.

## If they diverge

No window result can be compared to the existing corpus. Axis 5 needs its own within-CB baseline. That is a **finding about the runtime**, not a protocol failure, and it must be known **before any window cell runs**.

## Design notes (not predictions)

- Pipeline type participates in Fisher-Yates interleave (not blocked by type).
- Canary is pinned to plain LLMPipeline so the reference does not follow the per-cell CB path.
- WorkloadsSessionHost is re-killed every 5 minutes for the life of the run (respawn interval ~10-15 min).
