# Output artifacts

## Publishable (may appear in papers and slides)

| File | How produced |
|------|----------------|
| `real_agent_breakdown.json` | `real_agent_breakdown --backend openai` (local search) |
| `real_agent_breakdown.md` | auto-generated from the JSON above |
| `real_agent_breakdown_remote_search.json` | `real_agent_breakdown --backend openai --search-locality remote` |
| `real_agent_breakdown_remote_search.md` | auto-generated from the JSON above |
| `tool_locality_ablation.json` | `tool_locality_ablation --backend openai` |
| `tool_locality_ablation.md` | auto-generated from the JSON above |

The JSON must contain `"result_validity": "publishable"`.

## Debug only (instrumentation verification — never cite as results)

| File | How produced |
|------|----------------|
| `single_agent_breakdown_debug.json` / `.md` | Experiment 0 mock harness |
| `real_agent_breakdown_debug.json` / `.md` | Experiment 0R `--backend scripted` |

These use mock LLM sleeps and/or scripted tool decisions. They check that
timers, invariants, and reports work; they are **not** experimental data.

## Setup (not experiment results)

| File | Purpose |
|------|---------|
| `setup.json` | Pre-registration machine + task suite digest |
| `EXPERIMENT_SETUP.md` | Human-readable setup record (parent directory) |
