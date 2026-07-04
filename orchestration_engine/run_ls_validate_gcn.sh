#!/usr/bin/env bash
# C1 (thesis pillar): Vitis cosim vs LightningSim on the SAME gcn_stream_proj/sol1.
# Cosim runs on the traced solution (not a separate project) so RTL matches trace.pkl.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

STAMP_TAG="GNN_LS_LITE=df-u16-apmem-v2"
TRACE_SOL="$ROOT/gcn_stream_proj/sol1"
LS_STAMP="$TRACE_SOL/.oe_lightningsim_vitis"

if [[ -z "${CONDA_PREFIX:-}" ]] && [[ -d "$HOME/miniconda3/envs/fifo-advisor" ]]; then
  export CONDA_PREFIX="$HOME/miniconda3/envs/fifo-advisor"
fi

_oe_resolve_python() {
  local cand
  for cand in \
    "${OE_PYTHON:-}" \
    "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" \
    "$HOME/miniconda3/envs/fifo-advisor/bin/python" \
    "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$cand" ]] || continue
    [[ -x "$cand" ]] || continue
    if "$cand" -c "import fifo_advisor" 2>/dev/null; then
      echo "$cand"
      return 0
    fi
  done
  echo "ERROR: fifo-advisor required for C1 / LightningSim validation." >&2
  return 1
}

OE_PYTHON="$(_oe_resolve_python)" || exit 1
export PATH="$(dirname "$OE_PYTHON"):$PATH"

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"

if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  export PATH="$CONDA_PREFIX/bin:$PATH"
  OE_PYTHON="$CONDA_PREFIX/bin/python"
fi

if [[ ! -f "$TRACE_SOL/trace.pkl" ]]; then
  echo "ERROR: missing $TRACE_SOL/trace.pkl — run run_phase2_lightningsim.sh first." >&2
  exit 1
fi

if [[ ! -f "$LS_STAMP" ]] || ! grep -q "$STAMP_TAG" "$LS_STAMP"; then
  echo "ERROR: $TRACE_SOL stamp missing or not $STAMP_TAG." >&2
  echo "Rebuild trace+DSE so cosim pairs the same RTL:" >&2
  echo "  rm -rf gcn_stream_proj && bash orchestration_engine/run_phase2_lightningsim.sh" >&2
  exit 1
fi

# C1 needs a valid FULL DSE report (trace-backed, >=100 evals, real pareto_frontier).
if ! "$OE_PYTHON" -c "
import sys
from pathlib import Path
from orchestration_engine.phase2_gate.ls_gate import dse_report_valid
ok, detail = dse_report_valid(Path('$OUT/dse_report.json'))
print(detail)
sys.exit(0 if ok else 1)
"; then
  echo "ERROR: dse_report.json is not a valid full LightningSim DSE artifact." >&2
  echo "Run: bash orchestration_engine/run_phase2_lightningsim.sh (full DSE, no summaries)." >&2
  exit 1
fi

echo "=== C1: GNN_LS_LITE cosim on traced solution ($TRACE_SOL) ==="
echo "Using python: $OE_PYTHON"

# Drop stale Vitis side if csynth-only or missing cosim.rpt.
if [[ -f "$OUT/cosim_gcn_stream_ls.json" ]]; then
  if ! "$OE_PYTHON" -c "
from pathlib import Path
import json
from orchestration_engine.phase2_gate.ls_gate import gcn_ls_cosim_json_valid
p = Path('$OUT/cosim_gcn_stream_ls.json')
ok, _ = gcn_ls_cosim_json_valid(json.loads(p.read_text(encoding='utf-8')))
raise SystemExit(0 if ok else 1)
"; then
    echo "Removing stale invalid cosim_gcn_stream_ls.json"
    rm -f "$OUT/cosim_gcn_stream_ls.json" "$OUT/ls_gcn_eval.json"
  fi
fi

# Reject cosim from the old split-project flow (different RTL than trace).
if [[ -f "$OUT/cosim_gcn_stream_ls.json" ]]; then
  if ! "$OE_PYTHON" -c "
import json
from pathlib import Path
p = Path('$OUT/cosim_gcn_stream_ls.json')
d = json.loads(p.read_text())
rp = (d.get('report_path') or '').replace('\\\\', '/')
raise SystemExit(0 if 'gcn_stream_proj/' in rp else 1)
"; then
    echo "Removing cosim_gcn_stream_ls.json from old gcn_stream_ls_cosim_proj pairing"
    rm -f "$OUT/cosim_gcn_stream_ls.json" "$OUT/ls_gcn_eval.json"
  fi
fi

if ! vitis_hls -f run_hls_stream_ls_cosim_trace.tcl; then
  echo ""
  echo "ERROR: cosim on gcn_stream_proj failed. C1 cannot pass without real cosim cycles." >&2
  exit 1
fi

RPT="$(find gcn_stream_proj -path '*/sim/report/*_cosim.rpt' | head -1)"
if [[ -z "$RPT" ]]; then
  echo "ERROR: cosim finished but no *_cosim.rpt under gcn_stream_proj" >&2
  exit 1
fi

"$OE_PYTHON" -m orchestration_engine.phase2_gate.cosim_parser \
  --report "$RPT" \
  --out "$OUT/cosim_gcn_stream_ls.json"

echo "=== C1: fresh LightningSim eval on $TRACE_SOL ==="
"$OE_PYTHON" -m orchestration_engine.eval.ls_capture_gcn_eval

"$OE_PYTHON" -m orchestration_engine.eval.ls_validate --mode ls_lite
"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report --refresh

echo "Done. See $OUT/ls_validation.json"
