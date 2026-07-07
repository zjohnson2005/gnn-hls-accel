> **Publishable run.** Live OpenAI API agent decisions (`--backend openai`). Numbers below may be used in research outputs subject to the usual caveats in the report (tick resolution, wall-time partitioning, small-base sessions).

# Tool-locality ablation (search local vs remote)

Generated: 2026-07-07T17:38:38.200013+00:00
Setup digest: `fe9707b03e17a5b7`

## Question

Does search push sessions into the CPU-heavy regime because search is inherently local compute, or because this harness implements search as an in-process 50 MB regex scan?

## Configuration

- Backend: `openai`
- Seed: 0
- Tasks: SH-01, SH-02, CH-02, RE-02, RH-01
- Search locality arms: local (regex corpus) vs remote (mock HTTP + sleep)
- Retrieve locality: `local`
- Payload profile: `locality_ablation` (tool results padded to 4.0 KB max; identical across local/remote arms, does not affect TOOL_COMPUTE comparison)

## Per-session results

| task | search | wall (s) | host CPU (ms) | TOOL_COMPUTE (ms) | HTTP_CLIENT (ms) | I/O % wall | CPU % wall | search calls |
|------|--------|----------|---------------|-------------------|------------------|------------|------------|--------------|
| CH-02 | local | 4.364 | 0.0 | 0.0 | 0.0 | 99.6 | 0.0 | 0 |
| CH-02 | remote | 4.466 | 140.6 | 31.2 | 31.2 | 98.7 | 3.1 | 0 |
| RE-02 | local | 7.915 | 46.9 | 0.0 | 0.0 | 99.7 | 0.6 | 0 |
| RE-02 | remote | 5.739 | 15.6 | 0.0 | 15.6 | 105.9 | 0.3 | 2 |
| RH-01 | local | 8.528 | 46.9 | 15.6 | 0.0 | 99.5 | 0.5 | 0 |
| RH-01 | remote | 8.086 | 125.0 | 0.0 | 15.6 | 99.5 | 1.5 | 0 |
| SH-01 | local | 9.241 | 2265.6 | 2140.6 | 15.6 | 75.9 | 24.5 | 3 |
| SH-01 | remote | 7.613 | 46.9 | 0.0 | 15.6 | 108.0 | 0.6 | 3 |
| SH-02 | local | 12.969 | 4578.1 | 4515.6 | 15.6 | 62.8 | 35.3 | 4 |
| SH-02 | remote | 7.092 | 46.9 | 0.0 | 31.2 | 115.1 | 0.7 | 4 |

## Local vs remote (paired delta)

| task | local CPU ms | remote CPU ms | Δ CPU ms | local TOOL ms | remote TOOL ms | Δ TOOL ms | local CPU% wall | remote CPU% wall | Δ CPU% wall |
|------|--------------|---------------|----------|---------------|----------------|------------|-----------------|------------------|-------------|
| CH-02 | 0.0 | 140.6 | 140.6 | 0.0 | 31.2 | 31.2 | 0.0 | 3.1 | 3.1 |
| RE-02 | 46.9 | 15.6 | -31.3 | 0.0 | 0.0 | 0.0 | 0.6 | 0.3 | -0.3 |
| RH-01 | 46.9 | 125.0 | 78.1 | 15.6 | 0.0 | -15.6 | 0.5 | 1.5 | 1.0 |
| SH-01 | 2265.6 | 46.9 | -2218.7 | 2140.6 | 0.0 | -2140.6 | 24.5 | 0.6 | -23.9 |
| SH-02 | 4578.1 | 46.9 | -4531.2 | 4515.6 | 0.0 | -4515.6 | 35.3 | 0.7 | -34.6 |

## Interpretation

Remote search moves tool body work from TOOL_COMPUTE (local regex scan) into HTTP_CLIENT envelope CPU plus I/O wait (time.sleep round trip). Search-heavy tasks (SH-*): mean CPU% of wall drops by -29.2 points when search is remote (n=2). Across all paired tasks: mean TOOL_COMPUTE delta -1328.1 ms; mean CPU% of wall delta -10.9 points. Interpretation: search CPU in the baseline run is largely an artifact of in-process search locality, not a durable property of search-using agents when search is deployed as a remote service.

## Reproduce

```
python -m apu_characterization.experiments.tool_locality_ablation --backend openai --seed 0 --tasks SH-01,SH-02,CH-02,RE-02,RH-01 --retrieve-locality local
```

## Invariant

Residual 0.0% (limit 15%) → PASS
