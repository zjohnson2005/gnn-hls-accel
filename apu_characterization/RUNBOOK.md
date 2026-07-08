# APU characterization runbook (run these yourself, in order)

Everything runs locally, no FPGA server. Windows PowerShell, Python 3.11+.
All commands run from the repo root: `C:\Users\zjohn\Projects\gnn-hls-accel`.

## Minimal workflow stack

One-command gate before any full replication:

```powershell
$env:OPENAI_API_KEY = "sk-..."
.\apu_characterization\run_apu_gate.ps1
# or from WSL: make apu-gate
```

Unattended replication + poll (Cursor `/loop 10m make apu-replicate-check`):

```powershell
.\apu_characterization\run_apu_replicate_unattended.ps1
wsl make apu-replicate-check   # exit 2 = still running; 0 = done + validated
```

Nightly CI: `.github/workflows/apu-nightly.yml` (requires `OPENAI_API_KEY` repo secret).

Publishability policy for agents: `.cursor/rules/apu-characterization.mdc`.

## Verifiable data (read this first)

**Policy:** `VERIFIABLE_DATA.md` — synthetic/scripted paths are test-only.

**Recharacterization steps:** `RECHARACTERIZATION.md` — ordered Phase A3 → v2 replication.

## Result validity (read this first)

**Verifiable data policy:** read `VERIFIABLE_DATA.md` before citing any number.

| Run | Artifact | Valid for papers/slides? |
|-----|----------|--------------------------|
| `real_agent_breakdown --backend openai` | `out/real_agent_breakdown.json` | **Yes** (single-seed exploratory; prefer replication) |
| `replication_batch --backend openai --search-locality remote` | `out/replication_remote_search.json` | **Yes** — primary publishable headline |
| `tool_locality_ablation --backend openai` | `out/tool_locality_ablation.json` | **Yes (methods)** — matched SH pairs only |
| `real_agent_breakdown --backend scripted` | `out/real_agent_breakdown_debug.json` | **No** — synthetic model; instrumentation test only |
| `profile_reconcile_session --backend scripted` | `out/profile_*.json` | **No** — not valid for ATTRIBUTION_VERDICT |
| `single_agent_breakdown` (mock harness) | `out/single_agent_breakdown_debug.json` | **No** — mock harness only |
| `concurrency_sweep --backend scripted` | `out/concurrency_sweep.json` | **No** — debug smoke only |

Synthetic models (`--backend scripted`), mock LLM sleeps, and mock remote HTTP round-trips
exist only to test timers and invariants. **Verifiable characterization requires
`--backend openai` on Linux** plus real tool implementations (SymPy, NumPy, regex corpus,
CPython exec). Mock remote search is a labeled deployment model, not production HTTP.

**CPU attribution model:** read `apu_characterization/ATTRIBUTION.md` before quoting
ORCH or harness-strict percentages. ORCH is split into **measured** (stream step)
vs **reconcile** (session-end gap). Harness strict = ORCH+TOKEN+SER only (not TOOL/HTTP).

## Methodology checklist (blocking order)

1. **Linux + resolution self-test** (blocking): Windows data is footnote-only below
   ~200 ms/session (15.625 ms tick). On Linux:
   ```
   py -3 -m apu_characterization.tests.test_resolution
   py -3 -m apu_characterization.capture_setup --strict
   ```
2. **Accounting audit** (automatic): reports flag violations; `audit_failed` artifacts
   must not be cited. Re-run after fixing tick/cross-counter issues.
3. **Replication n≥5 seeds** (required for headlines):
   ```
   py -3 -m apu_characterization.experiments.replication_batch --backend openai --seeds 0,1,2,3,4 --search-locality local
   py -3 -m apu_characterization.experiments.replication_batch --backend openai --seeds 0,1,2,3,4 --search-locality remote
   ```
   Report medians and IQR only; single-seed tables are exploratory.
4. **Behavioral buckets** (in report): group by realized tool mix, not task labels.
5. **Matched ablation** for locality: `tool_locality_ablation` (matched pairs, live model);
   `trace_replay_ablation` (matched trace replay from recorded `tool_call_sequence`);
   full-suite remote rerun is **distribution comparison**, not matched-pair.
