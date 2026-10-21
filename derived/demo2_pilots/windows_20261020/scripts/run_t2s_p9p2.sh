#!/bin/bash
# T2S block Oct 19-25 (Task AY part 7; Rithwik confirmed the block in writing; all $0, local only).
# Hand the T2S back clean by midnight ET Oct 25 (Rithwik has it Oct 26 - Nov 8).
# Same structure and safety as the XPS window scripts. Differences:
#   - NO reboot unless REBOOT_OK=1 (Tailscale unattended mode is NOT confirmed).
#   - Nothing is killed on the T2S. Any banned app, any python, or any of Rithwik's processes
#     (t2s_r2_agent.py, ollama) -> STOP. Rithwik's watchdog task and files are never touched;
#     only its read-only launch-check runs (as launch_h1 -T2S does).
#   - launch_h1 -T2S: the uptime gate is skipped and recorded as UNCOLD_UPTIME (launcher rule).
#     run_decode_match (P9, P2) runs the full gates, uptime included (7,200 s), so P9/P2 need
#     one of these, set by Zach: REBOOT_OK=1 (reboot first, cold launch) or UNCOLD_OK=1
#     (--uncold-uptime-deviation, recorded in the gates and the plan). With neither, they are
#     skipped and logged.
#   - Entry 123 is not skipped via the XPS hang record on this host (that record is an XPS
#     outcome). LONGCTX_30 runs as two chunks around it (index 0-13 and 15-29). Then 123 runs
#     alone as the LAST steps (i8, then u4) with -TurnWatchdogS 600: a direct cross-device
#     check of the hang. It goes last because a hang may wedge the driver and there is no reboot.
#   - No py-spy on the T2S (approved for the XPS only).
# Steps: a read-only | b pin restore + pull | c P0a readback | d P0b smoke | e P9 drift |
#   f arm A BASE_30 + LONGCTX_30 (chunks) | g P8-u4 BASE_30 + LONGCTX_30 (chunks), P4, P2 |
#   h entry 123 alone (i8, then u4). Each step stops the script on any refusal.
# Output: ~/seam_closeout_1013/t2s/window_<stamp>/ ; resume with STEP_FROM=<a..h>.
# Run with:  caffeinate -i bash ~/seam_closeout_1013/xps/run_window_t2s.sh
#      or :  UNCOLD_OK=1 STEP_FROM=e caffeinate -i bash ~/seam_closeout_1013/xps/run_window_t2s.sh
set -u
STEP_FROM=${STEP_FROM:-a}
REBOOT_OK=${REBOOT_OK:-0}
UNCOLD_OK=${UNCOLD_OK:-0}
EXPECT_HEAD=3aa9e27
PIN_SHA=CC74A37ED84ED95B0F4DD4B8D7EB774F2737230DCFCA01321FE136CDBFBCA447
WATCHDOG_S=1800
LAUNCH_MAX_UPTIME_S=6900
X=zach@100.72.40.24
R='C:\Users\zach\Projects\gnn-hls-accel'
PY="$R\\.venv-seam\\Scripts\\python.exe"
OUT=~/seam_closeout_1013/t2s/window_$(date +%Y%m%d_%H%M)
mkdir -p "$OUT"
log(){ echo "[$(TZ=America/New_York date '+%m-%d %H:%M:%S ET')] $*" | tee -a "$OUT/steps.txt"; }
xs(){ ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 "$X" "$1" 2>&1 | tr -d '\r'; }
stop(){ log "STOP: $*"; exit 1; }
after(){ [[ "$1" > "$STEP_FROM" || "$1" == "$STEP_FROM" ]]; }   # run step $1 when >= STEP_FROM

