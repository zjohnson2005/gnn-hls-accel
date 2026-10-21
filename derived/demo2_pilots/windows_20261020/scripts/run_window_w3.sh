#!/bin/bash
# XPS window 3 (Task AY; approved by Zach 2026-10-20 "continue"; $0, local only, one entry).
# Pilot P10-HANG123, EXPLORATORY, registered before any run in
#   docs/amendments/DEMO2_PILOT_P10_HANG123_2026-10-20.md (DEMO2-PILOTS row).
# Entry multi_turn_long_context_123 alone (DEMO1_LONGCTX_30 -EntryOffset 14 -EntryCount 1),
# local_only, gpu_only, RESIDENT, -TurnWatchdogS 600 and py-spy, one launch per cell.
# Order C1..C6 (each a candidate fix), C0 (true default, expected to hang) last.
# A cell that hangs: recorded (hang_events.json, py-spy), parked, then the XPS is REBOOTED
#   before the next cell (a hung GPU may leave the driver wedged). No reboot otherwise.
# A cell that refuses or errors before turn 0: recorded as NOT_TESTED, parked, next cell.
# Decision rule (fixed in the registration): a knob avoids the hang if its cell completes
#   turn 0 within 600 s. Verdicts are written by the closeout, not by this script.
# Copy of run_window_20261020.sh (same safety checks, park/copy, uptime gate below 6,900 s).
# Run with:  caffeinate -i bash ~/seam_closeout_1013/xps/run_window_w3.sh
#      or :  W3_FROM=3 caffeinate -i bash ~/seam_closeout_1013/xps/run_window_w3.sh  (resume at a cell index)
set -u
W3_FROM=${W3_FROM:-0}
EXPECT_HEAD=3aa9e27
WATCHDOG_S=600
PYSPY=""
PYSPY_EXE='C:\Users\zjohn\seam_tools\py-spy.exe'
LAUNCH_MAX_UPTIME_S=6900
X=zjohn@100.101.81.6
R='C:\Users\zjohn\Projects\gnn-hls-accel'
OUT=~/seam_closeout_1013/xps/window_$(date +%Y%m%d_%H%M)_p10
mkdir -p "$OUT"
log(){ echo "[$(TZ=America/New_York date '+%m-%d %H:%M:%S ET')] $*" | tee -a "$OUT/steps.txt"; }
xs(){ ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 "$X" "$1" 2>&1 | tr -d '\r'; }
stop(){ log "STOP: $*"; exit 1; }

