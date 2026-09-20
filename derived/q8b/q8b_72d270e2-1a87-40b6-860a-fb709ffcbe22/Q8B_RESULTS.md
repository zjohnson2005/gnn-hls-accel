# Q-8B results (int4-4B vs int4-8B, KV=f16, interleaved)

run_id: `72d270e2-1a87-40b6-860a-fb709ffcbe22`
pipeline_mode: `block_interleave_single_pipe`
session_wall_s: 12231.5337204
tree_sha256: `e51811f169e2ac90f9d00be7e79293ccd24f3a89dbdaf877fa739420efd2ce71`

## Tier note

Fixed weight precision **int4**. No `Qwen3-8B-int8-ov` in registry — not an int8 substitution. Quant recipe confound: 4B INT4_SYM vs 8B INT4_ASYM.

## Q-KV f16 baseline (cross-session absolute rates not comparable)

Cited for prediction context only: run `137f6f46-cd3a-42d5-8479-4ff46a1074f1` gpu_only_f16 emission failures 62/200, trajectory_pass 10/200.

## Per-arm emission and completion

| arm | emission failures | emission ok | trajectory_pass |
|---|---:|---:|---:|
| `int4_4B` | 64/200 | 136/200 | 10/200 |
| `int4_8B` | 13/200 | 187/200 | 29/200 |

## Paired McNemar — emission

### int4_4B__vs__int4_8B
2×2: both_pass=135, first_only=1, second_only=52, both_fail=12
McNemar: discordant=53, first_only=1, second_only=52, p=1.19904e-14

## Paired McNemar — completion

### int4_4B__vs__int4_8B
2×2: both_pass=6, first_only=4, second_only=23, both_fail=167
McNemar: discordant=27, first_only=4, second_only=23, p=0.000310749

## Verdict

- emission arms agree: **False**
- completion arms agree: **False**
- tier quality-axis hypothesis falsified: **False**

