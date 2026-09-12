# Optimal-config cost figures — SUPERSEDING

**Status:** standing · **Date:** 2026-08-10 · **Amendment:** AM-035 (POST-DATA)

This file **supersedes** any earlier optimal-config / cost table that used the retracted
arm-A constant-plus-linear form (19.45 s intercept at `n_cached=12000`) or reported cost
interaction as **6×**. No prior committed writeup under that title was found in-repo; the
retracted numbers circulated as a narrative fit. This is the citable replacement.

## Citing runs

| Role | run_id | Seal |
|---|---|---|
| n_cached=4000 matrix (24/24 OK) | `9f38eb15-6fe6-40b4-871b-a02ec5629bb1` | `derived/delta_prefill/sealed_9f38eb15-6fe6-40b4-871b-a02ec5629bb1/` |
| n_cached=12000 matrix (17 OK + robustness) | `d5c98342-a0b2-41a9-b6e2-93ac7a39c3ba` | `derived/delta_prefill/sealed_d5c98342-a0b2-41a9-b6e2-93ac7a39c3ba/` |

Model form and retraction wording: `AMENDMENTS.md` **AM-035**;
`derived/delta_prefill/AM035_delta_prefill_model.json`.

## Standing cost table (corrected)

| Config | % local | Cost | Saving vs default |
|---|---:|---:|---:|
| default | 0% | $154.42 | — |
| gpu_only alone | 25% | — | 7% |
| gpu_only+residency | 42% | $130.33 | 16% |

## Interactions

| Quantity | Value | Note |
|---|---|---|
| Cost interaction (super-additive) | **2.3×** | Corrected; was 6× on the retracted intercept model (AM-035) |
| Latency interaction | **2.4×** | **UNCHANGED** — from measured medians, not fits |

## Feasibility consequence (from measured model)

Local feasibility depends on session position (`n_cached`), not delta alone.
Max feasible Δ at the 10 s bound, gpu_only+residency:

| n_cached | max feasible Δ |
|---:|---:|
| 4000 | 5760 |
| 12000 | 1920 |
| 27600 | 834 |

## Retraction (do not cite)

- Arm-A **19.45 s** constant at `n_cached=12000` — artifact of two points at one cached length.
- Cost interaction **6×** derived under that bad model.
- Any feasibility bound that ignores `n_cached`.
