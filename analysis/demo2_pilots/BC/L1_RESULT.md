# Ladder L1 result: K = 1,024, shape h70t30 (Task BC, 2026-10-21 ET)

Rule registered in docs/amendments/DEMO2_ARMS_REVISED_2026-10-21.md (commit
17a102e) before this run. Mac, no model, $0.

Record: derived/demo2_ladder/L1/l1_replay.json, sha256
a5cbad8210798da426b7c917f8536ff8a1587cde1d944ece412c3b7a735d2188. Run at
17a102e with tools/demo2_ladder_l1.py, bfcl_eval 2025.12.17, pinned tokenizer
(tokenizer.json aeb13307..., tokenizer_config.json 443bfa62...).

Scope:
- 280 entries: multi_turn_base and multi_turn_long_context, minus the 120 ids
  of DEMO2_HELDOUT_60 and _B.
- 406 required values in 175 entries.
- FULL tool-output tokens: 1,583,672. The largest gold observation is 31,666
  tokens (get_stock_info). Gold never calls the 49k-85k
  get_transaction_history blob.

| K | shape | values lost | kept share of FULL tokens |
|---|---|---|---|
| 512 | head | 1 | 0.092 |
| 512 | h70t30 | 4 | 0.092 |
| 512 | json | 12 | 0.079 |
| 1024 | head | 0 | 0.156 |
| **1024** | **h70t30** | **0** | **0.156** |
| 1024 | json | 1 (162: 420.0) | 0.136 |
| 2048 | head | 0 | 0.245 |
| 2048 | h70t30 | 0 | 0.245 |
| 2048 | json | 0 | 0.243 |

Decision by the rule: K = 1,024, shape h70t30. It is the smallest K with a
choosable shape at 100%; head is never chosen. In arm C (section 2 of the
amendment) this replaces K = 2,048 json:
-RetentionK 1024 -RetentionShape h70t30.

Notes:
- JSON-aware is not better than 70/30 here: at 1,024 it loses one value
  (entry 162, an exchange-rate argument 420.0) that 70/30 and head keep.
- The registered predictions used the K2048 atlas proxy and are not changed.
  K = 1,024 can only lower C's payload further, so the registered C
  prediction is conservative on this term (DERIVED, not re-priced).
- The required-value test is a heuristic (text match of gold argument values
  of >= 3 characters in earlier tool outputs, not in user text). It says
  nothing about values the model needs but gold does not pass as arguments.
