#!/usr/bin/env bash
# Bare-metal host provisioning for MCP-01 (preflight only; does not run the matrix).
set -euo pipefail

echo "MCP-01 bare-metal provisioning (no matrix launch)"

if [[ ! -d /sys/devices/system/cpu ]]; then
  echo "REFUSE: /sys CPU topology unavailable (not Linux?)" >&2
  exit 1
fi

GOVERNOR_OK=0
if compgen -G "/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor" > /dev/null; then
  echo "Setting CPU frequency governor to performance (requires sudo)..."
  if sudo -n bash -c 'echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null' 2>/dev/null; then
    GOVERNOR_OK=1
    echo "governor=performance (applied)"
  elif sudo bash -c 'echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null'; then
    GOVERNOR_OK=1
    echo "governor=performance (applied)"
  else
    echo "CAVEAT: could not set governor to performance (sudo failed or cpufreq missing)." >&2
    echo "  Publication runs should use performance; fix manually or re-run with sudo." >&2
  fi
else
  echo "CAVEAT: no cpufreq scaling_governor nodes; skipping governor change." >&2
fi

echo ""
echo "Turbo / boost state (best-effort):"
if [[ -r /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
  echo "  intel_pstate/no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo)"
fi
if [[ -r /sys/devices/system/cpu/cpufreq/boost ]]; then
  echo "  cpufreq/boost=$(cat /sys/devices/system/cpu/cpufreq/boost)"
fi
if [[ -r /sys/devices/system/cpu/intel_pstate/status ]]; then
  echo "  intel_pstate/status=$(cat /sys/devices/system/cpu/intel_pstate/status)"
fi

echo ""
echo "SMT sibling pairs (logical CPU -> siblings):"
mapfile -t CPU_NODES < <(ls -d /sys/devices/system/cpu/cpu[0-9]* 2>/dev/null | sort -V)
declare -A SEEN=()
for node in "${CPU_NODES[@]}"; do
  cpu="${node##*/cpu}"
  if [[ -n "${SEEN[$cpu]:-}" ]]; then
    continue
  fi
  if [[ -r "${node}/topology/thread_siblings_list" ]]; then
    siblings="$(tr -d '\n' < "${node}/topology/thread_siblings_list")"
    echo "  cpu${cpu}: siblings=${siblings}"
    IFS=',' read -ra PARTS <<< "$siblings"
    for part in "${PARTS[@]}"; do
      if [[ "$part" == *-* ]]; then
        start="${part%-*}"
        end="${part#*-}"
        for ((s=start; s<=end; s++)); do
          SEEN["$s"]=1
        done
      else
        SEEN["$part"]=1
      fi
    done
  fi
done

echo ""
echo "Core partition guidance for run_mcp_bare_metal.sh:"
echo "  - Pick disjoint CPU sets: OS, client, server (no overlap)."
echo "  - Never place client and server on SMT siblings of the same physical core."
echo "  - Reserve low-numbered CPUs for the OS (interrupts, ssh, logging)."
echo ""
echo "Example (adjust to your topology):"
echo "  export MCP_OS_CORES=0,1"
echo "  export MCP_CLIENT_CORES=2,3"
echo "  export MCP_SERVER_CORES=4,5"
echo ""
echo "Verify with: python apu_characterization/tools/check_mcp_bundle.py --source-only"
if [[ "$GOVERNOR_OK" -eq 0 ]]; then
  echo ""
  echo "NOTE: governor was not confirmed performance; fix before publication matrix." >&2
fi
