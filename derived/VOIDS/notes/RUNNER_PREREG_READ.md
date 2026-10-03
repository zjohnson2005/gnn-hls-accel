# Runner read of CAP3_PREDICTIONS.json

This note is not a void. The attached prediction block did not change the run.

## What happened

`tools/ttft_slo_predictions.py` `resolve_ttft_slo_plan_predictions` opened `derived/cap3/CAP3_PREDICTIONS.json` when the model-spec filename matched an arm (`Qwen3-8B-int4-ov.yaml` to `arm1_8b_int4`, `Qwen3-4B-int8-ov.yaml` to `arm2_4b_int8`). The match used the model-spec name only, not the KV arm. `tools/run_c1_ceiling.py` called that function for `--criterion ttft_slo` and stored the returned object on the plan and the summary.

The file's status is `pre_registered_before_measurement`. Runners must not open it. Scoring attaches predictions after the run.

## METADATA_ONLY

The returned object is not read again. In `tools/run_c1_ceiling.py` it is assigned at lines 869-877 and written only as `pre_registered_predictions` at lines 914, 1015, 1060, 1153, 1201, 1259, and 1347.

Search bounds, step, and repeats come from the command arguments (`args.low`, `args.high`, `args.resolution`, `args.repeats`) at lines 902-911, 978-981, and 1109-1112. The SLO timeout comes from `derive_probe_timeout_s` at lines 862-867. The canary guard is constructed at line 986 and consulted at lines 1002, 1117, and 1352-1359. Stop and abort use that guard and the arm results. `_eval_ttft_agreement` (lines 501-549), called at line 1303, uses arm results and `args.resolution`. The non-TTFT `primary_prediction_held` at line 1317 uses the completion ceilings and `args.resolution`.

The nested `search` object inside the CAP3 block is stored and not applied. `56c116a6` searched `low_init` 14000, `high_init` 26000. The attached `arm1_8b_int4` invoke is Low 3000, High 10000. `322b2f86` searched 3000-5500, not the file's 3000-10000. `69234ed5` searched 2000-8000. `a427233b` searched 4000-17000. `fea55e0c` searched 7000-12000, which matches that file's invoke line, and those bounds still came from the arguments.

Finding: METADATA_ONLY.

## Runs whose summary attached the file

Sealed and unsealed copies of the same four sessions. "Matched the arm" means the CAP3 `arm` field is `gpu_only_f16` and the run's arm is `gpu_only_f16`.

| run | attached | run arm | model | arm match |
|---|---|---|---|---|
| 322b2f86 | arm1_8b_int4, gpu_only_f16, P1 band [4000, 7000] | gpu_only_f16 | Qwen3-8B-int4-ov | yes |
| 69234ed5 | same arm1_8b_int4 block | gpu_only_u8 | Qwen3-8B-int4-ov | no (model only) |
| fea55e0c | arm2_4b_int8, gpu_only_f16, P1 band [7000, 9750] | gpu_only_f16 | Qwen3-4B-int8-ov | yes |
| a427233b | same arm2_4b_int8 block | gpu_only_u8 | Qwen3-4B-int8-ov | no (model only) |
| 56c116a6 | arm1_8b_int4, gpu_only_f16, P1 band [4000, 7000] | gpu_only_u8 | Qwen3-8B-int4-ov | no (model only) |

`56c116a6` is the T2S parity copy. Its CAP3 band is not a prediction for that cell and is not scored.

Checked and not this attachment:

- 051d2681: summary has no `predictions_path`. Source is the inline C-2 block (`docs/README_characterizations.md` Finding 2 / sealed 41e419bd).
- 5c714535: same, no `predictions_path` field.
- c2246b1f: `predictions_path` is null. Same inline source.

Plan files only (the summary does not carry the path): `q8b_b1a291f0` and `q8b_72d270e2` point at `Q8B_PREDICTIONS.json`; `q_repro_6dd387aa` points at `Q_REPRO_PREDICTIONS.json`; `q_kv_137f6f46` points at `Q_KV_PREDICTIONS.json`.

## Fix

`b8b1763298d8c83c4a95ecff7c22242f32988f91`. `resolve_ttft_slo_plan_predictions` no longer opens a file. It returns the inline C-2 block with `predictions_path` null. `tests/test_parity_remeasure_prereg.py` fails if any `derived/**` file whose name contains PREDICTIONS, PREREG, or AMEND is opened, including the 8B model-spec path that used to open CAP3.
