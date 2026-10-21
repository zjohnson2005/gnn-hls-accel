#!/bin/bash
# XPS window 2 (Task AY; approved by Zach 2026-10-20 "continue"; $0, local only).
# Copy of run_window_20261020.sh, with the same safety checks, park/copy and uptime gate.
# Before the reboot (read-only, plus the approved py-spy fetch if the exe is missing):
#   - record the iGPU/NPU driver versions (the GPU hang analysis needs them);
#   - copy the 24c1abc0 full worker log to the Mac.
# Then reboot -> pull (EXPECT_HEAD) -> P3 cell 0 FIRST (true-default resident limit,
#   run_resident_limit --arm gpu_only --high 50000, no scheduler override; ~50 min DERIVED)
#   -> arm A LONGCTX_30 entries 124..148: the 15 not yet run. The launch is
#   -EntryOffset 14 -EntryCount 16 with 123 skipped via its recorded hang (Task AY part 3:
#   counted as a local fail with outcome hang). Uses -TurnWatchdogS 1800 and py-spy.
# Every launch starts below LAUNCH_MAX_UPTIME_S (gate 7,200 s); the long run may go past it.
# Durations measured on the XPS: arm A LONGCTX 14 entries 54.8 min (841b84e4), u4 14 entries
#   42.8 min (162a9b5c), so ~60 min for the 15 (DERIVED). P3 cell 0 NOT YET MEASURED.
# Stops at the first REFUSED / Traceback / ARM_A_INVALID / dirty tree / banned app / hang.
# Run with:  caffeinate -i bash ~/seam_closeout_1013/xps/run_window_w2.sh
#      or :  START_AT=a15 caffeinate -i bash ~/seam_closeout_1013/xps/run_window_w2.sh  (skip cell 0)
set -u
START_AT=${START_AT:-c0}          # c0 (cell 0, then a15) | a15 (arm A entries 124..148 only)
EXPECT_HEAD=3aa9e27   # commit the XPS must be at after the pull (Task AY)
WATCHDOG_S=1800                   # per-turn limit; longest measured healthy turn 469.4 s (841b84e4)
PYSPY=""
PYSPY_EXE='C:\Users\zjohn\seam_tools\py-spy.exe'
HANG_REC='derived\demo2_pilots\hung_24c1abc0\interleaved_24c1abc0-0613-4890-87b6-3da05350beda\hang_events.json'
HANG_REC_SHA=257e1e9dfc31d95afcbddf47b60ce6587b91d21f9d55981754ae461afdbb4ad1
LAUNCH_MAX_UPTIME_S=6900
X=zjohn@100.101.81.6
R='C:\Users\zjohn\Projects\gnn-hls-accel'
OUT=~/seam_closeout_1013/xps/window_$(date +%Y%m%d_%H%M)
mkdir -p "$OUT"
log(){ echo "[$(TZ=America/New_York date '+%m-%d %H:%M:%S ET')] $*" | tee -a "$OUT/steps.txt"; }
xs(){ ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 "$X" "$1" 2>&1 | tr -d '\r'; }
stop(){ log "STOP: $*"; exit 1; }