banned(){ xs 'Get-Process | Where-Object { $_.ProcessName -match "^(cursor|chrome|msedge|code|claude|python)$" } | Select-Object -ExpandProperty ProcessName' | sort -u | tr '\n' ' '; }
uptime_s(){ xs '[int]((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalSeconds' | tr -dc '0-9'; }
wait_python(){ local t0=$(date +%s); while true; do n=$(xs '@(Get-Process python -ErrorAction SilentlyContinue).Count' | tr -dc '0-9'); [ "${n:-0}" = "0" ] && break; [ $(( $(date +%s) - t0 )) -gt 7200 ] && stop "python still running after 2 h"; sleep 30; done; }
clean_tree(){ s=$(xs "cd $R; git status --porcelain"); [ -z "$s" ] || stop "dirty tree: $s"; }
park(){ log "park $1"; xs "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\zjohn\\seam_tools\\park_untracked.ps1 -Label $1" | tee "$OUT/park_$1.txt"; grep -q '^MODIFIED' "$OUT/park_$1.txt" && stop "tracked file modified after $1"; { scp -q -r "$X:C:/Users/zjohn/gnn_backup_demo2/pending_closeout/$1" "$OUT/" || scp -O -q -r "$X:C:/Users/zjohn/gnn_backup_demo2/pending_closeout/$1" "$OUT/"; } && log "copied $1 to Mac" || log "WARN copy of $1 failed; it is safe on the XPS in pending_closeout"; }
field(){ grep -m1 "^$1" "$2" | sed 's/^[^:]*: //' | tr -d '\r'; }
check_log(){ xs "Get-Content '$1' -Tail 160" > "$OUT/$2_logtail.txt"; if grep -q 'TURN_WATCHDOG_HANG' "$OUT/$2_logtail.txt"; then grep 'TURN_WATCHDOG_HANG' "$OUT/$2_logtail.txt" | tee -a "$OUT/steps.txt"; return 2; fi; if grep -E -q 'REFUSED|Traceback|ARM_A_INVALID|FAIL_CANARY' "$OUT/$2_logtail.txt"; then grep -E 'REFUSED|Traceback|ARM_A_INVALID|FAIL_CANARY' "$OUT/$2_logtail.txt" | head -5 | tee -a "$OUT/steps.txt"; return 1; fi; return 0; }
reboot_xps(){
  log "reboot ($1)"; xs 'shutdown /r /t 5' >/dev/null; sleep 90
  T0=$(date +%s); until ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "$X" hostname >/dev/null 2>&1; do [ $(( $(date +%s) - T0 )) -gt 2700 ] && stop "XPS did not come back on ssh within 45 min of reboot (stuck at login, Windows Update, or Tailscale not starting before sign-in)"; sleep 10; done; log "XPS back"; sleep 60
  for i in 1 2; do xs 'Get-Process chrome,msedge,claude -ErrorAction SilentlyContinue | Stop-Process -Force' >/dev/null; sleep 60; done
  b=$(banned); [ -z "${b// }" ] || stop "banned apps still running after reboot: $b"
}
cell(){ # $1 label, rest: launch_h1 args. Returns 0 completed, 2 hang, 1 refused/error.
  local lbl=$1; shift
  clean_tree; b=$(banned); [ -z "${b// }" ] || stop "banned before $lbl: $b"
  log "launch $lbl (uptime $(uptime_s) s)"
  xs "cd $R; powershell -NoProfile -File tools\\launch_h1.ps1 $*" > "$OUT/${lbl}_launch.txt"
  if ! grep -q 'Spawned' "$OUT/${lbl}_launch.txt"; then
    grep -E 'REFUSED|refusal|FAILED' "$OUT/${lbl}_launch.txt" | head -5 | tee -a "$OUT/steps.txt"
    park "${lbl}_refused"; log "$lbl NOT_TESTED (did not spawn)"; return 1
  fi
  local rid=$(field 'session_id (run_id)' "$OUT/${lbl}_launch.txt"); local ll=$(field 'launch_log' "$OUT/${lbl}_launch.txt"); local ev=$(field 'launch_evidence_dir' "$OUT/${lbl}_launch.txt")
  log "$lbl run_id $rid"; echo "$lbl $rid" >> "$OUT/run_ids.txt"
  sleep 60; wait_python; log "$lbl worker exited"
  local ok=0; check_log "$ll" "$lbl" || ok=$?
  scp -q -r "$X:$(echo "$ev" | tr '\\' '/')" "$OUT/launch_${lbl}_$rid" 2>/dev/null
  scp -q "$X:$(echo "$ll" | tr '\\' '/')" "$OUT/${lbl}_worker.log" 2>/dev/null || log "WARN worker log copy failed for $lbl"
  park "$lbl"
  case $ok in
    0) log "$lbl completed (no hang recorded)";;
    2) log "$lbl HANG recorded";;
    *) log "$lbl NOT_TESTED or error (see ${lbl}_logtail.txt)";;
  esac
  return $ok
}

