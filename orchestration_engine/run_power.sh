#!/usr/bin/env bash
# Post-implementation power reports (server-only). Exports HLS RTL and runs Vivado
# power analysis. Placeholder flow until impl scripts land on ece-rschsrv.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

TARGET="${1:-all}"
PART="xczu3eg-sbva484-1-e"
CLK_MHZ=404.4

write_placeholder() {
  local name="$1"
  local top="$2"
  local cycles_key="$3"
  local cycles=0
  if [[ -f "$OUT/$cycles_key" ]]; then
    cycles="$(python3 - <<PY
import json
d=json.load(open("$OUT/$cycles_key"))
print(d.get("per_transaction_cycles") or d.get("latency_cycles") or 0)
PY
)"
  fi
  python3 - <<PY
import json
out={
  "top": "$top",
  "part": "$PART",
  "clock_mhz": $CLK_MHZ,
  "static_w": None,
  "dynamic_w": None,
  "total_w": None,
  "status": "pending_impl",
  "note": "Run Vivado power on exported RTL; replace placeholder via run_power.sh",
  "cycles_reference": float("$cycles") or None,
}
json.dump(out, open("$OUT/power_${name}.json","w"), indent=2)
print("Wrote $OUT/power_${name}.json (placeholder)")
PY
}

source "$ROOT/orchestration_engine/hls_env.sh"

case "$TARGET" in
  scatter)
    write_placeholder scatter oe_hls_scatter_stream cosim_stream.json
    ;;
  graph_load)
    write_placeholder graph_load oe_hls_graph_load cosim_graph_load.json
    ;;
  all)
    write_placeholder scatter oe_hls_scatter_stream cosim_stream.json
    write_placeholder graph_load oe_hls_graph_load cosim_graph_load.json
    python3 -m orchestration_engine.characterization.energy_calc --write-doc
    ;;
  *)
    echo "Usage: $0 [scatter|graph_load|all]"
    exit 1
    ;;
esac
