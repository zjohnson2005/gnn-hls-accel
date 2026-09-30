# Measurement mode — driving the XPS from the Mac

**A mode, not a reconfiguration.** The XPS stays a normal development machine. For runs where
contention would swamp the effect, you enter measurement mode: close everything on the XPS, drive
it from the Mac over SSH, and never open a session on it while it runs.

Setting this up costs nothing when you are not using it. SSH being enabled does not affect local
use.

---

## When measurement mode is required

Not a list of experiments — a criterion:

> **Any run whose primary endpoint is timing or memory, or whose result feeds a comparison,
> requires measurement mode.**

That covers throughput measurement, context-ceiling determination, canary baselines, and every
cross-configuration comparison. It does not cover development, tests, smoke runs, or anything
untimed — work on the XPS normally for those.

## The rule that makes it matter

**`isolation_mode` is recorded in every manifest as `remote` or `local`, and results from different
modes are never pooled or compared.**

This is not bookkeeping. The two prior runs behind the unexplained **1.98×** differed in machine
state, not configuration. If some runs happen with Cursor open and some without, that difference
re-enters every comparison silently — which is exactly the failure this mode exists to prevent.

A comparison spanning modes is invalid regardless of how clean each half looks.

Enforced in `seam/isolation.py`, not left to discipline:

- **No default.** `emit()` refuses without a declaration, from `SEAM_ISOLATION_MODE` or an explicit
  argument. A defaulted mode would mislabel exactly the runs the field exists to keep apart.
- **A contradicted declaration is refused.** Declaring `remote` with an editor resident stops the
  run and names the processes to close. The evidence is recorded on runs that pass, and the schema
  rejects a manifest that claims `remote` while listing contending processes — so the
  contradiction cannot exist in `raw/` at all.
- **`assert_poolable()` refuses cross-mode comparison**, and refuses a run predating the field:
  an unknown machine state is precisely what cannot be pooled.

---

## One-time setup

### 1 — SSH server on the XPS (**admin** PowerShell)

```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH*'
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
Get-NetFirewallRule -Name *ssh* | Select-Object Name, Enabled, Direction, Action
```

If the firewall rule is missing:

```powershell
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' `
  -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

### 2 — PowerShell as the default shell

Otherwise every remote command lands in `cmd.exe` and needs wrapping.

```powershell
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell `
  -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -PropertyType String -Force
```

### 3 — Address

```powershell
ipconfig | Select-String IPv4
```

Set a **DHCP reservation** on your router so the address does not move.

### 4 — Key on the Mac

```bash
ssh-keygen -t ed25519 -C "mac-to-xps" -f ~/.ssh/xps
cat ~/.ssh/xps.pub
```

### 5 — Install the key — **the step that silently fails**

Administrator accounts do **not** use `~/.ssh/authorized_keys`. Windows OpenSSH reads
`C:\ProgramData\ssh\administrators_authorized_keys`, and it **refuses the key without any error**
if that file's permissions are not restricted to Administrators and SYSTEM. You get a password
prompt and no explanation.

XPS, **admin** PowerShell:

```powershell
$key = 'ssh-ed25519 AAAA... mac-to-xps'   # the full line from step 4
$f = 'C:\ProgramData\ssh\administrators_authorized_keys'

Add-Content -Path $f -Value $key
icacls $f /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
icacls $f
```

### 6 — Mac config and test

`~/.ssh/config`:

```
Host xps
    HostName 192.168.1.XXX
    User zjohn
    IdentityFile ~/.ssh/xps
    ServerAliveInterval 60
    ServerAliveCountMax 10
```

```bash
ssh xps "hostname; (Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue"
```

A password prompt means the key is not being read — return to step 5.

### 7 — Sleep settings (**admin** PowerShell, one-time)

An unattended run dies if the machine sleeps or the lid closes.

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 15
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
```

Screen-off is fine and preferable. Sleep is not. These settings are harmless during normal use.

---

## Entering measurement mode

1. On the XPS: **close Cursor, browsers, and anything syncing.** Cursor alone was ~3 GB.
2. From the Mac, confirm the machine is actually quiet:

```bash
ssh xps "Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 2 -MaxSamples 5; Get-Counter '\Memory\Available MBytes' -SampleInterval 2 -MaxSamples 3"
```

3. Launch detached, from the Mac:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; <launch command>"
```

Boot 4 rehearsal is the same ssh session plus WMI detach. Do not start `-Rehearsal` from the Cursor terminal; that process is refused.

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_boot4.ps1 -Detach -Rehearsal"
ssh xps "powershell -NoProfile -Command Get-Content -Tail 50 C:/Users/zjohn/Projects/gnn-hls-accel/derived/c2_ttft/_launches/_rehearsal/boot4/boot4.log"
```

