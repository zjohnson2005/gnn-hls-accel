# DEMO-1 v2 groundwork (ENV-ATLAS, SLO-SENS, policy, pins, H1-CPU feasibility)

Date 2026-10-12. Offline, $0. Design: docs/DEMO1_DESIGN.md. Numbers from
analysis/demo1/DEMO1_ATLAS.json (tools/demo1_atlas.py) and
analysis/demo1/atlas/*.json (tools/h1_context_sizing.py). No predictions
here; the prereg draft is in the 2026-10-12 agent report.

## 1. ENV-ATLAS

Method:
- Gold BFCL trajectories run through the live H1 prompt path
  (MultiTurnAgentSession, render_bfcl_tools_style).
- Tokens are counted with the Qwen3-4B tokenizer (OpenVINO/Qwen3-4B-int4-ov
  b467368).
- n_ctx is the step-0 prompt of each user turn.
- Check: multi_turn_base turn 0 equals d482c621 on 200/200 entries. Live 4B
  later turns run a median +1.8% (p90 +8.3%) over gold.
- Within every entry, n_ctx never decreases (all atlases).

Bands, as share of turns / share of entries by their largest turn:

| workload, arm | [0,468] | (468,10000] | (10000,16437] | (16437,18500] | (18500,inf) |
|---|---|---|---|---|---|
| multi_turn_base, FULL | 0 / 0 | 1.000 / 1.000 | 0 / 0 | 0 / 0 | 0 / 0 |
| multi_turn_long_context, FULL | 0 / 0 | 0.867 / 0.800 | 0.005 / 0.005 | 0 / 0 | 0.128 / 0.195 |
| long_context, OBS_MASK K=256 | 0 / 0 | 1.000 / 1.000 | 0 / 0 | 0 / 0 | 0 / 0 |
| long_context, OBS_MASK K=512 | 0 / 0 | 0.970 / 0.950 | 0.030 / 0.050 | 0 / 0 | 0 / 0 |
| long_context, OBS_MASK K=1024 | 0 / 0 | 0.869 / 0.800 | 0.105 / 0.155 | 0.020 / 0.030 | 0.005 / 0.015 |
| long_context, OBS_MASK K=1536 | 0 / 0 | 0.867 / 0.800 | 0.049 / 0.060 | 0.023 / 0.040 | 0.061 / 0.100 |
| long_context, OBS_MASK K=2048 | 0 / 0 | 0.867 / 0.800 | 0.005 / 0.005 | 0.010 / 0.020 | 0.119 / 0.175 |
| long_context, OBS_MASK K>=4096 | same as FULL | | | | |
| SWE trajectories (15; replay only) | 0.003 / 0 | 0.620 / 0.467 | 0.316 / 0.400 | 0.018 / 0 | 0.043 / 0.133 |

Notes:
- SWE counts are the logging model's context_len_before, not Qwen tokens.
- multi_turn_base under OBS_MASK K=1024 is unchanged: its largest tool
  output is 147 tokens.

The ~31k tool output: every large long_context observation is
`get_stock_info` (TradingBot), 31,661-31,666 tokens. There are 41 such observations across 40 entries. The
first one in an entry comes at turn 1, 2 or 3 and moves the context from about 2-3k to about 34k in one
step.

What each retention arm in code does to it:
- FULL: unchanged, 31.7k tokens.
- POSITIONAL: no transform exists in code. It is only the budget number
  SEMANTIC must match (docs/RETENTION_PROTOCOL.md), so it cannot be sized.
- SEMANTIC: needs span labels (R-LABELS, Rithwik), so it cannot be sized.
- OBS_MASK (seam.retention_prompt.mask_observation): keeps the first K
  whitespace tokens, with no marker.
  - K=1024 shows 8,074 tokens of the stock output.
  - K=2048 shows 16,170.
  - K>=4096 keeps all of it (the output is under 4,096 whitespace tokens).
  - K is not registered anywhere. The sweep chooses it as a design
    parameter, before any run.

RET-ENVELOPE finding: OBS_MASK K=1024 puts 37 of the 40 jump entries into
(10,000, 18,500]: 31 in (10000,16437] and 6 in (16437,18500]. That makes it
the V4 source. The caveat: a live model sees a truncated observation, which
may cost capability. The atlas sizes gold calls only.

## 2. SLO-SENS

Method: the edge at target S is the n where cold prefill equals S.
- It is interpolated log-log between the two adjacent sealed probe medians
  that bracket S, within one sealed run.
- Source order: the config's limit run first. If that run doesn't bracket S,
  the same-platform/model/KV CAP-4 run: XPS 4B u8 2b3316b6, T2S 4B u8
  65e33de8.
- No extrapolation: an unbracketed S is reported as a bound.
- The 10 s edge here is interpolated. The sealed limit is the last passing
  rung, which is what routing uses.

| config | 5 s | 10 s (sealed limit) | 20 s |
|---|---|---|---|
| XPS CPU 4B | < 250 (6.47 s at 250, 7f232f86) | 680 (468) | 1,690 (7f232f86) |
| XPS GPU 4B u8 | < 8,000 (6.80 s at 8,000; 2b3316b6 starts at 12,000) | 10,175 (10,000) | 15,187 (2b3316b6) |
| T2S GPU 8B u8 | < 14,000 (7.67 s; no 8B curve) | 16,541 (16,437) | 25,317 (56c116a6) |
| T2S GPU 4B u8 | 12,720 (65e33de8) | 18,590 (18,500) | 27,878 (65e33de8) |

In-band share: the share of turns (entries with a turn) between the XPS GPU
edge and the T2S 4B edge.

| target | band | base | long_context FULL | long_context OBS_MASK 1024 | SWE |
|---|---|---|---|---|---|
| 5 s | (<8000, 12720] | 0 | >= 0.050 (21 entries) | >= 0.071 (34) | >= 0.316 (10) |
| 10 s | (10175, 18590] | 0 | 0.005 (2) | 0.128 (40) | 0.325 (8) |
| 20 s | (15187, 27878] | 0 | 0 (0) | 0.052 (17) | 0.091 (4) |

The 5 s row is a lower bound, counted over (8000, 12720], because the XPS
5 s edge is only bounded. This is a sensitivity, not a rule change: the SLO
stays 10 s. Tighter targets widen the band on long_context; looser ones
empty it. XPS edges move faster than T2S edges (exponent 2.12-2.25 vs 1.85).

## 3. Policy (from tools/run_h1_hybrid.py)

| policy | decision | triggers -> purchase |
|---|---|---|
| slo_escalate | sticky (stays on cloud for the rest of the entry) | measured TTFT > 10 s or decode < 6 tok/s -> latency (context when n_ctx > 18,500); stay_cloud inherits |
| emission_escalate | sticky | no_parseable_tool_call, no_tool_call / empty_execute at the local span end -> capability |
| full_signal_bounceback | per turn (one-turn bounce, then local) | no_parseable_tool_call, step_budget (5 steps), tool_exec_error -> capability. No latency trigger. |
| local_only | never escalates | none |
| cloud_only | every turn | reference |
| agnostic_default | never escalates (derived only, not run live) | none |
| legacy ctx gate (decide_slo_escalate_legacy_with_ctx, unused) | sticky | ttft, decode, n_ctx > 10,000 |

No existing policy is both per-turn and latency-triggered:
full_signal_bounceback is per-turn but capability-only, and slo_escalate is
the only one with a latency trigger.

Recommendation: slo_escalate in every cell.
- It is the only trigger that depends on hardware speed (H1_CPU_AMEND_1),
  and the latency purchase is exactly what DEMO-1 measures.
- Because n_ctx never decreases within an entry, sticky and per-turn routing
  send the same turns to cloud for latency and context triggers (up to TTFT
  noise at the edge).
- Capability purchases are not exercised in the V cells. They are
  hardware-independent by the thesis, and measured in d482c621 (81
  no_parseable, 11 step_budget, 0 tool_exec).
- A combined per-turn policy (bounceback triggers plus the SLO trigger)
  would need new code and an amendment. It is not proposed for 2026-10-16.

## 4. Pins (derived/h1_hybrid/demo1/, accepted by run_h1_hybrid ENTRY_PINS)

| pin | rule | sha256 |
|---|---|---|
| DEMO1_BASE_30 | multi_turn_base, every entry eligible (no turn exceeds 10,000), random.Random(20260930).sample 30 | 7842d7d960b4acb5d5b09614fbf5a2b06fe752407f766d8df57ddd02e1f0260c |
| DEMO1_LONGCTX_15 | long_context FULL, a turn > 10,000 (40 eligible), sample 15 | 7311610496286db6af4af8e98aa49723cdaaaf61d139d8c30d074358b18befdd |
| DEMO1_LONGCTX_OBSK1024_15 | long_context OBS_MASK K=1024, largest turn in (10,000, 18,500] (37 eligible), sample 15 | 3d6dc25f574019025a915c434ec4e7f284fca888e2e3935f0520b2385b939995 |
| DEMO1_LONGCTX_30 (v1) | kept | 7a71fa6ab4a649bdc18b2c994c9904e44f5667a680abadf2f79147f6ed2513cb |

Tooling gaps:
- V4 needs OBS_MASK in the live runner. It must mask the observations the
  local and the cloud model see, and record K in the plan. Estimate: about
  half a day of code plus tests (a hook at MultiTurnAgentSession's tool
  execute and at the shared cloud tool path).
- V4 does not need replay.
- Fallback if that isn't ready: a trace-driven replay of the SWE
  trajectories. Spec:
  - real cold local TTFT per turn, measured on each host by prefilling the
    logged n_ctx with the filler prompt;
  - the same routing rule (TTFT > 10 s, sticky);
  - cloud $ from logged tokens x $3.20 per M input;
  - the plan labeled "replay", with no quality.
  - Estimate: one day plus a host session per config.
  - Not built.

## 5. H1-CPU feasibility (200 entries, XPS CPU, RESIDENT)

Estimate:
- Start from d482c621's measured GPU local wall time per arm.
- Scale it by the sealed warm CPU/GPU time-to-action ratio: 3.61, from
  ac4e5472 (9.28/2.47 s at 4k, 11.19/3.24 s at 6k).
- Add the cold turn-0 CPU prefill, interpolated log-log over 7f232f86
  (to 2,000) and ac4e5472 (4,000: 59.5 s; 6,000: 99.5 s). That is 25.6 s at
  2,152 tokens and 63 s at 4,193.
- Cloud turn wall time is kept as measured.

| arm | GPU measured (local + cloud) | CPU estimate |
|---|---|---|
| slo_escalate | 1.17 h local | about 5.2 h (turn-0 local turn for all 200: 4.2 h, then about 1 h of cloud turns) |
| emission_escalate | 0.81 + 0.33 h | about 6.1 h |
| full_signal_bounceback | 0.82 + 0.18 h | about 6.0 h |
| local_only | (1.17 h all-local) | about 7.0 h |

The total is about 24 h. It cannot fit one 7200 s boot, nor four. A split
that fits:
- About 6,300 usable s per boot, after reboot, gates and C=3 canary
  calibration.
- Interleaved, all 4 arms take about 440 s per entry, so about 14 entries
  per boot and about 15 boots.
- Per arm, about 50-65 entries per boot, so about 4 boots per arm and about
  16 boots in total.

What it would need:
- An amendment to H1_CPU_PREREG that declares the chunking: entry ranges,
  per-boot gates and canary, and how the chunks combine.
- Runner support for --entry-offset/--entry-count; resume today is per
  artifact dir, not per boot.
- Any alternative, such as fewer entries, also needs an amendment. No change
  is made silently.

DEMO-1 V2 (30 entries, NON_RESIDENT, slo only) fits one boot: one cold CPU
local turn per entry, about 1-3 min, then cloud.
