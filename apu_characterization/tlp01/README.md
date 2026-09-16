# TLP-01 — limits of turn-level parallelism (v2)

Trace-driven limit study with two independent claim tracks:

1. **Ceiling** (M1/M2/M3): how much TLP exists under oracle/width/floor assumptions  
2. **Frontier** (M4 phase diagram): speculation policy × misprediction-penalty economics  

Protocol: `protocol_tlp01_v2.json`. Methodology: `../METHODOLOGY_TLP01.md`.
Promotion one-pager: `../PROMOTION_SUMMARY.md`.

## Keep from v1 / new in v2

| Item | Status |
|---|---|
| T0 traces, T1 S/C/J graphs, M0–M3, M5 | Kept |
| M4 predictor (Markov next-tool) | Migrated; reused by phase diagram |
| Policy × penalty phase diagram | **New flagship** |
| Bystander contention | **New secondary** |
| "Nobody harvests TLP" framing | **Retired** (died-ledger #2) |
| Single claim ladder | **Superseded** by ceiling + frontier tracks |

## Lifecycle

1. Freeze schema (in protocol).  
2. T0 S1 extract + S2 multi-tool live traces → lock.  
3. T1 dependence DAGs (G-D, G-A).  
4. **G-V must PASS** before any counterfactual.  
5. Ceiling ladder M1/M2/M3; frontier phase diagram; M5 at optimal policy.  
6. Report both rung tracks + related-work citations.

```bash
# Contract gate (no live data)
make tlp-gate

# T0: freeze schema → S1 extract → S2 live collect → close-out
python apu_characterization/tools/freeze_tlp01_schema.py
python apu_characterization/tools/extract_tlp01_s1.py
# Windows: .\apu_characterization\run_tlp01_s2_collect.ps1
python apu_characterization/tools/close_tlp01_t0.py
# Artifacts: out/tlp01/traces/{S1,S2,manifest.json,t0_collection_report.md}

# Debug smoke (synthetic; not quotable)
python -m apu_characterization.tlp01.runner --synthetic-debug

# T1: dependence graphs on frozen T0 (no T2)
python apu_characterization/tools/run_tlp01_t1.py
# Artifacts: out/tlp01/dependence_graphs/{index.json,t1_graph_report.md,...}

# T2: M0–M5 ladder (eligible task_ids only; sparse S1 excluded from bands)
python apu_characterization/tools/run_tlp01_t2.py
# Artifacts: out/tlp01/t2/{t2_ladder_report.md,aggregate.json}

# Full offline runner (also enforces replication floor)
python -m apu_characterization.tlp01.runner \
  --traces apu_characterization/out/tlp01/traces \
  --out apu_characterization/out/tlp01
```

## Validity

`turn_level_parallelism`. S/C brackets only. M1 not achievable. Tier-J never
in headlines. Praetor 20 µs = Tier D position only (boundary location is A/B).
Never "first to parallelize" / "nobody harvests TLP".