banned(){ xs 'Get-Process | Where-Object { $_.ProcessName -match "^(cursor|chrome|msedge|code|claude|python|ollama.*)$" } | Select-Object -ExpandProperty ProcessName' | sort -u | tr '\n' ' '; }
# GPU/NPU driver summary (Task AZ: the old grep -m2 printed the first two DriverVersion lines,
# which on the XPS are the HID input device and the NPU, not the GPU).
drv_summary(){ tr -d '\r' < "$1" | awk '/^DeviceName/{n=$0; sub(/^DeviceName *: */,"",n)} /^DriverVersion/{v=$0; sub(/^DriverVersion *: */,"",v); if (n ~ /Graphics|GPU|Arc|NPU/ && n !~ /Input/) printf "%s %s; ", n, v}'; }
rithwik(){ xs 'Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -match "t2s_r2_agent" -or $_.Name -match "^ollama") } | ForEach-Object { "{0} {1}" -f $_.ProcessId, $_.Name }' | tr '\n' ' '; }
watchdog_ok(){ xs "cd $R; \$n = @(Get-Process -Name python, llama-server -ErrorAction SilentlyContinue | ForEach-Object { \$_.ProcessName }); if (\$n.Count -eq 0) { \$j = '[]' } else { \$j = ConvertTo-Json -InputObject @(\$n) -Compress }; & '$PY' tools\\t2s_queue_watchdog.py launch-check --log C:\\apu\\ovn\\watchdog.log --running-json \$j; \"RC=\$LASTEXITCODE\"" > "$OUT/watchdog_check_$1.txt"; grep -q '^RC=0' "$OUT/watchdog_check_$1.txt"; }
guard(){ # before every launch: nothing of Rithwik's, no banned app, watchdog idle
  local r=$(rithwik); [ -z "${r// }" ] || stop "Rithwik's process running before $1: $r"
  local b=$(banned); [ -z "${b// }" ] || stop "banned/foreign process before $1: $b (nothing is killed on the T2S)"
  watchdog_ok "$1" || stop "T2S watchdog launch-check refused before $1 (see watchdog_check_$1.txt)"
}
uptime_s(){ xs '[int]((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalSeconds' | tr -dc '0-9'; }
wait_python(){ local t0=$(date +%s); while true; do n=$(xs '@(Get-Process python -ErrorAction SilentlyContinue).Count' | tr -dc '0-9'); [ "${n:-0}" = "0" ] && break; [ $(( $(date +%s) - t0 )) -gt 14400 ] && stop "python still running after 4 h"; sleep 30; done; }
clean_tree(){ s=$(xs "cd $R; git status --porcelain"); [ -z "$s" ] || stop "dirty tree: $s"; }
park(){ log "park $1"; xs "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\zach\\seam_tools\\park_untracked_t2s.ps1 -Label $1" | tee "$OUT/park_$1.txt"; grep -q '^MODIFIED' "$OUT/park_$1.txt" && stop "tracked file modified after $1"; { scp -q -r "$X:C:/Users/zach/gnn_backup_demo2/pending_closeout/$1" "$OUT/" || scp -O -q -r "$X:C:/Users/zach/gnn_backup_demo2/pending_closeout/$1" "$OUT/"; } && log "copied $1 to Mac" || log "WARN copy of $1 failed; it is safe on the T2S in pending_closeout"; }
field(){ grep -m1 "^$1" "$2" | sed 's/^[^:]*: //' | tr -d '\r'; }
check_log(){ xs "Get-Content '$1' -Tail 160" > "$OUT/$2_logtail.txt"; if grep -q 'TURN_WATCHDOG_HANG' "$OUT/$2_logtail.txt"; then grep 'TURN_WATCHDOG_HANG' "$OUT/$2_logtail.txt" | tee -a "$OUT/steps.txt"; return 2; fi; if grep -E -q 'REFUSED|Traceback|ARM_A_INVALID|FAIL_CANARY' "$OUT/$2_logtail.txt"; then grep -E 'REFUSED|Traceback|ARM_A_INVALID|FAIL_CANARY' "$OUT/$2_logtail.txt" | head -5 | tee -a "$OUT/steps.txt"; return 1; fi; return 0; }
on_hang(){ # $1 label
  if [ "$REBOOT_OK" = "1" ]; then reboot_t2s "after hang in $1"; else stop "$1: turn watchdog recorded a hang; no reboot (REBOOT_OK unset); the driver may be wedged"; fi
}
launch_h1(){ # $1 label, rest: launch_h1 args (always -T2S)
  local lbl=$1; shift
  clean_tree; guard "$lbl"
  log "launch $lbl (uptime $(uptime_s) s)"
  xs "cd $R; powershell -NoProfile -File tools\\launch_h1.ps1 -T2S $*" > "$OUT/${lbl}_launch.txt"
  grep -q 'Spawned' "$OUT/${lbl}_launch.txt" || { grep -E 'REFUSED|refusal|FAILED' "$OUT/${lbl}_launch.txt" | head -5 | tee -a "$OUT/steps.txt"; park "${lbl}_refused"; stop "$lbl did not spawn"; }
  local rid=$(field 'session_id (run_id)' "$OUT/${lbl}_launch.txt"); local ll=$(field 'launch_log' "$OUT/${lbl}_launch.txt"); local ev=$(field 'launch_evidence_dir' "$OUT/${lbl}_launch.txt")
  log "$lbl run_id $rid"; echo "$lbl $rid" >> "$OUT/run_ids.txt"
  sleep 60; wait_python; log "$lbl worker exited"
  local ok=0; check_log "$ll" "$lbl" || ok=$?
  scp -q -r "$X:$(echo "$ev" | tr '\\' '/')" "$OUT/launch_${lbl}_$rid" 2>/dev/null
  scp -q "$X:$(echo "$ll" | tr '\\' '/')" "$OUT/${lbl}_worker.log" 2>/dev/null || log "WARN worker log copy failed for $lbl"
  park "$lbl"
  [ $ok -eq 2 ] && { on_hang "$lbl"; return 2; }
  [ $ok -eq 0 ] || stop "$lbl log shows a refusal or error (see ${lbl}_logtail.txt)"
  log "$lbl OK"
}
detached(){ # $1 label, $2 log path (repo-relative), $3 python args
  local lbl=$1 lg=$2 cmd=$3
  clean_tree; guard "$lbl"
  log "launch $lbl (uptime $(uptime_s) s): $cmd"
  xs "cd $R; New-Item -ItemType Directory -Force (Split-Path $lg) | Out-Null; powershell -NoProfile -File tools\\spawn_detached.ps1 -CommandLine \"set SEAM_LAUNCH_CONTEXT=ssh_detached&& set SEAM_PLATFORM_ID=evo-t2&& $PY -u $cmd\" -LogPath $lg -WorkingDirectory $R" > "$OUT/${lbl}_launch.txt"
  sleep 60; wait_python; log "$lbl exited"
  local ok=0; check_log "$R\\$lg" "$lbl" || ok=$?
  scp -q "$X:$(echo "$R\\$lg" | tr '\\' '/')" "$OUT/${lbl}.log" 2>/dev/null || log "WARN $lbl log copy failed"
  park "$lbl"
  [ $ok -eq 0 ] || stop "$lbl log shows a refusal or error (see ${lbl}_logtail.txt)"
  log "$lbl OK"
}
reboot_t2s(){
  [ "$REBOOT_OK" = "1" ] || stop "reboot needed ($1) but REBOOT_OK is not set"
  log "reboot ($1; REBOOT_OK=1 set by Zach)"; xs 'shutdown /r /t 5' >/dev/null; sleep 90
  T0=$(date +%s); until ssh -o BatchMode=yes -o ConnectTimeout=5 "$X" hostname >/dev/null 2>&1; do [ $(( $(date +%s) - T0 )) -gt 900 ] && stop "T2S did not come back on ssh within 15 min of reboot"; sleep 10; done; log "T2S back"; sleep 120
}
decode_pilot(){ # $1 label, $2 log, $3 run_decode_match args: P9/P2 need REBOOT_OK or UNCOLD_OK
  if [ "$REBOOT_OK" = "1" ]; then
    reboot_t2s "cold launch for $1"
    local U=$(uptime_s); [ "${U:-99999}" -lt $LAUNCH_MAX_UPTIME_S ] || stop "uptime $U s before $1"
    detached "$1" "$2" "tools\\run_decode_match.py $3"
  elif [ "$UNCOLD_OK" = "1" ]; then
    detached "$1" "$2" "tools\\run_decode_match.py $3 --uncold-uptime-deviation"
  else
    log "SKIP $1: run_decode_match enforces the 7,200 s uptime gate; needs REBOOT_OK=1 or UNCOLD_OK=1 (decision for Zach)"
  fi
}

