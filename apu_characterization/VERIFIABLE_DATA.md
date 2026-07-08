# Verifiable data policy

Non-negotiable rule for papers, slides, advisor reviews, and concurrency-sweep gates:

**Synthetic and mock decision paths are for instrumentation testing only.**
They are never quotable experimental results.

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

Do not start the workers sweep until **verifiable** v2 replication exists (`replication_remote_search_v2.json`, audit PASS, live OpenAI, RESIDUAL_UNATTRIBUTED below 15% per session). Synthetic concurrency smokes are debug only.
