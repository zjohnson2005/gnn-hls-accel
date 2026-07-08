> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** This artifact used a mock, scripted, or synthetic decision path (no live OpenAI agent). Use only to verify instrumentation and invariants. Do not cite in papers, slides, or findings. See VERIFIABLE_DATA.md.

# Retrieve-locality ablation (LH-01, local matmul vs mock-remote)

Generated: 2026-07-08T13:00:57.774397+00:00
Setup digest: `6da6d4433aa84601`

## Question

Does local retrieve (100k×384 matmul in TOOL_COMPUTE) convert to remote mock-retrieve I/O wait when only retrieve locality changes?

## Per-session

| seed | retrieve | wall (s) | host CPU (ms) | TOOL (ms) | retrieve I/O (s) | LLM wait (s) | I/O % wall | CPU % wall | retrieve calls |
|------|----------|----------|---------------|-----------|------------------|-------------|------------|------------|----------------|
| 0 | local | 32.973 | 1153.2 | 913.4 | 0.0 | 0.0 | 0.0 | 3.5 | 12 |
| 0 | remote | 32.455 | 154.2 | 0.0 | 5.397 | 0.0 | 16.6 | 0.5 | 12 |
| 1 | local | 26.419 | 314.3 | 164.1 | 0.0 | 0.0 | 0.0 | 1.2 | 12 |
| 1 | remote | 30.978 | 148.2 | 0.0 | 4.729 | 0.0 | 15.3 | 0.5 | 12 |

## Paired delta (local → remote)

| seed | matched | Δ host ms | Δ TOOL ms | Δ I/O % wall | retrieve calls |
|------|---------|-----------|-----------|--------------|----------------|
| 0 | yes | -999.0 | -913.4 | 16.6 | 12 |
| 1 | yes | -166.1 | -164.1 | 15.3 | 12 |

## Interpretation

**Backend:** scripted (no `OPENAI_API_KEY` in env at run time) — debug-only; causal shape only.

Remote retrieve moves matmul CPU from TOOL_COMPUTE into HTTP_CLIENT I/O wait (mock round-trip), consistent with the search-locality ablation precedent.

