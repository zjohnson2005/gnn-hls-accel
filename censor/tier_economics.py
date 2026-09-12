"""Arm A: cost structure underneath metered-tier rate cards.

SCOPE LINE (do not cross): this module reasons about capacity arithmetic and
what it implies about cost structure. It makes NO claim about any provider's
actual internal serving configuration. "The cost structure implies batch
collapse near X tokens" is in scope. "Provider Y runs batch size 4" is not, and
would make the whole arm unfalsifiable.
"""

from __future__ import annotations

from dataclasses import dataclass

from censor.kv_math import (
    KvDtype,
    ModelSpec,
    Quant,
    kv_bytes_per_token,
    kv_footprint,
    weights_footprint,
)


@dataclass(frozen=True)
class Accelerator:
    name: str
    memory_bytes: float
    source: str
    confidence: str = "published"


ACCELERATORS: dict[str, Accelerator] = {
    "a100_80gb": Accelerator(
        name="NVIDIA A100 80GB",
        memory_bytes=80e9,
        source="NVIDIA A100 datasheet: 80GB HBM2e. Cited by RetroInfer (arXiv:2505.02922) ref [66].",
    ),
    "h200_141gb": Accelerator(
        name="NVIDIA H200 141GB",
        memory_bytes=141e9,
        source="NVIDIA H200 datasheet: 141GB HBM3e.",
    ),
    "mi300x_192gb": Accelerator(
        name="AMD Instinct MI300X 192GB",
        memory_bytes=192e9,
        source="AMD Instinct MI300X datasheet: 192GB HBM3.",
    ),
}

# Serving-stack cap on concurrent sequences, independent of memory. Needed
# because with a purely memory-limited batch the per-user KV:weights ratio is
# constant in context length (see l_cross docstring) and no crossover exists.
BATCH_CAP_DEFAULT = 256
BATCH_CAP_SOURCE = (
    "vLLM default max_num_seqs=256 (vLLM EngineArgs documented default). Carried "
    "as a bracket {32, 256} because the effective cap is a deployment choice, not "
    "a hardware property. confidence: published (the default), estimated (that any "
    "given deployment uses it)."
)
BATCH_CAP_BRACKET = (32, 256)


def batch_max(
    accel_memory_bytes: float,
    spec: ModelSpec,
    context_len: float,
    *,
    quant: Quant = "fp16",
    kv_dtype: KvDtype = "fp16",
    memory_overhead_fraction: float = 0.0,
) -> float:
    """Memory-limited concurrent sequences at a given context length.

    (accelerator memory - weights) / (kv_bytes_per_token * context_len)

    Returned unrounded so the sanity check compares against the published
    integer without a rounding artifact hiding a real disagreement.
    """
    usable = accel_memory_bytes * (1.0 - memory_overhead_fraction)
    free = usable - weights_footprint(spec, quant)
    if free <= 0:
        return 0.0
    return free / (kv_bytes_per_token(spec, kv_dtype) * float(context_len))


# ---------------------------------------------------------------------------
# A1 sanity gate
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SanityAnchor:
    label: str
    accelerator: str
    model: str
    context_len: int
    published_batch: float
    source: str


SANITY_ANCHORS: tuple[SanityAnchor, ...] = (
    SanityAnchor(
        label="RetroInfer A100-80GB / 8B GQA @128K",
        accelerator="a100_80gb",
        model="llama31_8b",
        context_len=131072,
        published_batch=4.0,
        source=(
            "RetroInfer, arXiv:2505.02922 (also VLDB vol19 p1016), Introduction: "
            "'an A100 GPU (80GB memory) can support a maximum batch size of 4 at a "
            "128K context length for Llama3-8B. Exceeding this limit results in "
            "OOM errors.'"
        ),
    ),
    SanityAnchor(
        label="HERALD batch @8K",
        accelerator="a100_80gb",
        model="llama31_8b",
        context_len=8192,
        published_batch=70.0,
        source="HERALD, arXiv:2606.21633: batch ~70 at 8K falling to ~17 at 32K, ~60% throughput loss.",
    ),
    SanityAnchor(
        label="HERALD batch @32K",
        accelerator="a100_80gb",
        model="llama31_8b",
        context_len=32768,
        published_batch=17.0,
        source="HERALD, arXiv:2606.21633: batch ~70 at 8K falling to ~17 at 32K, ~60% throughput loss.",
    ),
)

SANITY_TOLERANCE = 2.0


@dataclass(frozen=True)
class SanityResult:
    anchor: SanityAnchor
    predicted_batch: float
    ratio: float          # predicted / published
    disagreement: float   # max(ratio, 1/ratio)
    passed: bool


