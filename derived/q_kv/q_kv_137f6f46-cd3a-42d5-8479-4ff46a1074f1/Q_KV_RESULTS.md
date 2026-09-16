# Q-KV results

run_id: `137f6f46-cd3a-42d5-8479-4ff46a1074f1`
session_wall_s: 14046.808005799998
tree_sha256: `485b6ef08121117ae2758ee0e779a36b9c38069fc7fe08c860549541b597ced4`

## W-3 unset KV

Readback in seal 6225d6e1: **dynamic** (requested=None, enforced=False). Treated as unknown precision, not f16.

## Per-arm emission and completion

| arm | emission failures | emission ok | trajectory_pass |
|---|---:|---:|---:|
| `gpu_only_f16` | 62/200 | 138/200 | 10/200 |
| `gpu_only_u8` | 65/200 | 135/200 | 13/200 |
| `gpu_only_u4` | 71/200 | 129/200 | 11/200 |

## Paired McNemar — emission

### gpu_only_f16__vs__gpu_only_u4
2×2: both_pass=116, first_only=22, second_only=13, both_fail=49
McNemar: discordant=35, first_only=22, second_only=13, p=0.175465

### gpu_only_f16__vs__gpu_only_u8
2×2: both_pass=120, first_only=18, second_only=15, both_fail=47
McNemar: discordant=33, first_only=18, second_only=15, p=0.728332

### gpu_only_u8__vs__gpu_only_u4
2×2: both_pass=117, first_only=18, second_only=12, both_fail=53
McNemar: discordant=30, first_only=18, second_only=12, p=0.361595

## Paired McNemar — completion

### gpu_only_f16__vs__gpu_only_u4
2×2: both_pass=6, first_only=4, second_only=5, both_fail=185
McNemar: discordant=9, first_only=4, second_only=5, p=1

### gpu_only_f16__vs__gpu_only_u8
2×2: both_pass=6, first_only=4, second_only=7, both_fail=183
McNemar: discordant=11, first_only=4, second_only=7, p=0.548828

### gpu_only_u8__vs__gpu_only_u4
2×2: both_pass=7, first_only=6, second_only=4, both_fail=183
McNemar: discordant=10, first_only=6, second_only=4, p=0.753906

## Verdict

- emission arms agree (falsify KV-emission): **True**
- completion arms agree: **True**
- KV quality-axis hypothesis falsified: **True**

## H-1 headline config

Recommended KV arm for H-1 local quality: **`gpu_only_f16`** (rank by emission_ok, then trajectory_pass, then denser KV as tie-break).
- u8 emission failures: 65/200; completion 13/200
- u4 emission failures: 71/200; completion 11/200

## u8-dominated-by-u4 pruning

u4 significantly worse emission than u8 (McNemar): **False** (p=0.361595, u8_only=18, u4_only=12)
u4 significantly worse completion than u8 (McNemar): **False** (p=0.753906)
**Pruning survives: True** (survives only if u4 is not significantly worse than u8 on emission or completion).

## Predictions vs measured

Predicted failures f16/u8/u4: 45 / 65 / ≥65; measured: 62 / 65 / 71.
Predicted completion f16/u8/u4: 20 / 14 / ≤14; measured: 10 / 13 / 11.
