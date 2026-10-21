# Entry 123: what the "hangs" were (Task BB part 1, 2026-10-21 ET)

This note corrects analysis/demo2_pilots/AY/GPU_HANG_ENTRY123.md. That file is
committed and is not edited.

The result in one line: "4 hangs on 2 devices" (and "silent stall on two GPUs")
was overstated. One record shows a long stall (841b84e4). One shows a turn over
its time budget while still progressing (8af10211). Three have no progress signal
at all (bbdd1c0d, 24c1abc0, 027a07b7).

## 1. T2S window 2026-10-21 (~/seam_closeout_1013/t2s/window_20261021_1209_hang/)
- Head 9d67c18, clean. GPU driver 32.0.101.8509. Rebooted at window start.
- Committed records: derived/demo2_pilots/p11_l1_9b4cdefb/,
  derived/demo2_pilots/p11_l2_8af10211/ and derived/demo2_pilots/windows_20261021/.

**L1, 9b4cdefb** (tools/repro_hang123.py, plain LLMPipeline, gold-path prompts):
- step 0 (2,189 tokens): 3.875 s;
- step 1 (34,050 tokens): 54.862 s;
- status complete, no hang.

**L2, 8af10211** (runner, arm A true default, -StepLog, 600 s per-turn watchdog,
UNSEALED). Turn 0 of 123, from step_log.jsonl (UTC):

| step | pre-generate | prompt | new (est.) | gap to next step |
|---|---|---|---|---|
| 0 | 16:16:05 | 2,189 | 2,189 | 4 s |
| 1 | 16:16:09 | 87,392 | 85,077 | 400 s |
| 2 | 16:22:49 | 87,959 | 55 | 59 s |
| 3 | 16:23:48 | 88,526 | 55 | 59 s |
| 4 | 16:24:47 | 89,093 | 55 | 59 s |
| 5 | 16:25:46 | 89,660 | 55 | (watchdog at 16:26:05.96) |

- The watchdog was armed at 16:16:04.94 and fired at 601.016 s (limit 600 s),
  about 20 s into step 5.
- seen_tokens_before shows each step from 1 to 4 generated 512 tokens
  (max_new_tokens), and each added a ~45-token tool result.
- The step texts were not recorded. --debug-raw-text writes them only when the
  turn ends, and this turn never ended.
- The script then stopped by design: stalling step 5 had no variant set. The
  T2S was rebooted (back in 72 s) and the hand-back check passed (no python of
  ours, tree clean).

## 2. The step-0 tool calls on the model's path (DERIVED; text NOT RECORDED)
The run did not record the call or its result. They are reconstructed here from
the sizes it did record. Method: every subset of plausible 123 calls was replayed
through the runner's render path on the Mac (BFCL executor, pinned HF tokenizer).
Only one call set matches all of these:
- step-0 output 125 text tokens + EOS = 126 generated
  (2,315 = 2,189 + 126);
- step-1 prompt exactly 87,392 tokens;
- 464 characters, the same length as L1's step-0 output on the same prompt
  (sha256 c409edc1...).

The calls, in one step-0 output (5 calls):
- get_account_info(): 46 tokens.
- get_stock_info(symbol="TSLA"): 31,665 tokens.
- get_transaction_history() with no dates: 49,314 tokens. This is the call gold
  does not make.
- get_available_stocks(sector="Technology"): 3,982 tokens.
- place_order(Buy, TSLA, amount 150, a price written with 5 characters, e.g.
  667.0): about 30 tokens.

So step 1 receives about 85,000 tokens of tool results, mostly the
unbounded-date transaction history plus the stock series. Gold step 1 is 34,050.

Not recovered:
- The exact price. Every 5-character price with the default JSON layout gives
  87,392, but none of 3.76 M tested variants matches L1's output sha256. So the
  text is not byte-recovered, and L1's output may differ from L2's.
- What steps 1-4 generated: 512 tokens each, with small tool results.
- The replay scripts are in the Task BB session scratchpad. The definition used
  for X3r is in tools/repro_hang123_variants.py (X3R_STEP0_CALLS).

