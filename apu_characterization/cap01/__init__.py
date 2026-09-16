"""CAP-01 capability-scaling data plane."""

from .calibration import (
    CalibrationResult,
    calibrate_pool,
    classification_manifest,
    classify_probabilities,
    solved_probability,
)
from .generation import (
    DEFAULT_PROMPT_TEMPLATE,
    GenerationConfig,
    GenerationError,
    build_generation_prompt,
    generate_task_pool,
)
from .pool import (
    PoolError,
    PoolWriter,
    build_manifest,
    freeze_pool,
    load_frozen_pool,
    pool_manifest_sha256,
)
from .verifier import (
    ReexecutionResult,
    VerificationVerdict,
    VerifierLimits,
    normalize_exact,
    normalize_numeric,
    reexecute_verification,
    verify_candidate,
    verify_code,
    verify_math,
)

__all__ = [
    "CalibrationResult",
    "DEFAULT_PROMPT_TEMPLATE",
    "GenerationConfig",
    "GenerationError",
    "PoolError",
    "PoolWriter",
    "ReexecutionResult",
    "VerificationVerdict",
    "VerifierLimits",
    "build_generation_prompt",
    "build_manifest",
    "calibrate_pool",
    "classification_manifest",
    "classify_probabilities",
    "freeze_pool",
    "generate_task_pool",
    "load_frozen_pool",
    "normalize_exact",
    "normalize_numeric",
    "pool_manifest_sha256",
    "reexecute_verification",
    "solved_probability",
    "verify_candidate",
    "verify_code",
    "verify_math",
]
