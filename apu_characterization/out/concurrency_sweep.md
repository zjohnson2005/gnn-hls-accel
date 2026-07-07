> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** This artifact used a mock or scripted decision path (no live OpenAI agent). Use only to verify instrumentation and invariants. Do not cite in papers, slides, or findings.

# Concurrency sweep (workers × remote search)

- audit pass: **YES**
- publishable_ok: **NO**
- platform: `win32`

## Configuration

- Backend: `scripted`
- Profile: `mixed` (payload: `locality_ablation`)
- Search locality: `remote`
- Sessions per batch: **2**
- Workers sweep: `[1, 2]`
- Seeds: `[0]`

**Baseline note:** replication and real-agent breakdown at c=1 use `workers=1` — 10 sessions run **sequentially** one-at-a-time. Higher workers values run that many sessions in parallel (up to 10).

## Results by workers (median [IQR] over seeds)

| workers | batch host CPU ms | batch wall s | TOOL % | ORCH % | ORCH meas | ORCH recon | harness strict % |
|--------:|------------------:|-------------:|-------:|-------:|----------:|-----------:|-----------------:|
| 1 | 421.9 [421.9–421.9] | 14.6 [14.6–14.6] | 3.7 | 70.4 | 44.4 | 25.9 | 85.2 |
| 2 | 328.1 [328.1–328.1] | 4.8 [4.8–4.8] | 0.0 | 81.0 | 42.9 | 38.1 | 95.2 |

Comparison type: **workers sweep** with optional distribution over seeds.
Denominators: batch host CPU ms = sum(session process_time); pooled % = category CPU / batch host CPU.


Full data: `concurrency_sweep.json`
Reproduce: `python -m apu_characterization.experiments.concurrency_sweep --backend scripted --profile mixed --seeds 0 --workers 1,2 --sessions 2 --search-locality remote --allow-dirty`
