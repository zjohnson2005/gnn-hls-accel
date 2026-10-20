# LONGCTX hang, run 841b84e4 (XPS, 2026-10-19): facts and code read

Task AW, Mac only. Run record: derived/demo2_pilots/hung_841b84e4/ (UNSEALED
partial; README there). Every figure below is from that directory, its
evidence/ files, or a sealed run named with it. Nothing here is a cause:
the evidence does not identify one.

## 1. Timeline (ET, 2026-10-19)
- 5:18:59 PM launch (uptime 3,206 s); worker started 5:19 PM.
- 6:14:03 PM last telemetry row: entry multi_turn_long_context_121, turn 3,
  prompt 9,094 tokens. 14/30 entries complete, local pass 1/14 (entry 101).
- 6:14:08 PM last log write: the compiled-property dump of a pipeline load
  (PA, KV i8, CACHE_DIR empty, last line "[XAttention]: DISABLED on GPU
  device."). seam/genai_runtime.capture_native_output writes that dump to the
  log only after the load returns, so the load for the next entry finished.
- Next entry in pin order: multi_turn_long_context_123. No turn of 123 was
  written (the runner writes a telemetry row at the end of each turn).
- 9:20 PM the window script stopped waiting; 9:31 PM Zach stopped the worker.

## 2. Host counters while stalled
| sample (ET) | source | worker CPU s |
|---|---|---|
| 7:43 PM | Zach (chat; not in the copied files) | 4,986 |
| ~9:13 PM | evidence/longctx_status.txt | 9,162.0 |
| ~9:29 PM | evidence/longctx_stall.txt | 9,886.9 |
| 9:31 PM | evidence/longctx_kill.txt | 9,985.6 |

- CPU rate: 7:43 to 9:13 PM about 0.76 cores; 9:13 to 9:29 PM about 0.75;
  9:29 to 9:31 PM about 0.8 (file times; sample times are to the minute).
  The 1.4-core figure in the task prompt does not follow from these samples.
  At about 0.8 of one core on 8 logical CPUs, the worker used about 10% of
  the CPU.
- 9:31 PM: GPU 3D utilization 0% (6 x 5 s samples), 22 pages/s, pagefile
  18%. ~9:29 PM: available memory 3,019 MB, worker working set 7,391 MB,
  commit 10,992 MB.
- Reading: the worker was busy on the CPU with the GPU idle, and there was
  no paging storm. The memory-thrash explanation raised in chat is NOT
  supported by these counters. For scale, in this same run, entry 101's
  turn 0 saw 767.6 MB available and entries 112-117 saw 1,112-1,923 MB. All
  of them completed, so 3,019 MB was not low for this run.

## 3. (a) Entry 123 as the runner sees it
Built on the Mac with the runner's own path:
- tools.h1_context_sizing.size_entry, which drives the probe's
  MultiTurnAgentSession and render_bfcl_tools_style.
- Qwen3-4B HF tokenizer from OpenVINO/Qwen3-4B-int4-ov b467368d.
  tokenizer.json aeb13307..., tokenizer_config.json 443bfa62...,
  chat_template.jinja a55ee1b1..., all matching the pinned sha256.
- bfcl-eval 2025.12.17, transformers 5.19.0, tokenizers 0.23.3.
- No model load.

Results:
- Turn 0, step 0 prompt: **2,189 tokens**, 20 tools (TradingBot: add_to_watchlist,
  cancel_order, filter_stocks_by_price, fund_account, get_account_info,
  get_available_stocks, get_current_time, get_order_details,
  get_order_history, get_stock_info, get_symbol_by_name,
  get_transaction_history, get_watchlist, notify_price_change, place_order,
  remove_stock_from_watchlist, trading_get_login_status, trading_login,
  trading_logout, withdraw_funds).
- Expected calls, turn 0: get_account_info(), get_stock_info(symbol='TSLA'),
  place_order(order_type='Buy', symbol='TSLA', price=667.92, amount=150).
  Under long_context, get_stock_info returns 31,665 tokens (31,705 chars of
  MA(5)/MA(20) lists), so the gold step 1 prompt is 34,050 tokens.
- Turns 1-3: get_order_details(order_id=12446), cancel_order(order_id=12446),
  trading_logout(). Gold max n_ctx 35,821.
- These match the committed sizing
  derived/h1_hybrid/demo1/SIZING_multi_turn_long_context.json entry by entry.
- Nothing in size or class sets 123 apart from entries that completed in this
  run:
  - 10 of the 14 completed entries are TradingBot entries that called
    get_stock_info, get_watchlist or get_available_stocks (8 called
    get_stock_info).
  - 7 ran step-0 prompts of 34,066-43,961 tokens with step TTFT up to
    418.9 s, and completed.

## 4. (b) What in the runner can run with no GPU work and no telemetry
Code read at eddc760 (the run's commit), path
OpenVinoLocalBackend.begin_entry -> run_turn ->
MultiTurnAgentSession.run_user_turn (tools/bfcl_feasibility_probe.py):
- Step loop: bounded. Every pass either breaks or does `step += 1`, and the
  loop breaks at step > MAXIMUM_STEP_LIMIT (20), so at most 21 generates per
  turn. The only `continue` paths (feedback retry, empty retry, exec retry)
  need a P1 controller, and this run has none.
- Per-step Python work: render_bfcl_tools_style plus HF tokenization of the
  full prompt, a second render and tokenization of the GenAI chat history
  (RESIDENT), a JSON deep copy of the history, and on the first step
  assert_first_turn_token_equivalence. All are linear in the prompt and run
  once per step. In this run the per-turn maxima were t_tokenize 0.27 s,
  t_template_build 0.02 s, t_tool_exec 0.01 s and t_other 0.08 s (turn
  ledger), at prompts up to 43,961 tokens.
- Tool execution: BFCL execute_multi_turn_func_call evals call strings that
  convert_to_function_call builds from JSON arguments (literals only). The
  TradingBot methods have no unbounded loops (func_source_code/trading_bot.py),
  and an exception is caught and recorded. Bounded.
- Tool-call regexes: TOOL_CALL_RE / TOOL_CALL_RE_QWEN are non-greedy over at
  most 512 generated tokens. Bounded.
- Telemetry sampler (seam/turn_memory.py): its thread waits 0.1 s per loop.
  The GPU counter subprocess has a 15 s timeout and the joins have 5 s
  timeouts. Bounded.
- Streamer (_TtftStreamer.write) always returns RUNNING and has no loop.
- Scoring (session.finish) runs at entry end, which entry 123 never reached.
- Retry loops: none active in this configuration.
- **pipe.generate (OpenVINO GenAI, native)** has no timeout and no bound in
  our code other than max_new_tokens 512. It is the one unbounded call in the
  window between "load returned" and "turn 0 written". Inside it are chat
  template rendering, tokenization, the scheduler, prefill, decode and
  detokenization.

Conclusion from the code: the stall was inside pipe.generate, or in the
bounded Python steps if one of them misbehaved in a way the code does not
show. The counters (CPU busy, GPU idle) fit a CPU-side wait or loop inside
generate. They do not prove one. A native stack dump at the next occurrence
(section 6) is what would decide.

## 5. (c) Has any sealed run executed entry 123?
No.
- DEMO-1 v1 (5 configs on DEMO1_LONGCTX_30) was superseded on 2026-10-12
  before any run (registry change table).
- The v2 long-context cells (V3, V4) ran DEMO1_PAIRED_15, which does not
  contain 123.
- DEMO1_LONGCTX_15 contains 123 but no sealed cell ran it.
- A search of derived/ and analysis/ finds 123 only in pins, meta files,
  sizing and atlas tables (gold trajectories, no model).
So there is no earlier live run of 123 under any configuration to compare
with.

## 6. (d) Watchdog (built in Task AW; harness change, not a rule change)
- seam/turn_watchdog.py, runner flags --turn-watchdog-s and --hang-dump-py-spy,
  launch_h1 -TurnWatchdogS / -HangDumpPySpy. Default off. With the flags off,
  plans and ledgers are unchanged (tested).
- When one local turn runs longer than the limit, the watchdog:
  1. writes hang_events.json with outcome "hang" (entry, policy, turn,
     elapsed, limit, pid);
  2. dumps every Python thread's stack (faulthandler);
  3. if a py-spy path is given, runs `py-spy dump --native --pid <worker>`
     (120 s timeout);
  4. marks the policy aborted_hang with a quality row of outcome "hang", and
     writes the checkpoints and a summary with status aborted_hang;
  5. exits with code 86.
- The stalled call is native and cannot be cancelled from Python, so
  "moving on" is the next launch at the next entry.
- Limit for the next window: 1,800 s, about 3.8 x the longest measured
  local turn (469.4 s, entry 112 turn 1, this run).
- Known limit: if the native call holds the GIL, the watchdog thread cannot
  run. The faulthandler dump and the exit would then not happen, and the
  window script's 4 h wait stays the backstop. py-spy reads the process from
  outside and needs no GIL.

## 7. Addendum 2026-10-20 (Task AX): full worker log and launch evidence
- Both are now in derived/demo2_pilots/hung_841b84e4/evidence/. The launch
  evidence matches plan.json (3/3).
- The log ends with CELL_START for entry 123 and its 99-line load dump. That
  dump is byte-identical to entry 121's.
- No WARN, error, exception or fallback line appears anywhere in the log.
- Nothing more about 123 is in the log: the runner does not log per turn.
  Section 1's reading stands.
