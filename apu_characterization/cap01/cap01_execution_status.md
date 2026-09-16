# CAP-01 execution status

Date: 2026-07-14  
Protocol template: `cap01/protocol_cap01_v2.json`  
Authoritative docs: `METHODOLOGY_CAP01.md`, `PREDICTIONS_CAP01.md`, `cap01/cap01_verification_audit.md`

## Stage results

| Stage | Result | Notes |
|---:|---|---|
| 1 Rust audit re-runs (Axes 1/3/4/5) | **PASS** | All three harnesses measured. G8 DOMAIN rows include Rust; G3 20×3 three-harness; Axis 4 lag recorded as below_measurement_resolution on WSL; Axis 5 harness-consistent. |
| 2 P0 corpus | **PARTIAL (debug fixtures)** | 250-task synthetic private corpus frozen at `out/cap01/corpus.json`. Scope exclusions for BFCL Multi-Turn / BIRD interactive recorded. **Not** licensed BFCL/BIRD/HumanEval+/MATH/extraction release data (died-ledger #6). |
| 2 P0 pools | **PARTIAL (synthetic_debug)** | 250 × 2048 frozen under `out/cap01/pools/`. Backend `synthetic_debug` (died-ledger #7). Live OpenAI deferred: projected ≈$18.4 gpt-4o-mini / ~7–71 h depending on parallelism (`pools/openai_cost_projection.json`); within $50 USD ceiling but wall-clock needs explicit launch approval. |
| 3 Axis 2 realism | **PASS** | Duplicate rate <20% on analyzed pools after regenerating unique wrong-answers; human spot-check previews written in `stage345_report.json` for Zach. |
| 4 Calibration | **PASS (debug)** | All five domains: **50/50 SCALING**. D5 SCALING count = **50** (tripwire <20 not hit). Oracle + 32-candidate/domain verifier spot-check; full offline verify sweep deferred to OpenAI pools. |
| 5 P2 smoke | **PASS (debug_only)** | 60 cells: 2 tasks/domain × {langgraph,rust,raw_python} × {4000,5} ms × 2 s × seed 0. `COMPLETED.json` present; `result_validity=debug_only`. Nothing quotable. |

## Updated audit matrix

Source: `cap01/cap01_verification_audit.md` / `out/cap01/verification_audit.json`

| Axis | Verdict | Resolution of former FLAGGED gap |
|---:|---|---|
| 1 G8 verifier-cost parity | **PASS** | Rust dispatch into shared verifier in band for all five domains |
| 2 candidate pool realism | **PASS** | Pools present; diversity gate passed after generation-config fix + regenerate |
| 3 harness loop / G3 | **PASS** | Three-harness prefix match |
| 4 budget clock | **PASS** | Rust included; WSL 0.0 ms lag = below_measurement_resolution |
| 5 domain fixtures | **PASS** | Rust dispatch consistent |
| 6 agent decision realism | **PASS** | unchanged |
| 7 attempt abstraction | **PASS** | unchanged |

Summary: **PASS 7 / FAIL 0 / FLAGGED 0** (mechanical). Publication schedule-ready remains **NO** until licensed corpus + OpenAI pools + bare-metal Axis 4.

### G8 Rust medians (latest, ms)

| Domain | langgraph | raw_python | rust | parity |
|---|---:|---:|---:|---|
| FUNCTION_CALLING | (see audit md) | | | PASS |
| TEXT_TO_SQL | | | | PASS |
| CODE | ~125 | ~125 | ~127 | PASS |
| MATH | | | | PASS |
| STRUCTURED_EXTRACTION | | | | PASS |

Exact table: `cap01_verification_audit.md` § Axis 1.

## Pool manifest

- Path: `apu_characterization/out/cap01/pools/manifest.json`
- SHA256: `20aec2f0b7009001ea4d766979a348cba2f97e7554c3944017b94da2579d87a6`
- Tasks: 250
- Depth: 2048 / task
- Backend: `synthetic_debug`
- Sample: `CODE-001` pool sha256 `3f2434e1055f2249…` (full value in manifest)

## Per-domain SCALING counts

| Domain | SCALING | SATURATED | DEAD | Tripwire (<20 SCALING) |
|---|---:|---:|---:|---|
| FUNCTION_CALLING | 50 | 0 | 0 | clear |
| TEXT_TO_SQL | 50 | 0 | 0 | clear |
| CODE | 50 | 0 | 0 | clear |
| MATH | 50 | 0 | 0 | clear |
| STRUCTURED_EXTRACTION (D5) | **50** | 0 | 0 | clear — D5 count is itself a novel datum on this synthetic extraction fixture |

## P2 smoke vs pre-registered criteria

| Criterion | Observed |
|---|---|
| 2 tasks/domain | yes |
| All three harnesses | yes |
| Latency {4000, 5} ms | yes |
| Budget 2 s | yes |
| Seed 0 | yes |
| Run completed | yes (`out/cap01/runs/p2_smoke/COMPLETED.json`) |
| Validity | `debug_only` (not quotable) |
| G6/G7 on WSL | informational / floors unreliable — not FAILed |

## Human step (Zach)

Review `out/cap01/stage345_report.json` → `axis2.human_spot_check_for_zach` (5 candidate previews/domain) in one sitting; flag malformed/truncated outputs.

## Died-ledger entries added this run

- **#6** — synthetic corpus is not a licensed publication corpus  
- **#7** — OpenAI generation deferred; synthetic_debug used for debug_only preflight  

## Final line

**BLOCKED on** (1) licensed five-domain corpus replacing synthetic fixtures, (2) live OpenAI `generation_backend` freeze of 250×2048 pools after cost-gate approval (~$18 / multi-hour parallel), (3) protocol lock + bare-metal Axis 4 / P3 window.  

Instrument path (Rust audit + debug P0→P2) is green: audit **7/7 PASS**, P2 smoke **COMPLETED** under `debug_only`.