banned(){ xs 'Get-Process | Where-Object { $_.ProcessName -match "^(cursor|chrome|msedge|code|claude|python)$" } | Select-Object -ExpandProperty ProcessName' | sort -u | tr '\n' ' '; }
uptime_s(){ xs '[int]((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalSeconds' | tr -dc '0-9'; }
wait_python(){ local t0=$(date +%s); while true; do n=$(xs '@(Get-Process python -ErrorAction SilentlyContinue).Count' | tr -dc '0-9'); [ "${n:-0}" = "0" ] && break; [ $(( $(date +%s) - t0 )) -gt 14400 ] && stop "python still running after 4 h"; sleep 30; done; }
clean_tree(){ s=$(xs "cd $R; git status --porcelain"); [ -z "$s" ] || stop "dirty tree: $s"; }
park(){ log "park $1"; xs "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\zjohn\\seam_tools\\park_untracked.ps1 -Label $1" | tee "$OUT/park_$1.txt"; grep -q '^MODIFIED' "$OUT/park_$1.txt" && stop "tracked file modified after $1"; { scp -q -r "$X:C:/Users/zjohn/gnn_backup_demo2/pending_closeout/$1" "$OUT/" || scp -O -q -r "$X:C:/Users/zjohn/gnn_backup_demo2/pending_closeout/$1" "$OUT/"; } && log "copied $1 to Mac" || log "WARN copy of $1 failed; it is safe on the XPS in pending_closeout"; }
field(){ grep -m1 "^$1" "$2" | sed 's/^[^:]*: //' | tr -d '\r'; }
check_log(){ xs "Get-Content '$1' -Tail 120" > "$OUT/$2_logtail.txt"; if grep -q 'TURN_WATCHDOG_HANG' "$OUT/$2_logtail.txt"; then grep 'TURN_WATCHDOG_HANG' "$OUT/$2_logtail.txt" | tee -a "$OUT/steps.txt"; return 2; fi; if grep -E -q 'REFUSED|Traceback|ARM_A_INVALID|FAIL_CANARY' "$OUT/$2_logtail.txt"; then grep -E 'REFUSED|Traceback|ARM_A_INVALID|FAIL_CANARY' "$OUT/$2_logtail.txt" | head -5 | tee -a "$OUT/steps.txt"; return 1; fi; return 0; }
launch_h1(){ # $1 label, $2 args
  local lbl=$1; shift
  clean_tree; b=$(banned); [ -z "${b// }" ] || stop "banned before $lbl: $b"
  log "launch $lbl (uptime $(uptime_s) s)"
  xs "cd $R; powershell -NoProfile -File tools\\launch_h1.ps1 $*" > "$OUT/${lbl}_launch.txt"
  grep -q 'Spawned' "$OUT/${lbl}_launch.txt" || { grep -E 'REFUSED|refusal|FAILED' "$OUT/${lbl}_launch.txt" | head -5 | tee -a "$OUT/steps.txt"; park "${lbl}_refused"; stop "$lbl did not spawn"; }
  local rid=$(field 'session_id (run_id)' "$OUT/${lbl}_launch.txt"); local ll=$(field 'launch_log' "$OUT/${lbl}_launch.txt"); local ev=$(field 'launch_evidence_dir' "$OUT/${lbl}_launch.txt")
  log "$lbl run_id $rid"; echo "$lbl $rid" >> "$OUT/run_ids.txt"
  sleep 60; wait_python; log "$lbl worker exited"
  local ok=0; check_log "$ll" "$lbl" || ok=$?
  scp -q -r "$X:$(echo "$ev" | tr '\\' '/')" "$OUT/launch_${lbl}_$rid" 2>/dev/null
  scp -q "$X:$(echo "$ll" | tr '\\' '/')" "$OUT/${lbl}_worker.log" 2>/dev/null || log "WARN worker log copy failed for $lbl"
  park "$lbl"
  [ $ok -eq 2 ] && stop "$lbl: turn watchdog recorded a hang (outcome hang; see ${lbl}_logtail.txt); a further skip needs a new record"
  [ $ok -eq 0 ] || stop "$lbl log shows a refusal or error (see ${lbl}_logtail.txt)"
  log "$lbl OK"
}
gate_uptime(){ local U=$(uptime_s); [ "${U:-99999}" -lt $LAUNCH_MAX_UPTIME_S ] || stop "uptime $U s before $1: too close to the 7,200 s gate; run START_AT=$1 in the next window"; }

