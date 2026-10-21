# 8af10211: P11 L2, arm A on entry 123 alone with -StepLog (T2S, 2026-10-21), UNSEALED

run_id 8af10211-c517-4fe5-9281-42800edf0278. EVO-T2S (evo-t2), GPU driver
32.0.101.8509, head 9d67c18 clean, launched 12:14:52 PM ET (uptime 290 s).
- Flags: local_only, gpu_only, RESIDENT, --kv default, --require-true-default,
  --step-log, --debug-raw-text, --mem-telemetry, --gpu-mem-counters,
  --turn-watchdog-s 600, py-spy.
- Entry DEMO1_LONGCTX_30 index 14 (multi_turn_long_context_123). $0.
- Launch evidence: 3/3 files match plan.json by bytes and sha256.

What happened (step_log.jsonl):
- Turn 0 step 0 prompt 2,189 tokens.
- Step 1: 87,392 tokens (85,077 new), 400 s.
- Steps 2-5: +567 tokens each, started 59 s apart.
- The per-turn watchdog fired at 601.016 s, about 20 s into step 5 (outcome
  "hang" in the files, exit 86).
- Reclassified TURN_BUDGET_EXCEEDED_PROGRESSING in
  analysis/demo2_pilots/BB/ENTRY123_RECLASSIFIED.md.

Not sealed (hang path). interleaved_*/ is a byte copy of what the run wrote
(parked, copied to the Mac). evidence/ holds:
- the launch evidence dir;
- the launch output, the 160-line log tail and the full worker log;
- the park record and the watchdog launch-check.
