> **Publishable run.** Live OpenAI API agent decisions (`--backend openai`), real open-source tool bodies, audit PASS, Linux-resolution platform (or replication n≥5). Numbers may be used in research outputs subject to denominators and deployment caveats in VERIFIABLE_DATA.md and ATTRIBUTION.md.

# Bare-metal validation subset (platform: native_vm)

Generated: 2026-07-08T17:50:50.376605+00:00
Git commit: `8b84ddfa0236b8e073b4a822c95ffd65312be3f5` (dirty: yes)
Kernel: `6.8.0-124-generic`

Matched c=1 subset of the v3.1 replication configuration. Compare with
`python apu_characterization/tools/bare_metal_compare.py` which writes
`out/bare_metal_comparison.md` with the verdict.

## Per-task medians

| task | n | host CPU ms | LLM wait s | TOOL % | TPOOL % | FRMW % | ORCH_d % | RESID % |
|------|---|-------------|------------|--------|---------|--------|----------|---------|
| LH-01 | 3 | 523.8 | 17.62 | 39.2 | 3.7 | 9.1 | 11.2 | 0.0 |
| RH-01 | 3 | 161.7 | 7.41 | 46.1 | 32.2 | 5.4 | 3.8 | 0.0 |
| FO-01 | 3 | 79.5 | 7.94 | 0.0 | 28.3 | 20.2 | 8.8 | 8.0 |
| RE-01 | 3 | 48.6 | 10.20 | 4.2 | 14.3 | 12.3 | 28.1 | 0.0 |
| CH-01 | 3 | 35.2 | 3.86 | 6.4 | 16.5 | 11.0 | 17.2 | 0.0 |
| LH-02 | 3 | 8.3 | 4.77 | 0.0 | 0.0 | 8.4 | 0.0 | 0.0 |

## Residual gate (15% per session)

| session | residual ms | residual % | pass |
|---------|-------------|------------|------|
| CH-01_s0 | 0.00 | 0.0 | PASS |
| CH-01_s1 | 0.00 | 0.0 | PASS |
| CH-01_s2 | 0.00 | 0.0 | PASS |
| FO-01_s0 | 6.77 | 8.5 | PASS |
| FO-01_s1 | 3.80 | 1.6 | PASS |
| FO-01_s2 | 6.12 | 8.0 | PASS |
| LH-01_s0 | 0.00 | 0.0 | PASS |
| LH-01_s1 | 0.00 | 0.0 | PASS |
| LH-01_s2 | 1.97 | 0.4 | PASS |
| LH-02_s0 | 0.00 | 0.0 | PASS |
| LH-02_s1 | 0.00 | 0.0 | PASS |
| LH-02_s2 | 0.00 | 0.0 | PASS |
| RE-01_s0 | 0.00 | 0.0 | PASS |
| RE-01_s1 | 1.23 | 0.6 | PASS |
| RE-01_s2 | 0.00 | 0.0 | PASS |
| RH-01_s0 | 0.00 | 0.0 | PASS |
| RH-01_s1 | 0.00 | 0.0 | PASS |
| RH-01_s2 | 0.00 | 0.0 | PASS |

## Load hygiene

- 1-min loadavg range across run: 0.002 to 0.088 (start limit 1.0, abort limit 2.0)

Reproduce: `python -m apu_characterization.experiments.bare_metal_validation --backend openai --seeds 0,1,2`
