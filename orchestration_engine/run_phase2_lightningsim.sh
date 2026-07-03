#!/usr/bin/env bash
# LightningSim FIFO DSE on the streaming GCN kernel (DATAFLOW + hls::stream FIFOs).
# Run from repo root on the Vitis box, inside the fifo-advisor conda env.
#
# One-time setup (from a home dir with conda/mamba):
#   git clone https://github.com/sharc-lab/fifo-advisor.git
#   cd fifo-advisor && conda env create -f environment.yml
#   conda activate fifo-advisor
#   pip install --no-deps git+https://github.com/sharc-lab/fifo-advisor.git
#
# Then each session:
#   source /tools/software/xilinx/setup_env.sh
#   conda activate fifo-advisor
#   cd ~/gnn-hls-accel && bash orchestration_engine/run_phase2_lightningsim.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source "$ROOT/orchestration_engine/hls_env.sh"

if ! python -c "import fifo_advisor" 2>/dev/null; then
  echo "ERROR: fifo-advisor not importable."
  echo "Activate the conda env first:"
  echo "  conda activate fifo-advisor"
  echo "See fifo_pareto/README.md for install steps."
  exit 1
fi

SOLUTION_DIR="$ROOT/gcn_stream_proj/sol1"
CSYNTH_RPT="$SOLUTION_DIR/syn/report/gcn_layer_stream_csynth.rpt"

if [[ ! -f "$CSYNTH_RPT" ]]; then
  echo "=== Building streaming GCN kernel (DATAFLOW target for LightningSim) ==="
  rm -rf gcn_stream_proj
  vitis_hls -f run_hls_stream.tcl
fi

if [[ ! -d "$SOLUTION_DIR" ]]; then
  echo "ERROR: expected $SOLUTION_DIR after csynth"
  exit 1
fi

mkdir -p orchestration_engine/characterization/out/phase2

echo "=== LightningSim FIFO DSE (500 samples; first run builds trace.pkl) ==="
python -m orchestration_engine.eval.dse_sweep \
  --solution-dir "$SOLUTION_DIR" \
  --n-samples 500 \
  --batch-size 64 \
  --output orchestration_engine/characterization/out/phase2/dse_report.json

echo ""
python -m orchestration_engine.phase2_gate.gate_report
echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
