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

## Rehearsal ssh-parent check and the npu-1 hint

`Test-SeamProcessAncestor` walks four parent processes looking for
`sshd.exe`. A `powershell -File` on the ssh command adds a process, and
that walk then misses `sshd.exe`. The rehearsal refuses with
`REFUSED -- rehearsal -Detach must be started from ssh`. Invoke the
script in the ssh PowerShell:

```
.\tools\launch_t2s_npu1.ps1 -Detach -Rehearsal
```

not `powershell -NoProfile -File tools\launch_t2s_npu1.ps1`. The same
rule applies to every T2S launch and rehearsal, and to the XPS A5
commands. Found 2026-10-03. Not fixed yet.

Profile `npu-1` is not in `$script:RehearsalMac` in
`tools/launch_boot1.ps1`. The refusal hint falls through to the default,
which prints an XPS command for `tools\launch_boot4.ps1`. The T2S command
is `.\tools\launch_t2s_npu1.ps1`. Not fixed yet.

## Boot 1-3 det cells have no rehearsal smoke

Fixed 2026-10-04. Rehearsal of kind `det` calls `Invoke-DetProbe`, the same
function as a real cell, with a stub worker that prints `SMOKE_OK det` and
returns an `Exit` code. It no longer throws `REFUSED -- no rehearsal smoke`.

## NPU-1 attempt c3caa5fc crashed before any cell

Boot `c3caa5fc`. `T2S_NPU1_SUMMARY` state `crashed`, `cells` empty. Right
after the machine-lock check, strict mode threw `The property 'Exit' cannot
be found on this object`. `Invoke-NpuCell` left the worker stdout in its
return, so `$ran` was not the result object. Nothing was measured. Fixed:
worker stdout is captured and the result is `Get-BootCeilingResult`.
Rehearsal of `npu`, `det`, `ceiling`, and `control` now calls that same
invoker with a stub worker.
