# `raw/` — WRITE-ONCE

Governed by blueprint §5.3 and implementation spec §9.1.

## The rule

**Never modify a file under `raw/` after its run completes.** Raw data is append-only while a run
is in progress and immutable the moment it is sealed. This is not a style preference; it is the
property that makes every downstream number auditable.

## Layout

```
raw/
├── _blinding/              # condition -> blinded label mapping and salt (salt is gitignored)
└── <run_id>/               # one uuid4 directory per run
    ├── manifest.json       # blueprint §5.2 / spec §6.1 — the run's identity
    ├── summary.json        # run-specific results
    ├── samples.ndjson      # telemetry time series (M2 onward)
    ├── steps.ndjson        # per-agent-step records (M3 onward)
    ├── events.ndjson       # structured log of what happened during the run
    └── .sealed             # seal marker: tree hash, file list, self-check verdict
```

## How the guard works

`seam/rawstore.py` enforces two layers:

1. **Advisory** — the `.sealed` marker. Every mutating method checks for it and raises
   `RunSealedError` on *attempt*, before any bytes are written, so a sealed run cannot be partially
   corrupted by a refused write.
2. **Best-effort OS enforcement** — files are marked read-only at seal time, which stops a script
   or editor that never asked `rawstore` for permission.

Neither layer defends against a determined attacker, and neither is meant to. They defend against
the realistic failure: a well-intentioned later script appending "just one fix" to finished data.

## If data is wrong

Do not edit it. Emit a **new** run and record the supersession in `AUDIT_LOG.md`. A run may be
*excluded* from primary analysis — for throttle residency above threshold, harness self-check
failure, or API error (blueprint §5.3) — but exclusion means flagged and counted in the paper, never
deleted. Post-hoc discarding of inconvenient values is misconduct.

## Integrity checks

`seam.rawstore.verify_sealed()` recomputes a sealed run's tree hash and compares it against the
recorded value. Blueprint §5.6 item 3 requires this weekly.
