> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** This artifact used a mock or scripted decision path (no live OpenAI agent). Use only to verify instrumentation and invariants. Do not cite in papers, slides, or findings.

# Tool-locality ablation (search local vs remote)

Generated: 2026-07-07T18:20:47.594827+00:00
Setup digest: `fe9707b03e17a5b7`

## Question

Does search push sessions into the CPU-heavy regime because search is inherently local compute, or because this harness implements search as an in-process 50 MB regex scan?

## Configuration

- Backend: `scripted`
- Seed: 0
- Tasks: SH-01
- Search locality arms: local (regex corpus) vs remote (mock HTTP + sleep)
- Retrieve locality: `local`
- Payload profile: `locality_ablation` (tool results padded to 4.0 KB max; identical across local/remote arms, does not affect TOOL_COMPUTE comparison)

- Comparison type: **matched_pair_live_model**

## Per-session results

| task | search | wall (s) | host CPU (ms) | TOOL_COMPUTE (ms) | HTTP_CLIENT (ms) | I/O % wall | CPU % wall | search calls |
|------|--------|----------|---------------|-------------------|------------------|------------|------------|--------------|
| SH-01 | local | 2.266 | 828.1 | 781.2 | 0.0 | 0.0 | 36.5 | 8 |
| SH-01 | remote | 3.881 | 46.9 | 0.0 | 15.6 | 69.8 | 1.2 | 8 |

## Local vs remote (paired delta)

| task | local CPU ms | remote CPU ms | Δ CPU ms | local TOOL ms | remote TOOL ms | Δ TOOL ms | local CPU% wall | remote CPU% wall | Δ CPU% wall |
|------|--------------|---------------|----------|---------------|----------------|------------|-----------------|------------------|-------------|
| SH-01 | 828.1 | 46.9 | -781.2 | 781.2 | 0.0 | -781.2 | 36.5 | 1.2 | -35.3 |

## Interpretation

Remote search moves tool body work from TOOL_COMPUTE (local regex scan) into HTTP_CLIENT envelope CPU plus I/O wait (time.sleep round trip). Search-heavy tasks (SH-*): mean CPU% of wall drops by -35.3 points when search is remote (n=1). Across all paired tasks: mean TOOL_COMPUTE delta -781.2 ms; mean CPU% of wall delta -35.3 points. Interpretation: search CPU in the baseline run is largely an artifact of in-process search locality, not a durable property of search-using agents when search is deployed as a remote service.

## Reproduce

```
python -m apu_characterization.experiments.tool_locality_ablation --backend scripted --seed 0 --tasks SH-01 --retrieve-locality local
```

## Invariant

Residual 0.0% (limit 15%) → PASS
