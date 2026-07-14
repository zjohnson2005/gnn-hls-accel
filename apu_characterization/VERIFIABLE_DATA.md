# Verifiable data policy

Non-negotiable rule for papers, slides, advisor reviews, and concurrency-sweep gates:

**Synthetic and mock agent decision paths are for instrumentation testing
only.** They are never quotable agent-characterization results. The MCP-01
protocol microbenchmark exception below uses deterministic no-op tools to
isolate protocol cost; it licenses only protocol/transport claims.

## What counts as synthetic (test only)

| Component | Implementation | Valid use |
|-----------|----------------|-----------|
| `--backend scripted` | TaskSpec turn sequence, no live model | Timer/invariant smoke tests only |
| Mock LLM (`asyncio`/`time.sleep`) | Zero CPU wall wait | Mock harness (Experiment 0), debug artifacts |
| `single_agent_breakdown` | Plain-Python mock agent | Instrumentation proof only |
| Synthetic worker thread tests | `tests/test_reconcile_worker.py` | Proves reconcile arithmetic only |
| Mock remote search/retrieve | `sync_mock_remote_call` + `time.sleep` | Locality **ablation control arm**, not production HTTP characterization |

Artifacts from these paths are stamped `result_validity: debug_only` or carry the DEBUG banner.
Filenames use the `_debug` suffix where applicable.

## What counts as verifiable characterization

| Requirement | Why |
|-------------|-----|
| `--backend openai` | Live LangGraph ReAct agent; model chooses tools and queries |
| Linux WSL2, `test_resolution` PASS | Sub-200 ms sessions are tick-safe |
| Accounting audit PASS, n≥5 replication | Medians/IQR over seeds |
| Git-clean stamp on publishable artifact | Reproducibility |

**Tool bodies must be real open-source implementations** (already in this repo):

- `search` (local arm): regex scan over fixture corpus (`re`, on-disk text)
- `retrieve`: NumPy cosine over memory-mapped vectors
- `calculator`: SymPy (or bounded eval fallback)
- `code_exec`: CPython `exec` with bounded builtins
- LLM I/O: LangChain/OpenAI client (real HTTP stack via httpx when using `--backend openai`)

Do not substitute sleeps, stubs, or fabricated call sequences for these when reporting verifiable CPU shares.

## Controlled protocol-microbenchmark class (MCP-01)

`result_validity: protocol_microbenchmark` is a separate, narrow class for
MCP protocol/transport characterization. Deterministic no-op tool bodies are
required controls: tool compute and model decisions are outside the claim.

Publication requires all of:

- native bare-metal Linux (WSL2 is smoke/debug only)
- frozen `mcp_tax_v1.5` protocol and exact SDK lock
- disjoint verified OS/client/server core sets
- strictly serial measurement, n=5 seeds per cell
- clean git stamp and immutable run directories
- G1-G5 audit PASS under `apu_characterization.mcp_tax.audit`
- throttle primary; full is observer-only; paired stripped tax reported

Quotable: per-message MCP CPU tax, category decomposition, CPU-vs-wait split,
payload/schema/tool-count scaling, and SDK-minus-raw delta. Never quotable as
production agent CPU share, production latency, tool-body cost, model cost,
or evidence that synthetic agent runs satisfy the live-OpenAI policy.

## Deployment caveats (label in every caption)

The **publishable replication** uses **remote search** implemented as a mock HTTP envelope plus I/O wait (`harness/mock_api.py`). That is a **deliberate deployment model** (tool body off-host), not a claim about production search latency or a specific vendor API.

For causal locality claims, use **matched pairs only** (SH-01, SH-02) in `tool_locality_ablation` with `--backend openai`.

Local search (50 MB regex scan) is a **methods control**, not a production workload.

## Commands that produce verifiable data

```bash
# Publishable replication (Linux/WSL, OPENAI_API_KEY, clean git)
python3 -m apu_characterization.experiments.replication_batch \
  --backend openai --seeds 0,1,2,3,4 --search-locality remote

# ORCH reconcile profile (Phase A3, live agent only)
bash apu_characterization/run_profile_lh01_wsl.sh

# Validate before citing
python3 apu_characterization/tools/validate_publishable.py \
  apu_characterization/out/replication_remote_search.json
```

## Commands that do NOT produce verifiable data

```bash
# ANY of these: test instrumentation only
python3 -m apu_characterization.experiments.real_agent_breakdown --backend scripted ...
python3 -m apu_characterization.experiments.single_agent_breakdown ...
python3 -m apu_characterization.experiments.profile_reconcile_session --backend scripted ...
```

## Concurrency sweep gate

