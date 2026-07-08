"""Pin BLAS/OpenMP threads for reproducible TOOL vs THREADPOOL attribution.

OpenBLAS reads OPENBLAS_NUM_THREADS when the library loads (first numpy import).
Import this module before any code path that imports numpy.

Shell drivers also export these vars via ``apu_env.sh`` so subprocesses inherit
the pin even if Python import order differs.
"""

from __future__ import annotations

import os

BLAS_PIN_VARS = ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")
_PIN_VALUE = "1"


def pin_blas_threads(*, value: str = _PIN_VALUE) -> dict[str, str]:
    """Set BLAS/OpenMP thread env vars when unset. Returns effective values."""
    out: dict[str, str] = {}
    for var in BLAS_PIN_VARS:
        os.environ.setdefault(var, value)
        out[var] = os.environ[var]
    return out


def blas_pin_snapshot() -> dict[str, str]:
    """Current BLAS pin env (for setup capture / run artifacts)."""
    return {var: os.environ.get(var, "unset") for var in BLAS_PIN_VARS}


pin_blas_threads()