def run_sanity_check(
    specs: dict[str, ModelSpec],
    *,
    tolerance: float = SANITY_TOLERANCE,
) -> tuple[bool, list[SanityResult]]:
    """Gate. If any anchor disagrees by more than ``tolerance``x, the arithmetic
    is wrong and A2/A3 must not be built on it."""
    results: list[SanityResult] = []
    for anchor in SANITY_ANCHORS:
        accel = ACCELERATORS[anchor.accelerator]
        predicted = batch_max(
            accel.memory_bytes, specs[anchor.model], anchor.context_len
        )
        ratio = predicted / anchor.published_batch if anchor.published_batch else float("inf")
        disagreement = max(ratio, 1.0 / ratio) if ratio > 0 else float("inf")
        results.append(
            SanityResult(
                anchor=anchor,
                predicted_batch=predicted,
                ratio=ratio,
                disagreement=disagreement,
                passed=disagreement <= tolerance,
            )
        )
    return all(r.passed for r in results), results


# ---------------------------------------------------------------------------
# A2 amortization collapse
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PerUserCost:
    context_len: float
    batch_memory_limited: float
    batch_effective: float
    weights_share_bytes: float
    kv_share_bytes: float
    total_bytes: float
    kv_dominates: bool


def per_user_memory_cost(
    accel_memory_bytes: float,
    spec: ModelSpec,
    context_len: float,
    *,
    quant: Quant = "fp16",
    kv_dtype: KvDtype = "fp16",
    batch_cap: float = BATCH_CAP_DEFAULT,
) -> PerUserCost:
    """Bytes of accelerator memory attributable to one concurrent user.

    weights_share = W / B(L)   (the amortization term)
    kv_share      = kv_footprint(L)   (private, un-amortizable)
    """
    b_mem = batch_max(
        accel_memory_bytes, spec, context_len, quant=quant, kv_dtype=kv_dtype
    )
    b_eff = min(b_mem, batch_cap) if b_mem > 0 else 0.0
    w = weights_footprint(spec, quant)
    w_share = w / b_eff if b_eff > 0 else float("inf")
    kv_share = kv_footprint(spec, context_len, kv_dtype)
    return PerUserCost(
        context_len=context_len,
        batch_memory_limited=b_mem,
        batch_effective=b_eff,
        weights_share_bytes=w_share,
        kv_share_bytes=kv_share,
        total_bytes=w_share + kv_share,
        kv_dominates=kv_share > w_share,
    )


def l_cross(
    spec: ModelSpec,
    *,
    quant: Quant = "fp16",
    kv_dtype: KvDtype = "fp16",
    batch_cap: float = BATCH_CAP_DEFAULT,
) -> float:
    """Context length where per-user KV exceeds the per-user weights share.

    ANALYTIC NOTE, and it is the point of A2: under a purely MEMORY-LIMITED
    batch there is no crossover at all. With B(L) = (M-W)/(kv_pt*L),

        weights_share = W / B(L) = W * kv_pt * L / (M - W)
        kv_share      = kv_pt * L

    both scale linearly in L, so their ratio is (M-W)/W -- a constant,
    independent of context length. A crossover exists only where some cap other
    than memory sets the batch, which is why ``batch_cap`` is required here and
    is carried as a bracket rather than a single value.

    In the capped regime weights_share = W/batch_cap is flat while kv_share
    grows linearly, so L_cross = W / (batch_cap * kv_bytes_per_token).
    """
    w = weights_footprint(spec, quant)
    return w / (batch_cap * kv_bytes_per_token(spec, kv_dtype))


def memory_limited_kv_to_weights_ratio(
    accel_memory_bytes: float, spec: ModelSpec, *, quant: Quant = "fp16"
) -> float:
    """(M - W) / W. Constant in context length. See l_cross docstring."""
    w = weights_footprint(spec, quant)
    return (accel_memory_bytes - w) / w


def collapse_ratio(l_low: float, l_high: float) -> float:
    """B(l_low)/B(l_high). Since B ~ 1/L this is exactly l_high/l_low for every
    model and accelerator -- an analytic result, not an empirical one."""
    return l_high / l_low


# ---------------------------------------------------------------------------
# A3 threshold prediction and published comparison
# ---------------------------------------------------------------------------
# A rational provider introduces a long-context price step where weight
# amortization has collapsed to a small number of concurrent users, because
# below that the per-token cost of serving is no longer covered by the standard
# rate. B_min is unobservable, so it is swept, not chosen.
B_MIN_SWEEP: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)


