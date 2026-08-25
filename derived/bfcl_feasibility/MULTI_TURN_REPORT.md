# BFCL multi-turn feasibility (DISPATCH A3)

**Gold selftest:** `multi_turn_checker` via CAP-01 shim — **20/20 valid**.  
**gpu_only 20-entry agent loop:** **BLOCKED_ON_OPERATOR** — no accuracy invented.

## Wiring

| Piece | Path |
| --- | --- |
| CAP-01 wrapper | `apu_characterization/cap01/bfcl_cap01_multi_turn_checker.py` |
| Shims (same as AST) | `apu_characterization/cap01/bfcl_shims` |
| Probe modes | `tools/bfcl_feasibility_probe.py` → `multi_turn_gold_selftest`, `run_gpu_multi_turn` |
| Gold artifact | `derived/bfcl_feasibility/multi_turn_gold_selftest.json` |
| Gate snapshot | `derived/bfcl_feasibility/multi_turn_precondition_gate.json` |
| Operator cmd | `derived/bfcl_feasibility/OPERATOR_CMD_MULTI_TURN.md` |

Gold path: wrap each turn’s GT execute-string list as a single decoded step, call official `multi_turn_checker` under shims, unique `model_name` per call to avoid `globals()` instance reuse.

## Preconditions (2026-08-10)

| Check | Result |
| --- | --- |
| AC (`BatteryStatus=2`) | PASS |
| Available MBytes ≥ 7000 | **FAIL** (6045) |
| Tier-1 clean | **FAIL** (Cursor ~2003 MiB private, chrome ~1543 MiB) |

`tools/run_gpu_only_matrix.ps1 -DryRunGate` → REFUSED. Per protocol: stop; do not fake scores.

## 20-entry gpu_only results

Not measured. No `correct/n`, wall-clock, token distributions, or context-growth numbers exist for the multi-turn agent loop.

When clean, run the SSH/detached command in `OPERATOR_CMD_MULTI_TURN.md`. Expected artifact: `multi_turn_gpu_probe_report.json`.

## Verdict vs single-turn (A2)

| Arm | Score | Status |
| --- | --- | --- |
| A2 single-turn AST (`simple_python`) | 3/5 | measured |
| A2 single-turn AST (`parallel`) | 5/5 | measured |
| A3 multi-turn (`multi_turn_base`, n=20) | **unknown** | blocked |

Cannot yet say multi-turn accuracy is near zero (or not) relative to single-turn. Checker path is trusted (gold 20/20); model multi-turn accuracy requires the clean gpu_only run.
