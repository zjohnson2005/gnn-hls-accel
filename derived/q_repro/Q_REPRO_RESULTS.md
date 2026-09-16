# Q-REPRO results

run_id: `6dd387aa-7575-401f-a4ed-ed53ca1bf1ef`
session_wall_s: 9347.1910967
tree_sha256: `ca30dba6f8159daa0d372ae198b1c0887b9ef0fffe053322cac470730f98d6df`

## Seal diff (pre-run)

See `derived/q_repro/SEAL_DIFF_6225d6e1_vs_137f6f46.md`.

## Per-arm

| arm | emission failures | trajectory_pass |
|---|---:|---:|
| `gpu_only` | 61/200 | 14/200 |
| `gpu_only_f16` | 59/200 | 11/200 |

W-3 baseline: 45 failures, 20 completions.
Q-KV f16: 62 failures, 10 completions.

Arm A KV readback normalized counts: {'dynamic': 200}

**Outcome class:** `A_like_QKV_f16_W3_does_not_reproduce`

## Paired McNemar

### emission gpu_only__vs__gpu_only_f16
2x2: both_pass=121, first_only=18, second_only=20, both_fail=41
McNemar: discordant=38, p=0.871415

### completion gpu_only__vs__gpu_only_f16
2x2: both_pass=6, first_only=8, second_only=5, both_fail=181
McNemar: discordant=13, p=0.581055

Interpretation: W-3 does not reproduce. Quality instrument is not stable across sessions; sealed quality numbers (including emission OR 4.57 from 6225d6e1/1d8db970) need a stability statement before the paper.
