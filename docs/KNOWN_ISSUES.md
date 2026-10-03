# Known issues

Open problems that are recorded but not yet fixed.

## Tests write tracked files

`tests/test_fdr_replay_d1.py` rewrites six tracked files in `derived/d1_replay/`
(`CLOUD_COST_FIT.md`, `CLOUD_RECONCILIATION.md`, `H1_PREDICTIONS.md`,
`X2_DECOMPOSITION.md`, `X2_REPLAY_CHECK.md`, `configs.json`). The only change
is the generated timestamp, but a full pytest run leaves the tree dirty, and
rule 5 forbids launching from a dirty tree. Until it is fixed, restore them
after a test run with `git checkout -- derived/d1_replay/`.
Found 2026-10-02 on the Mac clone. Confirmed 2026-10-03 on the XPS:
a full pytest run rewrote the same six files. Not fixed yet.

## R2C fake history is missing get_messages

`tools/bfcl_feasibility_probe.py` copies the resident history with
`resident_history.get_messages()` before appending the assistant turn.
`tests/test_r2c_turnwise_lifecycle.py` uses `_FakeChatHistory`, which does
not implement `get_messages`. On the XPS, where OpenVINO is installed, these
three tests fail with `AttributeError`:

- `test_openvino_backend_interleaved_lifecycle_no_leak`
- `test_three_policy_gold_tools_zero_instance_mismatch`
- `test_lifecycle_smoke_cli_helper`

The Mac suite does not reach this line (OpenVINO is not installed there).
Not fixed yet.
