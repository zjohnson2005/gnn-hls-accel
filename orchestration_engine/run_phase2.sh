#!/usr/bin/env bash
# Phase 2 pipeline — run on the Vitis box from repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source /tools/software/xilinx/setup_env.sh

echo "=== Phase 2: scatter csynth ==="
rm -rf oe_scatter_proj
vitis_hls -f orchestration_engine/run_hls_scatter.tcl

SCATTER_RPT="$(find oe_scatter_proj -name 'oe_hls_scatter_kernel_csynth.rpt' | head -1)"
if [[ -z "$SCATTER_RPT" ]]; then
  SCATTER_RPT="$(find oe_scatter_proj -name '*_csynth.rpt' | head -1)"
fi
echo "csynth report: $SCATTER_RPT"

python3 -m orchestration_engine.phase2_gate.csynth_parser --report "$SCATTER_RPT"

COSIM_RPT="$(find oe_scatter_proj -name 'oe_hls_scatter_kernel_cosim.rpt' | head -1)"
if [[ -n "$COSIM_RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser --report "$COSIM_RPT" --fan-out 2
fi

echo ""
echo "=== Phase 2: full engine csynth ==="
rm -rf oe_proj
vitis_hls -f orchestration_engine/run_hls.tcl

echo ""
echo "=== Phase 2: native oe_bench ==="
cd "$ROOT/orchestration_engine"
mkdir -p build
g++ -std=c++17 -I include -I software -o build/oe_bench \
  software/engine_sim.cpp software/cpu_baseline.cpp software/workload_gen.cpp \
  software/main_bench.cpp
./build/oe_bench 4 2 42
./build/oe_bench 100 2 42

echo ""
echo "=== Phase 2: LightningSim DSE (if fifo-advisor installed) ==="
cd "$ROOT"
if python3 -c "import fifo_advisor" 2>/dev/null; then
  python3 -m orchestration_engine.eval.dse_sweep \
    --solution-dir oe_proj/sol1 \
    --n-samples 500 \
    --output orchestration_engine/characterization/out/phase2/dse_report.json
else
  echo "fifo-advisor not installed — skip DSE (see fifo_pareto/README.md)"
fi

python3 -m orchestration_engine.phase2_gate.gate_report
echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