log "start (START_AT=$START_AT); output in $OUT"
case "$EXPECT_HEAD" in *PLACEHOLDER*) stop "EXPECT_HEAD not set in this script";; esac
ssh -o BatchMode=yes -o ConnectTimeout=15 "$X" hostname >/dev/null 2>&1 || stop "XPS not reachable over ssh before reboot (check tailscale status / that the XPS is on and awake)"
B64=$(base64 < ~/seam_closeout_1013/xps/tools/park_untracked.ps1 | tr -d '\n')
xs "New-Item -ItemType Directory -Force C:\\Users\\zjohn\\seam_tools | Out-Null; [IO.File]::WriteAllBytes('C:\\Users\\zjohn\\seam_tools\\park_untracked.ps1', [Convert]::FromBase64String('$B64')); (Get-FileHash C:\\Users\\zjohn\\seam_tools\\park_untracked.ps1).Hash" | tee "$OUT/park_tool_hash.txt"
grep -q -E '^[0-9A-F]{64}' "$OUT/park_tool_hash.txt" || stop "could not write park_untracked.ps1 on the XPS"

# Read-only records before the reboot (Task AY part 2).
xs 'Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass -eq "DISPLAY" -or $_.DeviceName -match "NPU" } | Select-Object DeviceName,DriverVersion,DriverDate,InfName,DeviceID | Format-List' | tee "$OUT/drivers.txt"
# GPU/NPU driver summary (Task AZ: the old grep -m2 printed the first two DriverVersion lines,
# which on the XPS are the HID input device and the NPU, not the GPU).
drv_summary(){ tr -d '\r' < "$1" | awk '/^DeviceName/{n=$0; sub(/^DeviceName *: */,"",n)} /^DriverVersion/{v=$0; sub(/^DriverVersion *: */,"",v); if (n ~ /Graphics|GPU|Arc|NPU/ && n !~ /Input/) printf "%s %s; ", n, v}'; }
grep -q 'DriverVersion' "$OUT/drivers.txt" && log "drivers recorded: $(drv_summary "$OUT/drivers.txt")" || log "WARN driver query returned nothing (see drivers.txt)"
scp -q "$X:C:/Users/zjohn/Projects/gnn-hls-accel/derived/h1_hybrid/_launches/h1_interleaved_20261020_152709.log" "$OUT/h1_interleaved_20261020_152709_24c1abc0.log" && log "copied 24c1abc0 full worker log" || log "WARN 24c1abc0 worker log copy failed (it stays on the XPS)"

# py-spy pre-step (approved 2026-10-20): standalone exe, download only if missing.
B64=$(base64 < ~/gnn-hls-accel/tools/get_pyspy.ps1 | tr -d '\n')
xs "[IO.File]::WriteAllBytes('C:\\Users\\zjohn\\seam_tools\\get_pyspy.ps1', [Convert]::FromBase64String('$B64')); powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\zjohn\\seam_tools\\get_pyspy.ps1; \"RC=\$LASTEXITCODE\"" | tee "$OUT/pyspy.txt"
PRC=$(grep -m1 '^RC=' "$OUT/pyspy.txt" | tr -dc '0-9')
if [ "$PRC" = "0" ] && grep -q '^PIP_FREEZE_UNCHANGED' "$OUT/pyspy.txt"; then
  PYSPY="$PYSPY_EXE"; log "py-spy ready: $(grep -m1 '^VERSION' "$OUT/pyspy.txt") $(grep -m1 '^SHA256' "$OUT/pyspy.txt")"
elif [ "$PRC" = "4" ]; then
  stop "pip freeze of .venv-seam changed during the py-spy fetch (see pyspy.txt)"
else
  log "py-spy not available (rc ${PRC:-none}; see pyspy.txt); continuing without -HangDumpPySpy"
fi

