#!/usr/bin/env bash
# Shared APU characterization environment (source from driver scripts).
# Pin BLAS/OpenMP to 1 thread so NumPy matmul CPU stays on the calling thread
# (TOOL_COMPUTE) instead of fanning out to invisible OpenBLAS workers (THREADPOOL).
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