Resident-limit rehearsal uses the same path:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_resident_limit.ps1 -Detach -Rehearsal"
ssh xps "powershell -NoProfile -Command Get-Content -Tail 50 C:/Users/zjohn/Projects/gnn-hls-accel/derived/c2_ttft/_launches/_rehearsal/resident-limit/resident-limit.log"
```

`REHEARSAL_COMPLETE` in that log is the success line. `-Detach` returns as soon as `Win32_Process.Create` has spawned the sequencer.

**Use `tools/spawn_detached.ps1`, never `Start-Process`.** See "Detachment" below — this is
measured, not assumed.

4. **Do not touch the XPS.** Poll from the Mac:

```bash
ssh xps "Get-Content C:/Users/zjohn/Projects/gnn-hls-accel/derived/<track>/heartbeat_<run_id>.json"
```

5. When it finishes, read results over SSH or reopen Cursor on the XPS — the run is sealed by then.

**Step 4 is the whole point.** Reopening Cursor to check progress was itself contaminating runs.

## Exiting

Nothing to undo. Reopen what you closed and work normally. SSH stays enabled; it costs nothing idle.

---

## Where the agent runs

**Default: leave the agent on the XPS.** It prepares the code and the launch command, you enter
measurement mode, launch and poll from the Mac, then reopen Cursor and paste results back. That is
the smallest change from how you already work, and it removes the one contaminating step.

**Optional, for a long campaign:** clone the repo to the Mac and run the agent there, driving the
XPS entirely over SSH. Git over SSH is the sync path — `rsync` is not available on Windows by
default. This forces the commit outstanding since 2026-07-30 (the `AMENDMENTS.md` /
blueprint §14 dual-definition collision is resolved — AMENDMENTS-side content reissued as
AM-033 / AM-034), so do not take this route casually.

```bash
git clone ssh://xps/C:/Users/zjohn/Projects/gnn-hls-accel
```

```powershell
# XPS, only if you want to push to it
git config receive.denyCurrentBranch updateInstead
```

The XPS copy stays canonical for `raw/`.

---

## Detachment

The whole workflow rests on a launched run outliving the SSH session. That is not automatic.
Win32-OpenSSH places a session's processes into a job object, and a job with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` terminates every member the instant the connection drops.
`Start-Process` children stay inside that job and die with it.

**Measured, not assumed.** `tools/_job_teardown_probe.py` builds a kill-on-close job, assigns
itself to it, spawns one heartbeat writer with `subprocess` (the `Start-Process` equivalent) and
one through the WMI service, then exits so the job tears down:

| launch path | after teardown |
| --- | --- |
| `subprocess` / `Start-Process` | heartbeat frozen at tick 4, process dead |
| `Win32_Process.Create` | tick advancing (18 → 22), process alive |

`tools/spawn_detached.ps1` therefore launches through the WMI service. The new process is
parented to `WmiPrvSE.exe` and was never a member of the session's job, so there is nothing for a
teardown to reach. The cost is that `Win32_Process.Create` cannot redirect output, so the command
is wrapped in `cmd.exe`, which is why every launcher must supply a log path.

End-to-end confirmation over a real SSH session, run once:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -File tools/verify_detach.ps1 -Start"
# the session closes here — this is the event under test
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -File tools/verify_detach.ps1 -Check"
```

`-Start` returning promptly is itself part of the test: an SSH command that hangs means the
spawned process is holding the session's output handle, which breaks the workflow even when the
process survives.

## Acceptance test

One fixed configuration — same prompt, same config, sealed — measured twice, twenty minutes
apart. From the Mac, with the XPS closed down:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -File tools/acceptance.ps1"
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -File tools/acceptance.ps1 -Status"

sleep 1200

ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -File tools/acceptance.ps1"
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -File tools/acceptance.ps1 -Status"

ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -File tools/acceptance.ps1 -Compare"
```

Each launch declares `isolation_mode=remote` and refuses if an editor or browser is resident.
`-Compare` refuses outright if the two runs differ in isolation mode, config hash, prompt hash or
working-set lock, so a ratio is never produced for runs that are not the same measurement.

Reported: `R_prefill` and `R_decode`, per repeat and as medians. **1.98× is the number to beat.**

### The bound is derived, not asserted

Same discipline as the paging and canary gates — baseline first, threshold from the baseline,
both in the manifest:

- `s` = the larger of the two runs' within-run relative spread on the basis metric (`r_decode_tok_s`).
  The estimator is CV = sd/|mean|, which is what the harness already computes
  (`seam.analysis.slice_stats.coefficient_of_variation`). MAD/median appears nowhere in the
  codebase, and at three repeats it degenerates to the smaller of the two non-zero deviations,
  which would bias the band low and manufacture failures.
- `band` = 2 × `s`.
- **PASS iff `|ratio − 1| ≤ band` and `s ≤ 0.10`.**

The second condition is not redundant. `|ratio − 1| ≤ 2s` alone can be satisfied by making `s`
large, so a sufficiently noisy pair would pass on the strength of its own noise. A wide band
derived from a noisy run is a machine that cannot support a claim, not a pass.

An underivable band — fewer than two repeats yielding a rate in either run — is `INDETERMINATE`,
never a pass.

`--compare` seals its own run. `s`, the band and the ratio exist in neither source run alone, so
without a manifest of their own they would be numbers with no `run_id` behind them. The sealed
verdict carries every input to the bound, so it can be recomputed without the source runs. The
prefill ratio is derived and recorded the same way but does not gate; a prefill result that
disagrees with the decode verdict says which part of the pipeline moved.

Also record the XPS at rest in each mode — CPU and available memory with Cursor open versus closed.
The delta between them is the justification for the mode, and it belongs in the C9 ledger.

## What this does not fix

Windows' own background stack stays: Defender, `aihost`, `aicontext`, McAfee. Those still want the
measurement user account and possibly reserved CPU sets, per `CURSOR_PROMPT_isolation.md`.

They were the smaller half. `mc-fw-host` was roughly 12% of one machine; Cursor was roughly 20% of
RAM plus your own activity on top.