log "start (STEP_FROM=$STEP_FROM REBOOT_OK=$REBOOT_OK UNCOLD_OK=$UNCOLD_OK); output in $OUT"
case "$EXPECT_HEAD" in *PLACEHOLDER*) stop "EXPECT_HEAD not set in this script";; esac
ssh -o BatchMode=yes -o ConnectTimeout=15 "$X" hostname >/dev/null 2>&1 || stop "T2S not reachable over ssh"
B64=$(base64 < ~/seam_closeout_1013/t2s/tools/park_untracked_t2s.ps1 | tr -d '\n')
xs "New-Item -ItemType Directory -Force C:\\Users\\zach\\seam_tools | Out-Null; [IO.File]::WriteAllBytes('C:\\Users\\zach\\seam_tools\\park_untracked_t2s.ps1', [Convert]::FromBase64String('$B64')); (Get-FileHash C:\\Users\\zach\\seam_tools\\park_untracked_t2s.ps1).Hash" | tee "$OUT/park_tool_hash.txt"
grep -q -E '^[0-9A-F]{64}' "$OUT/park_tool_hash.txt" || stop "could not write park_untracked_t2s.ps1 on the T2S"

if after a; then
  # a. Read-only.
  xs 'hostname; [int]((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalSeconds' | tee "$OUT/a_host_uptime.txt"
  r=$(rithwik); [ -z "${r// }" ] || stop "Rithwik's process running: $r"
  b=$(banned); [ -z "${b// }" ] || stop "banned/foreign process running: $b"
  xs 'Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings" -ErrorAction SilentlyContinue | Select-Object PauseUpdatesStartTime,PauseUpdatesExpiryTime,PauseFeatureUpdatesEndTime,PauseQualityUpdatesEndTime | Format-List' | tee "$OUT/a_windows_update_pause.txt"
  WU=$(grep -m1 'PauseUpdatesExpiryTime' "$OUT/a_windows_update_pause.txt" | sed 's/^[^:]*: *//')
  if [ -z "$WU" ]; then log "WARN Windows Update NOT paused (no PauseUpdatesExpiryTime); Rithwik asked for a pause through Nov 8"; else log "Windows Update paused until $WU (needs >= 2026-11-08)"; fi
  xs 'Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass -eq "DISPLAY" -or $_.DeviceName -match "NPU" } | Select-Object DeviceName,DriverVersion,DriverDate,InfName,DeviceID | Format-List' | tee "$OUT/a_drivers.txt"
  grep -q 'DriverVersion' "$OUT/a_drivers.txt" && log "drivers recorded: $(drv_summary "$OUT/a_drivers.txt")" || log "WARN driver query returned nothing (see a_drivers.txt)"
  watchdog_ok a || stop "T2S watchdog launch-check refused (see watchdog_check_a.txt)"
  log "a read-only done"