def predicted_knee(
    accel_memory_bytes: float,
    spec: ModelSpec,
    b_min: float,
    *,
    quant: Quant = "fp16",
    kv_dtype: KvDtype = "fp16",
) -> float:
    """Context length at which memory-limited batch falls to ``b_min``."""
    free = accel_memory_bytes - weights_footprint(spec, quant)
    if free <= 0:
        return 0.0
    return free / (b_min * kv_bytes_per_token(spec, kv_dtype))


@dataclass(frozen=True)
class PublishedThreshold:
    provider: str
    model: str
    threshold_tokens: float | None  # None = no long-context tier
    input_multiplier: float | None
    applies_to_whole_request: bool | None
    source: str
    confidence: str
    note: str = ""


PUBLISHED_THRESHOLDS: tuple[PublishedThreshold, ...] = (
    PublishedThreshold(
        provider="OpenAI",
        model="GPT-5.4",
        threshold_tokens=272_000,
        input_multiplier=2.0,
        applies_to_whole_request=True,
        source=(
            "alatirok.com 'LLM Long-Context Pricing Surcharge 2026' table "
            "(>272K, $2.50->$5.00 input, whole session); tokencost.app "
            "'anthropic-long-context-flat-pricing' comparison table (GPT-5.4, "
            "272K, $2.50->$5.00, 2x); developersdigest 'Frontier Model API "
            "Pricing July 2026' (verified 2026-07-24 against "
            "developers.openai.com/api/docs/pricing)."
        ),
        confidence="published",
        note=(
            "CONFLICT: morphllm.com 'LLM Context Window Comparison (2026)' lists "
            "OpenAI as having no long-context tier. Three sources against one, and "
            "the OpenAI pricing page itself carries a separate long-context column, "
            "so the dissent is treated as an error -- but it is recorded, not hidden."
        ),
    ),
    PublishedThreshold(
        provider="OpenAI",
        model="GPT-5.5",
        threshold_tokens=272_000,
        input_multiplier=2.0,
        applies_to_whole_request=True,
        source="alatirok.com surcharge table: >272K, $5.00->$10.00 input, $30->$45 output, whole session.",
        confidence="published",
    ),
    PublishedThreshold(
        provider="Google",
        model="Gemini 3.1 Pro",
        threshold_tokens=200_000,
        input_multiplier=2.0,
        applies_to_whole_request=True,
        source=(
            "ai.google.dev/gemini-api/docs/pricing via developersdigest (verified "
            "2026-07-24): input $2->$4, output $12->$18 above 200K; morphllm table "
            "concurs ($2.00/$12.00 -> $4.00/$18.00 at 200K)."
        ),
        confidence="published",
    ),
    PublishedThreshold(
        provider="Google",
        model="Gemini 2.5 Pro",
        threshold_tokens=200_000,
        input_multiplier=2.0,
        applies_to_whole_request=True,
        source="alatirok.com surcharge table: >200K input, $1.25->$2.50 input, $10->$15 output.",
        confidence="published",
    ),
    PublishedThreshold(
        provider="Alibaba",
        model="Qwen3.5-Plus",
        threshold_tokens=256_000,
        input_multiplier=1.25,
        applies_to_whole_request=None,
        source="morphllm.com context-window comparison: 256K threshold, $0.40/$2.40 -> $0.50/$3.00.",
        confidence="published",
    ),
    PublishedThreshold(
        provider="MiniMax",
        model="M3",
        threshold_tokens=512_000,
        input_multiplier=2.0,
        applies_to_whole_request=True,
        source="alatirok.com surcharge table: >512K, $0.60->$1.20 input, cache reads also doubled.",
        confidence="published",
    ),
    PublishedThreshold(
        provider="Anthropic",
        model="Claude Sonnet 4.6 / Opus 4.6-4.8",
        threshold_tokens=None,
        input_multiplier=None,
        applies_to_whole_request=None,
        source=(
            "finout.io Anthropic pricing guide and tokencost.app: the 2x input / "
            "1.5x output surcharge above 200K was ELIMINATED 2026-03-13; flat rate "
            "to 1M tokens. Sonnet 4.5 on the 1M beta retains the old 200K cliff."
        ),
        confidence="published",
        note=(
            "FALSIFIER for the cost-driven hypothesis: the threshold was removed on "
            "a date, with no corresponding change in accelerator memory capacity."
        ),
    ),
    PublishedThreshold(
        provider="DeepSeek",
        model="V3.2 / V4",
        threshold_tokens=None,
        input_multiplier=None,
        applies_to_whole_request=None,
        source="tokencost.app and morphllm tables: flat rate, no long-context tier.",
        confidence="published",
    ),
)
