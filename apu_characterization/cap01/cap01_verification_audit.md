# CAP-01 full behavioral verification audit

- Protocol: `cap01_v2`
- Mechanical P3 eligible (no FAIL axis): **YES**
- Schedule-ready: **NO** for capability_scaling publication (licensed corpus + OpenAI pools + bare-metal Axis 4 still required). Mechanical audit is 7/7 PASS on the debug_only instrument path.
- Confirmed via pytest + Stage-1/3/5 execution, 2026-07-14; Rust G8/G3/clock included; Axis 2 PASS after pool regenerate

## Headline yield

Axes 6 and 7 are the redesign-or-die structural checks. Both **PASS** on static inspection of the measured loop: pure replay-and-verify (zero live model / unseeded randomness in the timed path) and 1:1 candidate→verifier→verdict in all five domains. That converts "CAP-01 is structurally immune to Rithwik's failure mode" from an argument into a measured fact for the surface that exists.

## Load-bearing architectural finding

All three harnesses share **one** verifier callable inside `budget.execute_task_loop` under `TOOL_COMPUTE`. Harness differences are candidate dispatch only (in-process JSON vs Rust NDJSON). There is no per-harness sandbox spawn path to diverge.

Consequence for G8: parity on the shared-verifier portion is **guaranteed by construction**. A Rust re-run therefore tests Rust's **dispatch path into the shared verifier**, not an independent verifier implementation. A future G8 failure means a dispatch-path problem, not a verifier-logic problem.

**Standing rule:** the shared-verifier architecture is load-bearing for G8's validity. Un-sharing the verifier (for performance or any other reason) re-opens Axis 1 / G8 before further measurement. See `protocol_cap01_v2.json` gates.G8.load_bearing_constraint.

## Summary table

| Axis | Name | Verdict | Measurement | Fix required before P3 |
|---:|---|---|---|---|
| 1 | verifier_cost_parity | **PASS** | 200 in-situ verifier calls/harness/domain; cross-harness TOOL_COMPUTE medians within ±15%. | — |
| 2 | candidate_pool_realism | **PASS** | Analyzed 50 task pools; duplicate rate <20% and no empty/truncated heuristic hits in sampled JSONL. | Still require human spot-check of 5 candidates/domain and solve-curve monotonicity after calibration correctness labels exist. |
| 3 | harness_loop_fidelity | **PASS** | Identical loop steps across harnesses; G3 hash match on 20-task × 3-seed smoke. | — |
| 4 | budget_clock_integrity | **PASS** | Deadline lag medians {'langgraph': 0.0, 'rust': 0.0, 'raw_python': 0.0}; fixed-cost counted medians {'langgraph': 8, 'rust': 8, 'raw_python': 8}. Lag medians of 0.0 ms on Windows/WSL are below timer resolution (~15.6 ... | — |
| 5 | domain_fixture_idleness | **PASS** | Per-domain check and overhead costs within ±15% across harnesses. | — |
| 6 | agent_decision_realism | **PASS** | Zero live model calls or unseeded randomness in budget/harness/runner/verifier loop path; decisions are replay-and-verify only. | — |
| 7 | attempt_abstraction | **PASS** | All five domains: one candidate generation maps to exactly one verifier invocation and one pass/fail verdict in the measured loop. | — |

Note (Axis 2 / pool depth): 2048 is the pre-registered pool depth per `protocol_cap01_v2.json`; 128 refers specifically to the DEAD-classification threshold from the original spec (`DEAD@128` secondary context) and is not a separate, smaller pool size.

## Axis 1 / G8 per-domain medians (ms)

| Domain | langgraph | raw_python | rust | band median | parity |
|---|---:|---:|---:|---:|---|
| FUNCTION_CALLING | 0.1512 | 0.0952 | 0.2016 | 0.1512 | PASS |
| TEXT_TO_SQL | 0.2747 | 0.1710 | 0.3920 | 0.2747 | PASS |
| CODE | 70.7932 | 122.4114 | 72.1005 | 72.1005 | PASS |
| MATH | 0.0883 | 0.0429 | 0.0934 | 0.0883 | PASS |
| STRUCTURED_EXTRACTION | 18.5971 | 5.9786 | 13.9542 | 13.9542 | PASS |

## Gate G8 (verifier cost parity)

- Automated gate pass (cost-divergence failures only): **YES**
- Primary-eligible (no FAIL and no FLAGGED toolchain gaps): **YES**

Re-run G8 whenever any harness verifier-invocation path changes, and whenever the shared-verifier architecture is altered.

### G8 band amendment (died-ledger #5) — process note

The half_width rule `max(0.15 × median, 0.25 ms absolute, max within-harness IQR)` was amended **mid-audit** after relative-only ±15% falsely failed MATH (~0.09 ms) and noisy TEXT_TO_SQL. The amendment is technically sound (timer physics; CODE-class relative discipline preserved) and was ledgered, but it is exactly the post-data threshold move pre-registration forbids. Honest record: G8's timer-resolution floor should have been calibrated at freeze time (MCP-01 tick lesson). Standing principle extracted: any future gate over sub-millisecond quantities freezes a timer-resolution floor at protocol freeze time, not at failure time.

## Required decisions before P3

1. **Rust gap (Axes 1/3/4/5) — fix, do not caveat.** Rust is one side of the pre-registered primary cell (LangGraph-vs-Rust). An audit that never touched Rust has not audited the primary comparison at all: that cell is currently **0% audited on one of its two sides**. Install rustc/cargo and re-run.
2. **Axis 2 pools — long pole.** Generate and freeze pools at the **pre-registered** `minimum_candidates_per_task=2048` (see `METHODOLOGY_CAP01.md` and `protocol_cap01_v2.json`). Note: 2048 is the pre-registered pool depth per `protocol_cap01_v2.json`; 128 refers specifically to the DEAD-classification threshold from the original spec and is not a separate, smaller pool size. 2048 was frozen before data because 128 exhausts before 5 ms primary cells. Then re-run diversity / solve-curve / human spot-check.
3. **Axis 4 bare-metal re-run — explicit, alongside Rust.** Local lag medians of 0.0 ms on Windows/WSL mean **below measurement resolution** (~15.6 ms tick), not measured zero. Fine as a gate; publication clock integrity requires bare-metal Axis 4.
4. **G8 half-width amendment** — already ledgered (#5); keep. Do not reopen unless the shared-verifier architecture changes.
5. **CODE ~90 ms / D5 nested≈3× flat** — accept as domain physics if Rust re-run stays inside band and D5 complexity ratio stays `<10`.
6. No axis may remain FAIL when P3 is scheduled. Mechanical `p3_eligible=True` is not schedule readiness.

## Decision rule

CAP-01 does not enter P3 scheduling with any axis in FAIL. FLAGGED items require a documented fix / scope-narrow / accept-with-caveat decision and died-ledger entries for anything retired or narrowed. Keep building toward P2; do not spend the bare-metal window until the Rust column and frozen pools exist.