fi
if after b; then
  # b. Pin restore (Task AM; the T2S checkout of DEMO2_HELDOUT_60 is the CRLF form 8B0844EF), pull, clean.
  xs "cd $R; git pull --ff-only; Remove-Item derived\\h1_hybrid\\demo2\\DEMO2_HELDOUT_60.json; git checkout -- derived/h1_hybrid/demo2/DEMO2_HELDOUT_60.json; (Get-FileHash -Algorithm SHA256 derived\\h1_hybrid\\demo2\\DEMO2_HELDOUT_60.json).Hash; git log -1 --format=%h; git status --short" | tee "$OUT/b_pull_pin.txt"
  grep -q "^$PIN_SHA" "$OUT/b_pull_pin.txt" || stop "DEMO2_HELDOUT_60 hash after restore is not $PIN_SHA"
  grep -q "^${EXPECT_HEAD:0:7}" "$OUT/b_pull_pin.txt" || stop "T2S head is not $EXPECT_HEAD after the pull"
  clean_tree; log "b pin restored, at $EXPECT_HEAD, tree clean"
fi
if after c; then
  # c. P0a readback; STOP unless PA, no SDPA fallback, compiled KV i8.
  detached p0a_readback 'derived\c2_ttft\_launches\demo2_p0\t2s_readback.log' 'tools\kv_compiled_readback.py --kv all --mode all'
  python3 - "$OUT/p0a_readback.log" > "$OUT/c_p0a_verdict.txt" <<'PYEOF'
