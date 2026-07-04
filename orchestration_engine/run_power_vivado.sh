#!/usr/bin/env bash
# B2 full: export HLS RTL and run Vivado power (post-implementation).
# Server-only. Requires closed timing on exported netlist + SAIF/VCD activity.
#
# Status today: scaffold only — run_power.sh placeholders remain until impl
# scripts land. This script documents the intended flow and fails clearly.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

TARGET="${1:-all}"
source "$ROOT/orchestration_engine/hls_env.sh"

_export_one() {
  local name="$1"
  local proj="$2"
  local top="$3"
  local sol="$ROOT/$proj/sol1"

  if [[ ! -d "$sol/syn/verilog" ]]; then
    echo "ERROR: missing synthesized RTL at $sol/syn/verilog"
    echo "Run csynth first (e.g. run_phase2_scatter_stream.sh for scatter)."
    return 1
  fi

  echo "=== Export $top from $proj (manual Vivado power step follows) ==="
  echo "  RTL dir: $sol/syn/verilog"
  echo "  Next: create Vivado project, import RTL, run impl, report_power"
  echo "  Then patch $OUT/power_${name}.json with static_w/dynamic_w from report."

  python3 - <<PY
import json
from pathlib import Path
out = Path("$OUT") / "power_${name}.json"
payload = {
    "top": "$top",
    "project": "$proj",
    "rtl_dir": "$sol/syn/verilog",
    "status": "rtl_exported_pending_impl",
    "note": "RTL exported from HLS csynth; Vivado impl + report_power not automated yet",
}
if out.exists():
    prev = json.loads(out.read_text(encoding="utf-8"))
    payload["cycles_reference"] = prev.get("cycles_reference")
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Updated", out)
PY
}

case "$TARGET" in
  scatter)
    _export_one scatter oe_stream_proj oe_hls_scatter_stream
    ;;
  graph_load)
    _export_one graph_load oe_graph_load_proj oe_hls_graph_load
    ;;
  all)
    _export_one scatter oe_stream_proj oe_hls_scatter_stream
    _export_one graph_load oe_graph_load_proj oe_hls_graph_load
    ;;
  *)
    echo "Usage: $0 [scatter|graph_load|all]"
    exit 1
    ;;
esac

echo ""
echo "Vivado power automation is deferred. Placeholder JSONs updated with RTL paths."
