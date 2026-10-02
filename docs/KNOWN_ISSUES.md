# Known issues

Open problems that are recorded but not yet fixed.

## Tests write tracked files

`tests/test_fdr_replay_d1.py` rewrites six tracked files in `derived/d1_replay/`
(`CLOUD_COST_FIT.md`, `CLOUD_RECONCILIATION.md`, `H1_PREDICTIONS.md`,
`X2_DECOMPOSITION.md`, `X2_REPLAY_CHECK.md`, `configs.json`). The only change
is the generated timestamp, but a full pytest run leaves the tree dirty, and
rule 5 forbids launching from a dirty tree. Until it is fixed, restore them
after a test run with `git checkout -- derived/d1_replay/`.
Found 2026-10-02 on the Mac clone. Not fixed yet.
