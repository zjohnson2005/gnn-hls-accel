# 9b4cdefb: P11 L1 repro of entry 123 turn 0, gold path (T2S, 2026-10-21)

run_id 9b4cdefb-8658-4cf3-8b9c-88aa7a7c5306. EVO-T2S (evo-t2), GPU driver
32.0.101.8509, head 9d67c18 clean, launched 12:13:27 PM ET at uptime 205 s
(~/seam_closeout_1013/xps/run_window_t2s_hang.sh as run, copy in
../windows_20261021/scripts/).
- tools/repro_hang123.py run on derived/repro_hang123/inputs_e123_t0.json
  (sha256 d12142f8...), plain LLMPipeline(model, "GPU"), greedy, max_new_tokens 512.
  The per-generate watchdog was 600 s, with py-spy.
- Step 0 (2,189 tokens): 3.875 s, output 464 chars, sha256 c409edc1...
- Step 1 (34,050 tokens): 54.862 s, output 552 chars.
- Status: complete, no hang.

No seal mechanism exists for repro runs. These are byte copies of run.json and of
the launch, log, park and watchdog-check records. Analysis:
analysis/demo2_pilots/BB/ENTRY123_RECLASSIFIED.md.
