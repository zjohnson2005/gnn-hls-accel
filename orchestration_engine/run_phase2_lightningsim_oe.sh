#!/usr/bin/env bash
# LightningSim FIFO DSE on OE engine (graph_load then scatter; axis FIFO trace).
# No synthetic fallbacks — trace capture failure is a hard error.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

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
  echo "ERROR: fifo-advisor not importable." >&2
  return 1
}

OE_PYTHON="$(_oe_resolve_python)" || exit 1
source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"
export PATH="$(dirname "$OE_PYTHON"):$PATH"

echo "Using python: $OE_PYTHON"

PROJ="oe_engine_ls_proj"
STAMP_TAG="OE_ENGINE_LS=oe-ls-lite-u64-v9-ready-drain-df"
SOLUTION_DIR="$ROOT/$PROJ/sol1"
CSYNTH_RPT="$SOLUTION_DIR/syn/report/oe_hls_engine_stream_csynth.rpt"
LS_STAMP="$SOLUTION_DIR/.oe_lightningsim_vitis"

if [[ -f "$CSYNTH_RPT" ]] && [[ -f "$LS_STAMP" ]] && grep -q "$STAMP_TAG" "$LS_STAMP"; then
  echo "Reusing $SOLUTION_DIR ($(cat "$LS_STAMP"))"
else
  echo "=== Building oe_hls_engine_stream for LightningSim ($STAMP_TAG) ==="
  rm -rf "$PROJ"
  vitis_hls -f orchestration_engine/run_hls_oe_engine_ls.tcl
  echo "$(command -v vitis_hls) $STAMP_TAG" > "$LS_STAMP"
fi

if [[ -d "$ROOT/$PROJ/sol1" ]] && [[ ! -e "$ROOT/$PROJ/solution1" ]]; then
  ln -sfn sol1 "$ROOT/$PROJ/solution1"
fi

"$OE_PYTHON" -m orchestration_engine.eval.patch_lightningsim "$SOLUTION_DIR"

if [[ ! -f "$SOLUTION_DIR/trace.pkl" ]]; then
  echo "=== Refresh csim + capture trace.pkl (required for real LS DSE) ==="
  vitis_hls -f orchestration_engine/run_hls_oe_engine_ls_csim_refresh.tcl
  if ! "$OE_PYTHON" -m orchestration_engine.eval.capture_ls_trace --solution-dir "$SOLUTION_DIR"; then
    echo ""
    echo "ERROR: OE engine trace capture failed. C2 cannot pass without trace.pkl." >&2
    echo "Fix DATAFLOW top / patch_lightningsim / csim on $SOLUTION_DIR" >&2
    echo "Do NOT use --synthetic or offline DSE for thesis artifacts." >&2
    exit 1
  fi
fi

echo "=== LightningSim FIFO DSE on $SOLUTION_DIR ==="
"$OE_PYTHON" -m orchestration_engine.eval.dse_sweep \
  --solution-dir "$SOLUTION_DIR" \
  --n-samples 500 \
  --batch-size 64 \
  --output "$OUT/dse_report_oe.json"

"$OE_PYTHON" -m orchestration_engine.eval.ls_capture_oe_eval

echo "=== C2 Vitis side: oe_hls_engine_stream cosim (2023.1, same source stamp) ==="
if [[ -f "$OUT/cosim_oe_engine_ls.json" ]]; then
  if ! "$OE_PYTHON" -c "
import json
from pathlib import Path
p = Path('$OUT/cosim_oe_engine_ls.json')
d = json.loads(p.read_text())
rp = (d.get('report_path') or '').replace('\\\\', '/')
raise SystemExit(0 if 'oe_engine_ls_proj/' in rp else 1)
"; then
    echo "Removing cosim_oe_engine_ls.json from old split-project pairing"
    rm -f "$OUT/cosim_oe_engine_ls.json"
  fi
fi
# Reuse only a valid real-cosim cache (never csynth-only or a stale/failed run).
if [[ -f "$OUT/cosim_oe_engine_ls.json" ]] && ! "$OE_PYTHON" -c "
from pathlib import Path
import json
from orchestration_engine.phase2_gate.ls_gate import gcn_ls_cosim_json_valid
p = Path('$OUT/cosim_oe_engine_ls.json')
ok, _ = gcn_ls_cosim_json_valid(json.loads(p.read_text(encoding='utf-8')))
raise SystemExit(0 if ok else 1)
"; then
  echo "Removing invalid cosim_oe_engine_ls.json (not real cosim)"
  rm -f "$OUT/cosim_oe_engine_ls.json"
fi
if [[ ! -f "$OUT/cosim_oe_engine_ls.json" ]]; then
  if ! vitis_hls -f orchestration_engine/run_hls_oe_engine_ls_cosim_trace.tcl; then
    echo ""
    echo "ERROR: OE engine cosim failed. C2 needs real cosim cycles for the pairing." >&2
    echo "Do NOT substitute csynth estimates or the scatter-only anchor." >&2
    exit 1
  fi
  RPT="$(find oe_engine_ls_proj -path '*/sim/report/*_cosim.rpt' | head -1)"
  if [[ -z "$RPT" ]]; then
    echo "ERROR: engine cosim finished but no *_cosim.rpt found" >&2
    exit 1
  fi
  "$OE_PYTHON" -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$RPT" \
    --out "$OUT/cosim_oe_engine_ls.json"
else
  echo "Reusing $OUT/cosim_oe_engine_ls.json"
fi

"$OE_PYTHON" -m orchestration_engine.eval.ls_validate --mode ls_lite
"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report --refresh

echo "Done. See $OUT/dse_report_oe.json and $OUT/ls_validation.json"
