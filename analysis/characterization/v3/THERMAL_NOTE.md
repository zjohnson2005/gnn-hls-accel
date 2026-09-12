# THERMAL_NOTE — Item 1.0c

## What was controlled

Prefill replication on Lunar Lake (Intel Core Ultra 5 325), CPU-only llama-bench
`b10155` / `1cbfd1988`, model `qwen2.5-0.5b-instruct-q4_k_m.gguf`, flags
`-n 0 -ngl 0 -t 8 -r 3`.

Depth block order was **randomized** (seed `20260728`) to
`[65536, 32768, 8192]` — not ascending. Deep points were measured **first**,
not last on a warm part. **90 s idle** between depth blocks.

Within each depth block, three timed reps ran back-to-back (llama-bench `-r 3`,
same harness pattern as the original shallow sweeps). The throttle rule was:
monotone decline across the three `samples_ts` values ⇒ throttling, mean
**invalid**, do not average through it.

## What was measured

| Signal | Result |
|--------|--------|
| `Win32_PowerMeter` `CurrentReading` | **Unavailable during the run** (`power_mw: null` on every telemetry sample). Idle probes also returned null in this session. Package power was **not** recorded. |
| `% Processor Performance` | Recorded every ~5–8 s during each depth block. Sustained effective clocks stayed elevated (block means ~152–161% of base; mins stayed ≥97%). Not a RAPL joule meter; it is a clock proxy only. |

So the thermal control is **procedural + clock-proxy**, not package-power-closed-loop. It rules out “deep depths always last on a warm ascending sweep” as a design bias. It does **not** prove the SoC was at a fixed thermal set-point.

## Throttle checks (1.0c / 1.0d)

| depth | samples_ts | monotone decline? | mean valid? |
|------:|------------|:-----------------:|:-----------:|
| 65536 | 52.65, 53.18, 53.64 | no (trend **up**) | yes |
| 32768 | 86.49, 85.72, 86.10 | no | yes |
| 8192 | 202.08, 187.80, 193.41 | no | yes |

No replicated deep/mid depth failed the monotone-decline rule.

**Carry-forward finding:** the original v2 `L=2048` vector
`[262.91, 255.59, 247.18]` **does** monotone-decline. That mean was treated as
invalid under the 1.0c rule and **re-measured**. The remeasure returned
~346 tok/s — faster than the stale v2 `L=512` mean (280 tok/s), which is
physically inconsistent for cold prefill. `L=512` was therefore also
re-measured in the same cool-session window. Both shallow points moved up
~35% vs v2; depth ordering is restored.

| depth | v2 mean | 1.0 mean | Δ |
|------:|--------:|---------:|--:|
| 512 | 280.38 | 382.21 | **+36.3%** |
| 2048 | 255.23 | 345.71 | **+35.5%** |
| 8192 | 185.37 (RECOVERED) | 194.43 | +4.9% |
| 32768 | 89.40 (n=1) | 86.10 | **−3.7%** |
| 65536 | 52.17 (n=1) | 53.15 | +1.9% |

This is a finding about the **original single-shot / warm ascending-sweep
design**, not a quiet update to the means. Shallow points were depressed in
v2; deep points were comparatively stable. Item 1 must fit the 1.0 sample
vectors, not the v2 CSV.

## What this does / does not rule out

- **Rules out:** systematic “deep-last-on-warm-sweep” bias in the 1.0 deep
  campaign (order was deep-first); monotone within-block throttling at
  8192/32768/65536; use of v2 shallow means as same-regime as the deep reps.
- **Does not rule out:** absolute thermal headroom differences vs a cold-boot
  run; DVFS policy changes across long sessions; the missing package-power
  trace; that 512/2048 (remeasured after the long deep campaign) and the
  deep blocks share one perfect set-point — they share a cooler post-campaign
  window, not a designed interleaved five-depth design.
- **Does not claim:** that relative SEM at 32768/65536 (0.26% / 0.54%) is
  hardware noise alone — only that the three-rep vectors are not
  monotone-throttle artifacts under the stated rule.
