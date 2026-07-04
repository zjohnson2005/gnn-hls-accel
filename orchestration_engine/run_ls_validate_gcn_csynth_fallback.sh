#!/usr/bin/env bash
# REMOVED: csynth-only was never valid for LightningSim proof.
echo "ERROR: run_ls_validate_gcn_csynth_fallback.sh is disabled." >&2
echo "C1 requires real cosim: bash orchestration_engine/run_ls_validate_gcn.sh" >&2
exit 1
