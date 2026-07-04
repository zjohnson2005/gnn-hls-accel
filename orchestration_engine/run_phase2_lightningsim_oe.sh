#!/usr/bin/env bash
# LightningSim DSE on orchestration engine kernels (graph_load -> scatter DATAFLOW).
# Server-only: Vitis 2023.1 ARCHIVE + conda fifo-advisor.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "NOTE: compose graph_load+scatter DATAFLOW top, csynth with hls_env_lightningsim.sh,"
echo "then ls_probe + dse_sweep -> characterization/out/phase2/dse_report_oe.json"
echo "Pending composed kernel instrumentation (Phase C2)."
