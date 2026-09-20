# R2b-on-8B predictions (INF-6 / R2B8B-PREP)

**Status:** `pre_registered_before_measurement`  
**Registered UTC:** 2026-09-20T16:47:38.513754+00:00  
**Do not edit after the first probe starts.**

## Invoke

```text
powershell -NoProfile -File tools/launch_h1.ps1 -Policy emission_escalate -ModelSpec configs/models/Qwen3-8B-int4-ov.yaml
```

## Basis

| prior | value |
|---|---|
| R2b 4B (`8ffd8371`) | **$17.47**, **65** escalations |
| cost vs n_cloud_turns | R² = **0.64** |
| cost vs context-at-escalation | R² = **0.001** |
| Q-8B (`72d270e2`) emission failures | **13** (vs 4B **64**) |

## Predictions

| id | claim | falsified if |
|---|---|---|
| P1 | ~**13** escalations | > **25** |
| P2 | ~**$3.50** cloud | > **$8** |
| P3 | completion ~**37**/200 (29 local + ~65% of 13 rescued) | forensic; P1/P2 primary |

Derivation P2: $17.47/65 ≈ $0.269/esc × 13 ≈ $3.50.
