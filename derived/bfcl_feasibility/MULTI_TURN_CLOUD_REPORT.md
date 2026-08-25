# BFCL multi-turn local vs cloud

entries: 20
entry_ids: ["multi_turn_base_0", "multi_turn_base_1", "multi_turn_base_2", "multi_turn_base_3", "multi_turn_base_4", "multi_turn_base_5", "multi_turn_base_6", "multi_turn_base_7", "multi_turn_base_8", "multi_turn_base_9", "multi_turn_base_10", "multi_turn_base_11", "multi_turn_base_12", "multi_turn_base_13", "multi_turn_base_14", "multi_turn_base_15", "multi_turn_base_16", "multi_turn_base_17", "multi_turn_base_18", "multi_turn_base_19"]
entry_ids_match_pinned_file: True
entry_ids_match_gpu_report: True
checker: bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker
wrapper: apu_characterization.cap01.bfcl_cap01_multi_turn_checker

## Trajectory (official multi_turn_checker)
local 1/20
cloud 13/20

## Per-turn (official checker prefixes)
local 18/70
cloud 50/70
local_recoverable: True
cloud_recoverable: True

## First-failure turn distribution
local: {"0": 10, "1": 5, "2": 2, "3": 2, "none": 1}
cloud: {"0": 2, "1": 3, "2": 2, "none": 13}

id	local_first_failure_turn	cloud_first_failure_turn
multi_turn_base_0	0	None
multi_turn_base_1	1	None
multi_turn_base_2	0	None
multi_turn_base_3	1	None
multi_turn_base_4	2	2
multi_turn_base_5	0	1
multi_turn_base_6	0	1
multi_turn_base_7	1	None
multi_turn_base_8	2	2
multi_turn_base_9	0	0
multi_turn_base_10	0	1
multi_turn_base_11	1	None
multi_turn_base_12	None	None
multi_turn_base_13	0	None
multi_turn_base_14	3	None
multi_turn_base_15	3	None
multi_turn_base_16	0	None
multi_turn_base_17	0	None
multi_turn_base_18	0	0
multi_turn_base_19	1	None

## Spend
prompt_tokens_sum: 1687158
completion_tokens_sum: 23038
usd: 5.407044000000001
rates_usd_per_1M: in=3.0 out=15.0
