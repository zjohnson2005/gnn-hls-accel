# Provenance follow-ups

## Canary output path

Launchers should write opening-canary output under that launch's run directory.
`derived/h1_hybrid/_canary_opening/` is a shared tracked path. A later launch
overwrites the previous opening canary, so the file mtime and the measurement
`utc` can diverge from the commit that last touched the path.

Done 2026-10-13 for tools/launch_h1.ps1: the opening canary and the gate JSON
go to `derived/h1_hybrid/_launches/<run_id>/` (gitignored), and the worker
hashes them into plan.json `git.launch_evidence`. The tracked
`derived/h1_hybrid/_canary_opening/` keeps the d482c621 copy.