## 3. Reclassification of every entry-123 "hang" record
| run | host | limit | evidence | class |
|---|---|---|---|---|
| 841b84e4 | XPS | none (stopped by hand) | No turn record for 3 h 17 min after the load. GPU 3D counter 0% at 9:31 PM ET; worker CPU rose 9,162 -> 9,986 s between ~9:13 and 9:31 PM (~0.75 core) | STALL |
| 24c1abc0 | XPS | 1,800 s per turn | No step log, no progress signal | UNKNOWN |
| 027a07b7 | XPS | 600 s, prefix caching off | No step log; every step re-prefills the whole prompt | UNKNOWN |
| bbdd1c0d | T2S | 600 s per turn | No step log. Same config and host as 8af10211, which was progressing at 600 s | UNKNOWN |
| 8af10211 | T2S | 600 s per turn | Steps 2-5 started 59 s apart; fired 20 s into step 5 | TURN_BUDGET_EXCEEDED_PROGRESSING |

Caveats on 841b84e4, the only STALL:
- The counter behind "GPU 3D 0%" was not recorded. Whether OpenCL compute work
  shows on the 3D engine on that driver is NOT YET MEASURED.
- DERIVED expectation for a progressing turn 0 on the XPS:
  - T2S turn 0 to the 21-step limit is ~26 min (step 1 400 s, then ~60 s per
    step);
  - matched steps above 40,960 ran 3.5-5.1x slower on the XPS (entry 117 t3s1
    388 s vs 110 s; 135 t1s1 533 vs 105; 138 t0s3 780 vs 197);
  - so XPS turn 0 is ~1.5-2.2 h. 841b84e4 went more than 1 h past that with no
    record. That is consistent with a stall, but it is not proof.
- 24c1abc0's 1,800 s is inside the DERIVED XPS step-1 time alone (400 s x
  3.5-5.1 = 1,400-2,040 s).

## 4. What the native stacks do and do not show
- 8af10211 was progressing, and its py-spy dump has the main thread "active" in
  igdrcl64.dll under ov::InferRequest::infer <- ContinuousBatchingPipeline::step.
- 027a07b7's dump has the same frames, also "active". 24c1abc0's is "idle" in
  NtGdiDdDDIWaitForSynchronizationObjectFromCpu.
- One sample of a thread that spends most of its time waiting on GPU work looks
  like either. So the AY reading "inside an OpenCL enqueue the CPU waits on a GPU
  sync object; the wait does not end" is withdrawn as evidence of a stall. The
  stack shows where the thread was, not that it stopped.

## 5. Corrections to GPU_HANG_ENTRY123.md (AY) and the AZ/BA framing
- Section 3 "a silent device stall": withdrawn for 24c1abc0 (UNKNOWN). It
  stands only for 841b84e4, with the caveats above.
- Section 3 "The prompt is short (2,189 tokens at step 0)": misleading. Step 1
  on the model's path is 87,392 tokens, 2.1x the model's 40,960 positions.
- Section 5, regime "silent device stall under the shipped default
  configuration": not established. What is established:
  - the default accepts prompts far past the model's positions with no error
    or warning;
  - at that size a turn can run for tens of minutes while still progressing.
- "4 of 4 attempts stalled, on 2 devices / 2 drivers" (AZ; CLAUDE.md, registry,
  P10-T2S note): overstated. It was 1 long stall (XPS), 1 progressing over
  budget (T2S), 3 unknown.
- P10 C1 "prefix caching off does NOT avoid the hang" (027a07b7) becomes "C1 did
  not finish turn 0 within 600 s". With prefix caching off every step
  re-prefills ~88k tokens, so 600 s cannot separate a stall from slowness.
  New dated note: docs/amendments/DEMO2_HANG_FRAMING_CORRECTION_2026-10-21.md.

## 6. What Claude told Zach that was wrong (chat level)
- The memory-thrash idea, i.e. that the 841b84e4 stall came from memory pressure
  or paging. The worker was not paging (22 pages/s, 3,019 MB available), and no
  memory signal was ever tied to the stop.
- "It hangs on the T2S too" (bbdd1c0d). bbdd1c0d has no progress signal, and the
  same setup on the same host (8af10211) was progressing at 600 s.
- "Silent stall on two GPUs" and "4 of 4 on 2 devices". Only the XPS 841b84e4
  record is a long stall.
- Implied by those: "the prompt is short, so size is not the cause". The model's
  own step 1 is 87,392 tokens.