6. **Pre-registration**: predictions in `apu_characterization/PREDICTIONS.md` before sweep.
7. **Denominators baked into captions**: every headline % travels with batch CPU ms,
   seed count, search locality, and c.
8. **Environment capture**: `capture_setup --strict` refuses dirty git / missing fields.

## Prerequisites (one time)

**Windows before any publishable run:**

1. Install [Git for Windows](https://git-scm.com/download/win) and restart PowerShell.
2. Set your API key in the same session (capture records whether it is set):
   ```powershell
   $env:OPENAI_API_KEY = "sk-..."
   ```
3. Re-capture after both are in place:
   ```powershell
   py -3 -m apu_characterization.capture_setup --strict
   ```

**Platform note:** `test_resolution` is expected to **FAIL** on Windows (15.625 ms
thread-time tick). Publishable per-category shares require **Linux** with
`test_resolution` PASS. Windows OpenAI runs are footnote-only below ~200 ms/session.

```
py -3 -m pip install numpy psutil matplotlib
py -3 -m pip install tiktoken sympy
```

`tiktoken` and `sympy` are optional; the harness falls back to len/4 token
estimation and plain-python eval if they are missing, and records which path
was used.

## Experiment 0: prove the breakdown on one agent

This is the smallest complete demonstration of the measurement model.
Three steps, all mandatory before any sweep is trusted.

### Step 0.0: capture the setup (do this before any measurement)

```
py -3 -m apu_characterization.capture_setup
```

Probes your machine and writes the pre-registration record:

- `apu_characterization/out/setup.json`
- `apu_characterization/EXPERIMENT_SETUP.md`

The .md contains the CPU model, core counts, frequency, RAM, power plan,
OS, Python and package versions, git commit, the exact agent architecture
under test, the category taxonomy, the profile parameters, and the full
task suite (every task goal and every tool call with its literal
arguments). Read it and confirm it matches your machine before going on.
Experiments refuse to run if this record is missing, and every run
artifact embeds the setup digest so results trace back to this record.

If the CPU model or RAM shows as unknown, install psutil
(`py -3 -m pip install psutil`) and re-run the capture.

### Step 0.1: timer correctness tests

```
py -3 -m apu_characterization.tests.test_instr
py -3 -m apu_characterization.tests.test_resolution
```

What it proves, and what you should see:

- nested exclusive accounting: an inner SERIALIZATION region inside a
  PROMPT_ASSEMBLY region is not double counted. Expect outer ~40 ms and
  inner ~30 ms self-time, printed with OK.
- accounting invariant: instrumented + residual = total thread CPU within
  1%, and a deliberately uninstrumented 10 ms spin shows up as residual.
- I/O exclusion: a 150 ms time.sleep inside a region records ~150 ms wall
  but ~0 ms CPU. This is the mechanism that excludes I/O wait without
  guessing.
- timer overhead: prints ns per enter/exit pair. Note the number; it goes
  into the methodology later.

If any assertion fails, stop. Nothing downstream is valid.

### Step 0.2: single-agent breakdown (debug only)

Verifies instrumentation on the plain-Python mock harness. Output is
`out/single_agent_breakdown_debug.json` — **not valid experimental data**.

```
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile mixed --seed 0 --sessions 1
```

What it does: assigns a specific named task from the suite (for mixed,
seed 0, session 0 that is task SH-01: a basic weather-research question
answered through eight literal search queries), builds the task graph
through the OrchEngine (same setup/dispatch semantics as Phase 0), runs
the ReAct session with the mock LLM (asyncio sleep = I/O wait, zero
thread CPU) and real local tools executing the task's literal arguments
(regex corpus scans, the task's Python snippets, deterministic cosine
retrieval, the task's arithmetic), and wraps every CPU-bearing region in
an exclusive category timer. The executed task script is printed in full
in the report's "Tasks executed" section.

First run generates fixtures (50 MB topic-paragraph corpus + 100k x 384
float32 matrix) under `apu_characterization/fixtures/`; that takes a minute
and only happens once. If you generated fixtures before the task suite was
finalized, regenerate once so search queries match the corpus vocabulary:

```
py -3 -m apu_characterization.fixtures.generate_fixtures --force
```

Artifacts written (debug only — do not cite):

- `apu_characterization/out/single_agent_breakdown_debug.json`
- `apu_characterization/out/single_agent_breakdown_debug.md`

Every number in the .md is read from the .json. Nothing is hand-typed.

Windows measurement note: thread CPU time ticks at 15.625 ms granularity
(GetThreadTimes). A single session only accrues tens of ms of CPU, so
per-category numbers in a --sessions 1 run are quantization-noisy; treat
single-session runs as smoke tests of the mechanism and use --sessions 10
or more for share numbers you intend to quote. Tick attribution lands on
whichever region is active when the tick fires, so aggregation over many
regions is unbiased.

Acceptance for this experiment:

1. Exit code 0 and the console line ends with PASS
   (residual below 15% of total thread CPU).
2. Open the .md: the breakdown table should show nonzero CPU in ORCH_SETUP,
   ORCH_DISPATCH, SERIALIZATION, TOKENIZATION, PROMPT_ASSEMBLY,
   CONTEXT_MGMT, TOOL_COMPUTE, LOGGING. HTTP_CLIENT is nonzero only when
   the session runs an AH task (mock API envelopes); other tasks do not
   touch it. GC may be zero on a short run.
3. If residual is above 15%, the taxonomy has a hole: record the residual
   number, find the uninstrumented region (step 0.3), add a timer, rerun,
   and note what was added. Do not proceed to sweeps with a failing
   invariant.

Variations worth doing once each (same command, different flags). The task
suite has 16 tasks across 11 archetypes, and each archetype stresses a
different mechanism, so run at least these and compare the category tables:

```
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile rag_heavy --seed 0 --sessions 1
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile long_horizon --seed 0 --sessions 1
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile fanout --seed 0 --sessions 1
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile chain --seed 0 --sessions 1
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile swarm --seed 0 --sessions 1
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile structured_output --seed 0 --sessions 1
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile api_heavy --seed 0 --sessions 1
py -3 -m apu_characterization.experiments.single_agent_breakdown --profile mixed --seed 0 --sessions 10
```

What each should show, qualitatively:

- rag_heavy: SERIALIZATION and TOOL_COMPUTE bytes inflate (large results)
- long_horizon (LH-01/02): CONTEXT_MGMT and TOKENIZATION grow across turns
  within the session as state accumulates
- fanout (FO-01): dispatch burst; ORCH_DISPATCH count spikes in one turn,
  graph has 9 tool nodes joining one ALL_OF node
- chain (CN-01): extra SERIALIZATION + PROMPT_ASSEMBLY pairs from the
  piped handoffs between tools
- swarm (SW-01): ORCH_SETUP count = 4 (parent + three sub-agents); the
  per-session table lists the sub-agent sessions
- structured_output (SO-01): SERIALIZATION bytes_out grows every emit turn
  (the full list is re-emitted each time)
- api_heavy (AH-01): HTTP_CLIENT becomes nonzero and wall time far exceeds
  CPU time in those regions, verifying the I/O-wait exclusion
- mixed, sessions 10: per-session attribution sums correctly under
  concurrent asyncio sessions; sessions get different tasks from the pool

The report's per-session table now records tool calls per session and the
tool usage rollup, because task and tool mix is a grouping dimension in the
final analysis.

### Step 0.3 (only if residual fails): find the hole

```
py -3 -m pip install py-spy
py-spy record --format speedscope -o apu_characterization/out/pyspy_exp0.speedscope.json -- py -3 -m apu_characterization.experiments.single_agent_breakdown --profile mixed --seed 0 --sessions 10
```

Open the speedscope file at https://www.speedscope.app and look for hot
frames that are not inside any timed region. Wrap them, rerun 0.2.

### Step 0.4: REAL agent breakdown (LangGraph)

**Publishable run (required for any research output):**

```
py -3 -m apu_characterization.experiments.real_agent_breakdown --backend openai --profile mixed --seed 0 --sessions 10
```

Requires `OPENAI_API_KEY`. Writes `out/real_agent_breakdown.json` /
`.md` with `result_validity: publishable`.

**Debug run (instrumentation check only — do not cite):**

The plain-Python harness is the controlled instrument; this step runs the
same tasks through a genuine LangGraph create_react_agent with the same
real tools, so the breakdown is measured on a real agent framework.

One-time install (same requirements Phase 0 used):

```
py -3 -m pip install -r orchestration_engine/characterization/requirements-langgraph.txt
```

Scripted backend (debug only — synthetic LLM + TaskSpec decisions):

```
py -3 -m apu_characterization.experiments.real_agent_breakdown --backend scripted --profile mixed --seed 0 --sessions 10
```

Writes `out/real_agent_breakdown_debug.json` / `.md`. Use to confirm
invariants and report generation before spending API credits. **Never cite
these numbers as results.**

Fully real backend (ChatOpenAI decides tool calls itself; validation
scale, needs OPENAI_API_KEY). Runs **one session at a time** by default
(`--workers 1`) so process-wide CPU matches the category timers.

```
py -3 -m apu_characterization.experiments.real_agent_breakdown --backend openai --profile mixed --seed 0 --sessions 10
```

Publishable artifacts: `out/real_agent_breakdown.json` and `.md`.

**Remote-search deployment (corrected headline numbers):**

```
py -3 -m apu_characterization.experiments.real_agent_breakdown --backend openai --profile mixed --seed 0 --sessions 10 --search-locality remote
```

Writes `out/real_agent_breakdown_remote_search.json` / `.md`. Same task suite
and live OpenAI decisions; search tool is mock remote (HTTP + I/O wait). The
report includes a reconciliation table against the local-search baseline.
Uses `locality_ablation` payload profile (4 KB tool-result cap) by default to
stay under 128k context.

Measurement model difference, stated in the report: tool-side work uses
the same category timers, but LangGraph internals cannot be wrapped
region by region, so per-step framework CPU (thread CPU between stream
events minus tagged tool CPU) is attributed to ORCH_SETUP on the first
step and ORCH_DISPATCH on later steps. That is exactly the Phase 0
definition of orchestration cost, so ORCH numbers here are directly
comparable to the Phase 0 table. PROMPT_ASSEMBLY, CONTEXT_MGMT, and
LOGGING are inside the framework and fold into the ORCH buckets in this
mode; comparing Experiment 0 vs 0R shows how much of the framework's
step cost those mechanics explain.

Real-mode limitations (documented): reasoning-only, structured-emit,
sub-agent, and api turns cannot exist mid-loop in a real ReAct agent, so
scripted tasks fold them into neighboring turns; SW-01/SO-01/AH-01
signatures are only fully exercised by the plain harness.

### Step 0.5: tool-locality ablation (search local vs remote)

Tests whether search CPU in the publishable run is an artifact of
in-process regex search or a durable property of search-using agents.
Each task runs twice: `search=local` (50 MB regex, baseline) and
`search=remote` (mock HTTP envelope + I/O wait, production-shaped).

**Debug (scripted TaskSpec decisions, no API key):**

```
py -3 -m apu_characterization.experiments.tool_locality_ablation --backend scripted --seed 0
```

**Publishable (live OpenAI, same task goals):**

```
py -3 -m apu_characterization.experiments.tool_locality_ablation --backend openai --seed 0
```

Default tasks: SH-01, SH-02, CH-02, RE-02, RH-01 (all invoke search in
the mixed seed-0 batch). Override with `--tasks SH-01,SH-02`. Optional
`--retrieve-locality remote` ablates retrieve the same way.

Uses the `locality_ablation` payload profile (tool results capped at 4 KB)
so multi-tool OpenAI sessions stay under the 128k context limit. Padding
is identical across local/remote search arms and does not affect the
TOOL_COMPUTE comparison.

Artifacts: `out/tool_locality_ablation.json` / `.md` (publishable with
openai). Read the paired delta table: if SH tasks drop from CPU-heavy to
I/O-dominated when search is remote, the baseline search finding is a
tool-locality artifact, not a hardware problem.

## Experiment 1: concurrency sweep (workers × remote search)

Characterizes how host CPU breakdown scales when multiple agent sessions run
in parallel. Uses the same deployment as the Linux replication baseline:
OpenAI backend, remote search, `locality_ablation` payload profile, mixed task
suite, 10 sessions per batch.

**Baseline c=1** in replication and real-agent breakdown means `workers=1`:
all 10 sessions run **sequentially** one-at-a-time. This sweep varies
`--workers` (ThreadPoolExecutor slots) while holding `sessions=10`.

**Debug smoke (no API key, fast):**

```
py -3 -m apu_characterization.experiments.concurrency_sweep --backend scripted --workers 1,2 --sessions 2 --seed 0
```

Multi-seed replication (n≥5 for headlines):

```
py -3 -m apu_characterization.experiments.replication_batch --backend openai --seeds 0,1,2,3,4 --search-locality remote
```

**After code changes (ORCH split, audit, report templates)** — refresh stored JSON
without re-running OpenAI (accounting + aggregates only):

```
py -3 -m apu_characterization.experiments.replication_batch --refresh-only --allow-dirty
py -3 apu_characterization/tools/validate_publishable.py
py -3 apu_characterization/tools/replication_task_breakdown.py
```

For the final publishable stamp: commit all changes, re-run capture_setup, then
either `--refresh-only` on a clean tree or full Linux replication (no `--allow-dirty`).

## ORCH reconcile diagnosis and v2 replication (blocks concurrency sweep)

Phase A (diagnose, no harness changes):

```
py -3 -m apu_characterization.experiments.reconcile_phase_a
py -3 -m apu_characterization.tests.test_reconcile_worker
py -3 apu_characterization/tools/generate_attribution_verdict.py --profile-json apu_characterization/out/profile_lh-01_s0.json
```

Profile one heavy session (LH-01 = task index 8, seed 0) on Linux/WSL with OpenAI.
Uses a repo-local venv (PEP 668 safe; do not `pip install` system-wide on Debian/WSL):

```
# PowerShell (API key in this session):
.\apu_characterization\run_profile_lh01_wsl.ps1
```

Or in WSL directly:

```
export OPENAI_API_KEY=sk-...
bash apu_characterization/run_profile_lh01_wsl.sh
```

Manual steps (if you already have py-spy on PATH):

```
bash apu_characterization/run_profile_lh01_wsl.sh
```

Phase C (v2 replication, clean git, Linux):

```
py -3 -m apu_characterization.experiments.replication_batch --backend openai --seeds 0,1,2,3,4 --search-locality remote --instr-version 2
py -3 apu_characterization/tools/replication_v2_compare.py
```

Artifacts: `out/replication_remote_search_v2.json`, `out/replication_v1_v2_migration.md`.
Gate G2 for concurrency sweep: satisfied when v2 audit PASS and RESIDUAL_UNATTRIBUTED below 15% every session.

## Concurrency sweep (separate workstream)

Not required for Phase 0-prime headline numbers. See `experiments/concurrency_sweep.py`
when scaling workers is in scope.

**Publishable (Linux/WSL recommended, needs OPENAI_API_KEY):**

```
py -3 -m apu_characterization.experiments.concurrency_sweep --backend openai --seeds 0 --workers 1,2,4,8 --search-locality remote
```

Multi-seed replication (n≥5 for headlines):

```
py -3 -m apu_characterization.experiments.concurrency_sweep --backend openai --seeds 0,1,2,3,4 --workers 1,2,4,8 --search-locality remote
```

Artifacts: `out/concurrency_sweep.json` / `.md`. The summary table reports
batch host CPU ms, batch wall s, and pooled TOOL / ORCH / harness-APU strict %
per workers level (median [IQR] when multiple seeds).

Run `test_resolution` PASS on Linux before quoting per-category shares.
Windows OpenAI runs remain footnote-only below ~200 ms/session.

## What comes after (not yet run)

- Full profile sweep matrix (7 concurrency levels × 5 profiles × 5 seeds),
  analysis figures, scorecard. Profile dimension beyond mixed + remote search
  is the next implementation step after this workers sweep is validated.

## Notes and caveats already known

- The mock LLM latency scale flag (`--llm-scale`, default 0.05 for
  Experiment 0) shrinks wall time only. Latency is asyncio sleep, which
  costs zero thread CPU, so CPU shares are unaffected. The full sweep will
  use 1.0 unless the runtime budget forces scaling, which gets documented.
- GC hooks cover collector cycles only, not refcount deallocation, so GC is
  a lower bound.
- Per-category kernel time attribution is approximate; the report includes
  the process-wide user/system split from os.times.
