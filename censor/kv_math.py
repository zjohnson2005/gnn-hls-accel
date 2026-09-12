"""KV-cache arithmetic core. Serves BOTH tiers.

One implementation sets datacenter batch size (Arm A) and answers local KV
feasibility (Arm C1). Building it twice is how the two sides drift apart.

CRITICAL: KV size depends on ``n_kv_heads``, NOT ``n_heads``. For Llama-3.1-8B
that distinction is a 4x error; for a 70B GQA model it is 8x.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

KvDtype = Literal["fp16", "q8_0"]
Quant = Literal["fp16", "q8_0", "q4_k_m"]

BYTES_PER_ELEMENT: dict[str, float] = {"fp16": 2.0, "q8_0": 1.0}

# Bits per weight parameter by quantization scheme.
BITS_PER_WEIGHT: dict[str, float] = {
    "fp16": 16.0,
    "q8_0": 8.5,   # q8_0 carries an fp16 scale per 32-element block
    "q4_k_m": 4.85,
}
BITS_PER_WEIGHT_SOURCE = (
    "fp16=16 exact; q8_0=8.5 and q4_k_m=4.85 effective bits/weight from the "
    "llama.cpp quantization table (k-quants carry per-block scales/mins, so "
    "effective bpw exceeds the nominal bit count). confidence: published"
)


@dataclass(frozen=True)
class ModelSpec:
    """Architecture fields that determine KV size. All from model card/config.json."""

    name: str
    n_layers: int
    n_heads: int
    n_kv_heads: int
    head_dim: int
    d_model: int
    params_total: float
    params_active: float  # differs from total only for MoE
    attention: str        # MHA | GQA
    source: str
    confidence: str = "published"

    @property
    def gqa_group_size(self) -> float:
        return self.n_heads / self.n_kv_heads

    @property
    def is_moe(self) -> bool:
        return self.params_active < self.params_total


# ---------------------------------------------------------------------------
# Model table: 5 models spanning size, attention scheme, and dense/MoE.
# ---------------------------------------------------------------------------
MODEL_SPECS: dict[str, ModelSpec] = {
    "llama31_8b": ModelSpec(
        name="Llama-3.1-8B",
        n_layers=32, n_heads=32, n_kv_heads=8, head_dim=128, d_model=4096,
        params_total=8.03e9, params_active=8.03e9, attention="GQA",
        source=(
            "HF config.json (meta-llama/Meta-Llama-3.1-8B): num_hidden_layers=32, "
            "num_attention_heads=32, num_key_value_heads=8, head_dim=128, "
            "hidden_size=4096. Cross-checked against Llama 3 Herd of Models "
            "(arXiv:2407.21783) Table 3."
        ),
    ),
    "llama31_70b": ModelSpec(
        name="Llama-3.1-70B",
        n_layers=80, n_heads=64, n_kv_heads=8, head_dim=128, d_model=8192,
        params_total=70.6e9, params_active=70.6e9, attention="GQA",
        source=(
            "Llama 3 Herd of Models (arXiv:2407.21783) Table 3: Layers=80, "
            "Model Dimension=8192, Attention Heads=64, Key/Value Heads=8. "
            "head_dim = 8192/64 = 128."
        ),
    ),
    "llama2_7b_mha": ModelSpec(
        name="Llama-2-7B (MHA contrast)",
        n_layers=32, n_heads=32, n_kv_heads=32, head_dim=128, d_model=4096,
        params_total=6.74e9, params_active=6.74e9, attention="MHA",
        source=(
            "Llama 2 7B uses full MHA (n_kv_heads == n_heads == 32); 32 layers, "
            "hidden 4096. Param count 6.74B as reported by llama.cpp llama-bench "
            "output. Included as the MHA contrast case: 4x the KV of Llama-3.1-8B "
            "at nearly the same parameter count."
        ),
    ),
    "qwen25_32b": ModelSpec(
        name="Qwen2.5-32B",
        n_layers=64, n_heads=40, n_kv_heads=8, head_dim=128, d_model=5120,
        params_total=32.8e9, params_active=32.8e9, attention="GQA",
        source=(
            "Qwen2.5-32B HF config: num_hidden_layers=64, num_attention_heads=40, "
            "num_key_value_heads=8, hidden_size=5120, head_dim=128. The 40Q/8KV "
            "ratio matches the Qwen 32B-class convention tabulated in the "
            "MHA/MQA/GQA reference table (waylandz ch.23)."
        ),
        confidence="published",
    ),
    "qwen3_30b_a3b_moe": ModelSpec(
        name="Qwen3-30B-A3B (MoE)",
        n_layers=48, n_heads=32, n_kv_heads=4, head_dim=128, d_model=2048,
        params_total=30.5e9, params_active=3.3e9, attention="GQA",
        source=(
            "Qwen3-30B-A3B HF config: num_hidden_layers=48, "
            "num_attention_heads=32, num_key_value_heads=4, explicit head_dim=128 "
            "(hidden_size=2048, so head_dim must be read explicitly, not derived "
            "-- see LLMServingSim model-config note on the Qwen3 head_dim trap). "
            "30.5B total / ~3.3B active."
        ),
    ),
}


def kv_bytes_per_token(spec: ModelSpec, dtype: KvDtype = "fp16") -> float:
    """Bytes of KV cache per token. Factor 2 is K and V."""
    return 2.0 * spec.n_layers * spec.n_kv_heads * spec.head_dim * BYTES_PER_ELEMENT[dtype]


def kv_footprint(spec: ModelSpec, context_len: float, dtype: KvDtype = "fp16") -> float:
    """Bytes of KV cache for one sequence at ``context_len`` tokens."""
    return kv_bytes_per_token(spec, dtype) * float(context_len)


def weights_footprint(spec: ModelSpec, quant: Quant = "fp16") -> float:
    """Bytes of model weights. MoE holds ALL experts resident, so uses total."""
    return spec.params_total * BITS_PER_WEIGHT[quant] / 8.0


def attention_quadratic_coefficient(spec: ModelSpec) -> float:
    """c such that (attention FLOPs / weight FLOPs) = c * context_len.

    Prefill FLOPs ~ 2*P*L (weights) + 4*n_layers*d_model*L^2 (QK^T and AV).
    Ratio = (4*n_layers*d_model*L) / (2*P) = c*L with c = 2*n_layers*d_model/P.

    Used by prefill_bounds to build an architecture-derived degradation model
    rather than a guessed one.
    """
    return 2.0 * spec.n_layers * spec.d_model / spec.params_active


# ---------------------------------------------------------------------------
# C1: local feasibility
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LocalHw:
    name: str
    memory_bytes: float
    usable_fraction: float
    source: str
    confidence: str


LOCAL_HW: dict[str, LocalHw] = {
    "strix_halo": LocalHw(
        name="Strix Halo (Ryzen AI Max+ 395, 128GB unified)",
        memory_bytes=128e9,
        usable_fraction=0.75,
        source=(
            "128GB LPDDR5X unified. computingforgeeks Ryzen AI Max+ 395 comparison: "
            "'~96GB GPU-addressable on Linux' out of 128GB => usable_fraction 0.75. "
            "theaibench Framework Desktop page corroborates 'up to 96 GB assignable "
            "as VRAM to the 8060S iGPU'."
        ),
        confidence="published",
    ),
    "apple_m_series": LocalHw(
        name="Apple M4 Max 128GB unified",
        memory_bytes=128e9,
        usable_fraction=0.75,
        source=(
            "128GB unified-memory M4 Max config (mljourney 'M4 Max 128GB' bench "
            "column). macOS default caps GPU wired memory near 75% of unified RAM "
            "(iogpu.wired_limit_mb default); usable_fraction 0.75 reflects that "
            "default rather than a raised limit."
        ),
        confidence="estimated",
    ),
    "discrete_gpu_rtx5090": LocalHw(
        name="RTX 5090 32GB GDDR7",
        memory_bytes=32e9,
        usable_fraction=0.92,
        source=(
            "32GB published spec (see study_params local_hardware.discrete_gpu."
            "rtx_5090.memory_gb). usable_fraction 0.92 leaves headroom for CUDA "
            "context, activations, and fragmentation; not a measured figure."
        ),
        confidence="estimated",
    ),
    "discrete_gpu_rtx4090": LocalHw(
        name="RTX 4090 24GB GDDR6X",
        memory_bytes=24e9,
        usable_fraction=0.92,
        source=(
            "24GB published spec (see study_params local_hardware.discrete_gpu."
            "rtx_4090.memory_gb). usable_fraction 0.92 as above; not measured."
        ),
        confidence="estimated",
    ),
}


@dataclass(frozen=True)
class FeasibilityRow:
    hw: str
    model: str
    quant: str
    kv_dtype: str
    usable_bytes: float
    weights_bytes: float
    free_for_kv_bytes: float
    kv_bytes_per_token: float
    max_context_tokens: float
    context_floor: float
    feasible_at_context_floor: bool
    headroom_ratio: float


def local_feasibility(
    context_floor: float,
    *,
    models: list[str] | None = None,
    quants: tuple[Quant, ...] = ("q4_k_m", "q8_0", "fp16"),
    kv_dtypes: tuple[KvDtype, ...] = ("fp16", "q8_0"),
) -> list[FeasibilityRow]:
    """Can each local config hold weights + a context_floor-sized KV cache?"""
    rows: list[FeasibilityRow] = []
    model_keys = models or list(MODEL_SPECS)
    for hw_key, hw in LOCAL_HW.items():
        usable = hw.memory_bytes * hw.usable_fraction
        for mk in model_keys:
            spec = MODEL_SPECS[mk]
            for quant in quants:
                w = weights_footprint(spec, quant)
                for kvd in kv_dtypes:
                    kvpt = kv_bytes_per_token(spec, kvd)
                    free = usable - w
                    max_ctx = free / kvpt if free > 0 else 0.0
                    rows.append(
                        FeasibilityRow(
                            hw=hw_key,
                            model=mk,
                            quant=quant,
                            kv_dtype=kvd,
                            usable_bytes=usable,
                            weights_bytes=w,
                            free_for_kv_bytes=free,
                            kv_bytes_per_token=kvpt,
                            max_context_tokens=max_ctx,
                            context_floor=context_floor,
                            feasible_at_context_floor=max_ctx >= context_floor,
                            headroom_ratio=max_ctx / context_floor if context_floor else float("nan"),
                        )
                    )
    return rows