log "reboot"; xs 'shutdown /r /t 5' >/dev/null; sleep 90
T0=$(date +%s); until ssh -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "$X" hostname >/dev/null 2>&1; do [ $(( $(date +%s) - T0 )) -gt 900 ] && stop "XPS did not come back on ssh within 15 min of reboot (stuck at login, Windows Update, or Tailscale not starting before sign-in)"; sleep 10; done; log "XPS back"; sleep 60
for i in 1 2; do xs 'Get-Process chrome,msedge,claude -ErrorAction SilentlyContinue | Stop-Process -Force' >/dev/null; sleep 60; done
b=$(banned); [ -z "${b// }" ] || stop "banned apps still running after reboot: $b"
xs "cd $R; git pull --ff-only; git log -1 --format=%h" | tee "$OUT/pull.txt"; clean_tree
grep -q "^${EXPECT_HEAD:0:7}" "$OUT/pull.txt" || stop "XPS head is not $EXPECT_HEAD after the pull"
H=$(xs "cd $R; (Get-FileHash -Algorithm SHA256 $HANG_REC).Hash" | tr -dc '0-9A-F')
[ "$H" = "$(echo "$HANG_REC_SHA" | tr 'a-f' 'A-F')" ] || stop "hang record on the XPS has sha256 $H, expected $HANG_REC_SHA"

LONG='-Entries derived\h1_hybrid\demo1\DEMO1_LONGCTX_30.json'
COMMON='-Interleaved -InterleavedPolicies local_only -PolicyCapUsd local_only=0 -SessionMaxUsd 1 -Placement gpu_only -Residency RESIDENT'
ARM_A="$COMMON -Kv default -RequireTrueDefault"
TELE='-DebugRawText -MemTelemetry -GpuMemCounters'
WDA="-TurnWatchdogS $WATCHDOG_S"; [ -n "$PYSPY" ] && WDA="$WDA -HangDumpPySpy $PYSPY"
SKIP="-SkipEntries multi_turn_long_context_123 -SkipHangRecord $HANG_REC"

if [ "$START_AT" = "c0" ]; then
  # P3 cell 0 (added in Task AX): true-default resident limit, plain LLMPipeline(model, "GPU").
  lbl=p3_td_i8_unl
  cmd='run_resident_limit.py --arm gpu_only --model-spec configs\models\Qwen3-4B-int4-ov.yaml --high 50000'
  gate_uptime c0
  clean_tree; b=$(banned); [ -z "${b// }" ] || stop "banned before $lbl: $b"
  lg="derived\\c2_ttft\\_launches\\demo2_p3\\$lbl.log"
  log "launch $lbl (P3 cell 0; uptime $(uptime_s) s): $cmd"
  xs "cd $R; New-Item -ItemType Directory -Force derived\\c2_ttft\\_launches\\demo2_p3 | Out-Null; powershell -NoProfile -File tools\\spawn_detached.ps1 -CommandLine \"$R\\.venv-seam\\Scripts\\python.exe -u tools\\$cmd\" -LogPath $lg -WorkingDirectory $R" > "$OUT/${lbl}_launch.txt"
  sleep 60; wait_python; log "$lbl exited"
  ok=0; check_log "$R\\$lg" "$lbl" || ok=$?
  scp -q "$X:$(echo "$R\\$lg" | tr '\\' '/')" "$OUT/${lbl}.log" 2>/dev/null || log "WARN $lbl log copy failed"
  park "$lbl"
  [ $ok -eq 0 ] || stop "$lbl log shows a refusal or error (see ${lbl}_logtail.txt); after review run START_AT=a15"
  log "$lbl OK"
  START_AT=a15
fi
if [ "$START_AT" = "a15" ]; then
  # P6/P1/P8-i8: arm A on LONGCTX_30 index 14..29; 123 counted from 24c1abc0's hang record.
  gate_uptime a15; launch_h1 p6_longctx_124_148 $ARM_A $TELE $WDA $LONG -EntryOffset 14 -EntryCount 16 $SKIP
  log "window 2 done; next: window 3 (run_window_w3.sh, P10-HANG123), then START_AT=p3 P3_FROM=1 and p4 (run_window_20261020.sh)"
  exit 0
fi
stop "unknown START_AT=$START_AT"