Do not start the workers sweep until **verifiable** v3 replication exists
(`replication_remote_search_v3.json`, audit PASS, live OpenAI, residual
provenance below 15% per session, `validate_publishable.py` exit 0).
Synthetic concurrency smokes are debug only.

Live c-ladder publication gate (after the run):

```bash
python apu_characterization/tools/validate_sweep.py \
  apu_characterization/out/concurrency_sweep.json
```

Requires: Linux/WSL2, `--backend openai`, `instr_version >= 3`, n>=5 seeds
per level, clean-git stamp, `audit.pass` and `audit.publishable_ok`.
Do not use `--allow-dirty` for publishable stamps.

### Two arms (do not conflate)

| Arm | Backend | Artifact | Quotable for |
|-----|---------|----------|--------------|
| Live OpenAI c-ladder | `--backend openai` | `concurrency_sweep.json` | Composition shift, CPU/I/O wall split, rate-limit ceiling (if util low) |
| Mock CPU saturation | `--backend scripted` | `concurrency_sweep_mock.json` | **CPU-bound N_max / k only** (`debug_only`; never CPU-share headlines) |

If the openai ladder stops on throughput stall with host util ≪ 85%, label
`binding_constraint: rate_limit` and **do not** cite N_max/k as host capacity.
Run `run_sweep_mock_saturation.sh` for the CPU-bound arm.

## Mock latency-collapse promotion class

A third, narrow artifact class for the latency-collapse promotion sweep
(`latency_collapse_promo_*` stems, `run_latency_collapse_promote.sh`).
`result_validity` stays `debug_only` (scripted backend); the combined artifact
additionally carries a self-describing `promotion` block whose label reads:

> mock-latency-sweep, seeded lognormal LLM (sigma 0.6), throttle
> instrumentation (9.6 percent residual tax at c=100 vs stripped),
> audit-gated, n=5

Quotable ONLY for, with the mock caveat stated in every caption:

- the harness-floor band per turn (process upper bound, harness_strict lower
  bound) and its scale-invariance across the swept LLM-latency range
- per-category ms/turn composition per concurrency level (Track B derivation
  input)
- the crossover-latency range (strict to process bounds), stated as a
  property of THIS harness under a seeded mock LLM

Never quotable as:

- production CPU shares (the LLM is a sleep; TOOL/ORCH proportions depend on
  the scripted task mix)
- production latency or vendor inference speed claims
- a substitute for `--backend openai` publishable characterization

Gates that still apply: per-cell audit PASS (residual provenance below 15
percent per session at c=1, batch-level gate at c>1), n >= 5 seeds, and the
throttle residual tax (9.6 percent at c=100 vs stripped) stated in captions.
The retrieve-locality variant cells (`latency_collapse_promo_retr_*`) are a
bounding ablation reported separately, never pooled into primary cells.

## Mock hybrid-router sweep class

Sibling debug-only artifact class for fixed-fraction hybrid-router sweeps
(`hybrid_router_sweep_f*_c1` stems, `run_hybrid_router_sweep.sh`).
`result_validity` stays `debug_only` because the router uses the scripted
backend with seeded mock sleeps. Combined artifacts carry a `promotion` block
with class:

> mock_hybrid_router_sweep

Quotable ONLY with the mock caveat stated in every caption:

- measured behavior of the fixed Bernoulli router under this harness
- measured local-tier fraction, router overhead, and per-turn harness floor
- comparison of theoretical tier-latency advantage vs measured turn-cycle
  speedup for this debug-only mock setup

Never quotable as:

- production routing-policy quality
- production local inference latency or API latency
- production CPU shares
- a substitute for `--backend openai` publishable characterization

Gates that still apply: per-cell audit PASS, residual provenance below 15
percent, n >= 5 seeds, `instr_version >= 3`, throttle instrumentation label,
and all FAILs retained in the report.

## Mock overlap-decomposition class

The `overlap_decomposition` arm is debug-only. It uses the scripted,
non-streaming backend with seeded lognormal sleeps, n=5, c=1, the fixed
14-task main pool, and throttle instrumentation. Every artifact and report
caption must state the mock caveat.

`STREAM_OVERLAPPABLE` is semantic and `BY_CONSTRUCTION`: it labels measured
response-finalization CPU after the mock sleep and before the stamped
completion. It is not observed token-stream overlap.

Quotable only with the mock caveat:

- measured strict-floor CPU split by dependency position for this harness
- the `POST_SERIAL` residue under this fixed scripted arm
- a generous potential-overlap upper bound formed from `PRE` plus
  `STREAM_OVERLAPPABLE`

Never quotable as production CPU share, production latency, realized latency
reduction, vendor inference behavior, or a substitute for real-streaming
validation. The unchanged 15 percent residual gate applies per c=1 run.
Every FAIL is rerun once and a persistent FAIL remains in the artifact.