import json, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
doc, dec, i = None, json.JSONDecoder(), 0
while (i := text.find("{", i)) >= 0:
    try:
        obj, end = dec.raw_decode(text, i)
    except ValueError:
        i += 1
        continue
    if isinstance(obj, dict) and "genai_default" in obj:
        doc = obj
    i = end
if doc is None:
    print("VERDICT NO_JSON"); sys.exit(0)
p = doc["genai_default"].get("parsed") or {}
ok = p.get("backend") == "PA" and p.get("sdpa_fallback_warning") is False and p.get("kv_cache_precision") == "i8"
print("backend", p.get("backend"), "sdpa_fallback", p.get("sdpa_fallback_warning"), "kv", p.get("kv_cache_precision"))
print("rt_info_override", (doc["genai_default"].get("ir_rt_info") or {}).get("override"))
print("VERDICT", "PASS" if ok else "FAIL")
PYEOF
  cat "$OUT/c_p0a_verdict.txt" | tee -a "$OUT/steps.txt"
  grep -q '^VERDICT PASS' "$OUT/c_p0a_verdict.txt" || stop "P0a on the T2S did not read PA / no SDPA fallback / compiled KV i8 (recorded in c_p0a_verdict.txt)"
fi
LONG='-Entries derived\h1_hybrid\demo1\DEMO1_LONGCTX_30.json'
BASE='-Entries derived\h1_hybrid\demo1\DEMO1_BASE_30.json'
COMMON='-Interleaved -InterleavedPolicies local_only -PolicyCapUsd local_only=0 -SessionMaxUsd 1 -Placement gpu_only -Residency RESIDENT'
ARM_A="$COMMON -Kv default -RequireTrueDefault"
U4="$COMMON -Kv u4 -CompiledReadback"
TELE='-DebugRawText -MemTelemetry -GpuMemCounters'
WD="-TurnWatchdogS $WATCHDOG_S"
M='--model-spec configs\models\Qwen3-4B-int4-ov.yaml'
# --- P9 + P2 only (cold, REBOOT_OK=1). Written 2026-10-20 ~7:55 PM ET to replace STEP_FROM=e,
# which would also have re-run steps f, g and h. Run with: REBOOT_OK=1 STEP_FROM=e caffeinate -i bash <this>
[ "$REBOOT_OK" = "1" ] || stop "this script needs REBOOT_OK=1"
n=$(xs '@(Get-Process python -ErrorAction SilentlyContinue).Count' | tr -dc '0-9')
if [ "${n:-0}" != "0" ]; then
  log "python already running on the T2S (P9 from the interrupted script?); waiting for it, then parking it as p9_t2s"
  wait_python
  ok=0; check_log "$R\\derived\\c2_ttft\\_launches\\demo2_p9\\t2s_drift.log" p9_t2s || ok=$?
  scp -q "$X:$(echo "$R\\derived\\c2_ttft\\_launches\\demo2_p9\\t2s_drift.log" | tr '\\' '/')" "$OUT/p9_t2s.log" 2>/dev/null
  park p9_t2s
  [ $ok -eq 0 ] && log "p9_t2s OK" || log "p9_t2s log shows a refusal or error (continuing to P2)"
else
  decode_pilot p9_t2s 'derived\c2_ttft\_launches\demo2_p9\t2s_drift.log' "--pilot p9 --arm gpu_only $M"
fi
decode_pilot p2_i8_t2s 'derived\c2_ttft\_launches\demo2_p2\t2s_i8.log' "--pilot p2 --arm gpu_only $M"
decode_pilot p2_u4_t2s 'derived\c2_ttft\_launches\demo2_p2\t2s_u4.log' "--pilot p2 --arm gpu_only_u4 $M"
decode_pilot p2_f16_t2s 'derived\c2_ttft\_launches\demo2_p2\t2s_f16.log' "--pilot p2 --arm gpu_only_f16 $M"
log "T2S P9/P2 done; hand-back check below (no python, tree clean); hand back by midnight ET Oct 25"
xs "cd $R; git status --short; @(Get-Process python -ErrorAction SilentlyContinue).Count" | tee "$OUT/handback.txt"
exit 0
