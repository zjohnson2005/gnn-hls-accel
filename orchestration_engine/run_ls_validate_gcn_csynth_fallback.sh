#!/usr/bin/env bash
# C1 fallback: csynth-only when GNN_LS_LITE cosim segfaults on pointer ports.
# Writes cosim_gcn_stream_ls.json from csynth latency (not trusted like cosim).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
PROJ="gcn_stream_ls_cosim_proj"

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"

echo "=== C1 fallback: GNN_LS_LITE csynth-only (no cosim) ==="
vitis_hls -f run_hls_stream_ls.tcl

RPT="$(find "$PROJ" -name 'gcn_layer_stream_csynth.rpt' | head -1)"
if [[ -z "$RPT" ]]; then
  echo "ERROR: no csynth report under $PROJ" >&2
  exit 1
fi

python3 - <<PY
import json
import re
from pathlib import Path

rpt = Path("$RPT")
text = rpt.read_text(encoding="utf-8", errors="replace")
lat_min = lat_max = None
m = re.search(r"\\|\\s*Latency \\(cycles\\)\\s*\\|\\s*(\\d+)\\s*\\|\\s*(\\d+)", text)
if m:
    lat_min, lat_max = int(m.group(1)), int(m.group(2))
else:
    m2 = re.search(r"\\+ Latency:\\s*(\\d+)", text)
    if m2:
        lat_min = lat_max = int(m2.group(1))

payload = {
    "top": "gcn_layer_stream",
    "rtl": "Verilog",
    "status": "csynth_only",
    "passed": lat_max is not None,
    "latency_min": lat_min,
    "latency_max": lat_max,
    "latency_cycles": lat_max,
    "note": "C1 cosim failed (LS lite pointer ports); csynth max used as weak Vitis anchor",
    "report_path": str(rpt),
}
out = Path("$OUT") / "cosim_gcn_stream_ls.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Wrote", out, "latency_cycles=", lat_max)
PY