log "start P10-HANG123 (W3_FROM=$W3_FROM); output in $OUT"
case "$EXPECT_HEAD" in *PLACEHOLDER*) stop "EXPECT_HEAD not set in this script";; esac
ssh -o BatchMode=yes -o ConnectTimeout=15 "$X" hostname >/dev/null 2>&1 || stop "XPS not reachable over ssh before reboot (check tailscale status / that the XPS is on and awake)"
B64=$(base64 < ~/seam_closeout_1013/xps/tools/park_untracked.ps1 | tr -d '\n')
xs "New-Item -ItemType Directory -Force C:\\Users\\zjohn\\seam_tools | Out-Null; [IO.File]::WriteAllBytes('C:\\Users\\zjohn\\seam_tools\\park_untracked.ps1', [Convert]::FromBase64String('$B64')); (Get-FileHash C:\\Users\\zjohn\\seam_tools\\park_untracked.ps1).Hash" | tee "$OUT/park_tool_hash.txt"
grep -q -E '^[0-9A-F]{64}' "$OUT/park_tool_hash.txt" || stop "could not write park_untracked.ps1 on the XPS"
xs 'Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass -eq "DISPLAY" -or $_.DeviceName -match "NPU" } | Select-Object DeviceName,DriverVersion,DriverDate,InfName,DeviceID | Format-List' > "$OUT/drivers.txt"
# GPU/NPU driver summary (Task AZ: the old grep -m2 printed the first two DriverVersion lines,
# which on the XPS are the HID input device and the NPU, not the GPU).
drv_summary(){ tr -d '\r' < "$1" | awk '/^DeviceName/{n=$0; sub(/^DeviceName *: */,"",n)} /^DriverVersion/{v=$0; sub(/^DriverVersion *: */,"",v); if (n ~ /Graphics|GPU|Arc|NPU/ && n !~ /Input/) printf "%s %s; ", n, v}'; }
grep -q 'DriverVersion' "$OUT/drivers.txt" && log "drivers recorded: $(drv_summary "$OUT/drivers.txt")" || log "WARN driver query returned nothing (see drivers.txt)"
B64=$(base64 < ~/gnn-hls-accel/tools/get_pyspy.ps1 | tr -d '\n')
xs "[IO.File]::WriteAllBytes('C:\\Users\\zjohn\\seam_tools\\get_pyspy.ps1', [Convert]::FromBase64String('$B64')); powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\zjohn\\seam_tools\\get_pyspy.ps1; \"RC=\$LASTEXITCODE\"" | tee "$OUT/pyspy.txt"
PRC=$(grep -m1 '^RC=' "$OUT/pyspy.txt" | tr -dc '0-9')
if [ "$PRC" = "0" ] && grep -q '^PIP_FREEZE_UNCHANGED' "$OUT/pyspy.txt"; then PYSPY="$PYSPY_EXE"; log "py-spy ready"
elif [ "$PRC" = "4" ]; then stop "pip freeze of .venv-seam changed during the py-spy fetch (see pyspy.txt)"
else log "py-spy not available (rc ${PRC:-none}); cells run without -HangDumpPySpy"; fi

reboot_xps "window start"
xs "cd $R; git pull --ff-only; git log -1 --format=%h" | tee "$OUT/pull.txt"; clean_tree
grep -q "^${EXPECT_HEAD:0:7}" "$OUT/pull.txt" || stop "XPS head is not $EXPECT_HEAD after the pull"

ONE='-Entries derived\h1_hybrid\demo1\DEMO1_LONGCTX_30.json -EntryOffset 14 -EntryCount 1'
COMMON='-Interleaved -InterleavedPolicies local_only -PolicyCapUsd local_only=0 -SessionMaxUsd 1 -Placement gpu_only -Residency RESIDENT -DebugRawText -MemTelemetry -GpuMemCounters'
WD="-TurnWatchdogS $WATCHDOG_S"; [ -n "$PYSPY" ] && WD="$WD -HangDumpPySpy $PYSPY"
UNL=18446744073709551615
CELLS=(
  "p10_c1_prefix_off|-Kv default -CompiledReadback -SchedExploratory -SchedPrefixCaching off -SchedMaxBatchedTokens $UNL"
  "p10_c2_chunk4096|-Kv default -CompiledReadback -SchedPrefixCaching on -SchedMaxBatchedTokens 4096"
  "p10_c3_chunk256|-Kv default -CompiledReadback -SchedPrefixCaching on -SchedMaxBatchedTokens 256"
  "p10_c4_kv_u4|-Kv u4 -CompiledReadback"
  "p10_c5_kv_f16|-Kv f16 -CompiledReadback"
  "p10_c6_splitfuse_off|-Kv default -CompiledReadback -SchedExploratory -SchedPrefixCaching on -SchedMaxBatchedTokens $UNL -SchedDynamicSplitFuse off"
  "p10_c0_true_default|-Kv default -RequireTrueDefault"
)
for ((i=W3_FROM; i<${#CELLS[@]}; i++)); do
  lbl=${CELLS[$i]%%|*}; args=${CELLS[$i]#*|}
  U=$(uptime_s); [ "${U:-99999}" -lt $LAUNCH_MAX_UPTIME_S ] || stop "uptime $U s before $lbl: resume with W3_FROM=$i in the next window"
  rc=0; cell "$lbl" $COMMON $args $WD $ONE || rc=$?
  echo "$lbl rc=$rc" >> "$OUT/cells.txt"
  if [ $rc -eq 2 ] && [ $((i + 1)) -lt ${#CELLS[@]} ]; then reboot_xps "after hang in $lbl"; clean_tree; fi
done
log "P10-HANG123 cells done (cells.txt); closeout applies the registered rule"
exit 0
