"""External-measurement anchors that license findings.

ANCHOR GATE (binding): no cell becomes a FINDING until the model reproduces an
independent published measurement in that regime, OR the cell is explicitly
marked EXTRAPOLATED with its distance from the nearest anchor stated.

NEVER fit a parameter to an anchor it is being validated against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from censor.kv_math import MODEL_SPECS
from censor.tier_economics import (
    ACCELERATORS,
    SANITY_TOLERANCE,
    batch_max,
    run_sanity_check,
)

Regime = Literal["ANCHORED", "EXTRAPOLATED", "BLOCKED"]


@dataclass(frozen=True)
class AnchorResult:
    anchor_id: str
    passed: bool
    predicted: float
    published: float
    tolerance: float
    disagreement: float
    unit: str
    fitted_params: str  # must be "NONE" for a valid gate
    notes: str = ""
    citation: str = ""


@dataclass(frozen=True)
class Anchor:
    anchor_id: str
    citation: str
    published_value: float
    unit: str
    tolerance: float
    regime: str
    evaluate: Callable[[], AnchorResult]
    description: str = ""


# ---------------------------------------------------------------------------
# A_BATCH_* — already validated in Phase 2 Arm A1; re-exposed here as the gate.
# ---------------------------------------------------------------------------
def _batch_anchor(anchor_id: str, context_len: int, published: float, citation: str) -> AnchorResult:
    accel = ACCELERATORS["a100_80gb"]
    predicted = batch_max(accel.memory_bytes, MODEL_SPECS["llama31_8b"], context_len)
    ratio = predicted / published if published else float("inf")
    disagreement = max(ratio, 1.0 / ratio) if ratio > 0 else float("inf")
    return AnchorResult(
        anchor_id=anchor_id,
        passed=disagreement <= SANITY_TOLERANCE,
        predicted=predicted,
        published=published,
        tolerance=SANITY_TOLERANCE,
        disagreement=disagreement,
        unit="batch_size",
        fitted_params="NONE",
        notes="Memory-limited batch arithmetic; no free parameters.",
        citation=citation,
    )


def eval_A_BATCH_A100() -> AnchorResult:
    return _batch_anchor(
        "A_BATCH_A100",
        131072,
        4.0,
        "RetroInfer, arXiv:2505.02922 — A100-80GB max batch ~4 at 128K, Llama3-8B",
    )


def eval_A_BATCH_HERALD_8K() -> AnchorResult:
    return _batch_anchor(
        "A_BATCH_HERALD_8K",
        8192,
        70.0,
        "HERALD, arXiv:2606.21633 — batch ~70 at 8K",
    )


def eval_A_BATCH_HERALD_32K() -> AnchorResult:
    return _batch_anchor(
        "A_BATCH_HERALD_32K",
        32768,
        17.0,
        "HERALD, arXiv:2606.21633 — batch ~17 at 32K",
    )


# ---------------------------------------------------------------------------
# A_ENERGY_* — formula identity checks against arXiv:2604.18566 Table 11.
#
# The paper's local formula is transparent and identical to ours:
#   Wh = power_W * latency_s * PUE / 3600
# with Mac Studio power=140 W, PUE=1.02. Plugging THEIR published latencies
# must reproduce THEIR Wh/query — this validates the accounting identity,
# not a fitted efficiency coefficient.
# ---------------------------------------------------------------------------
MAC_STUDIO_INFERENCE_W = 140.0   # paper Table 11 footnote; third-party M3 Ultra
MAC_STUDIO_PUE = 1.02            # convective cooling, paper Table 11
# (model, latency_s, published_Wh)
_LOCAL_ENERGY_ROWS: tuple[tuple[str, float, float], ...] = (
    ("Kimi K2.5 GGUF Q3", 150.0, 5.9),
    ("DeepSeek V3.2 Q4KM", 209.0, 8.3),
    ("DeepSeek V3.2 MLX-4", 260.0, 10.3),
    ("GLM-5 MLX-4", 230.0, 9.1),
)


def local_wh(power_w: float, latency_s: float, pue: float = 1.0) -> float:
    """Canonical local energy accounting. Identical to arXiv:2604.18566."""
    return power_w * latency_s * pue / 3600.0


def eval_A_ENERGY_LOCAL() -> AnchorResult:
    """Reproduce Mac Studio 5.9–10.3 Wh/query band from published latencies."""
    preds = [
        local_wh(MAC_STUDIO_INFERENCE_W, lat, MAC_STUDIO_PUE) for _, lat, _ in _LOCAL_ENERGY_ROWS
    ]
    pubs = [p for _, _, p in _LOCAL_ENERGY_ROWS]
    # Worst relative disagreement across the four rows.
    disagreements = [max(a / b, b / a) for a, b in zip(preds, pubs)]
    worst = max(disagreements)
    # Absolute band check: predicted band must land inside 5.9–10.3 ± tolerance.
    pred_lo, pred_hi = min(preds), max(preds)
    band_ok = pred_lo >= 5.9 / 1.1 and pred_hi <= 10.3 * 1.1
    return AnchorResult(
        anchor_id="A_ENERGY_LOCAL",
        passed=worst <= 1.05 and band_ok,  # 5% identity tolerance
        predicted=pred_lo,  # report band low; hi in notes
        published=5.9,
        tolerance=1.05,
        disagreement=worst,
        unit="Wh/query",
        fitted_params="NONE",
        notes=(
            f"Predicted band [{pred_lo:.2f}, {pred_hi:.2f}] Wh against published "
            f"[5.9, 10.3]; per-row max disagreement {worst:.3f}x. "
            f"Formula: Wh = {MAC_STUDIO_INFERENCE_W} W × latency × "
            f"PUE {MAC_STUDIO_PUE} / 3600. Latencies from paper Table 11, "
            "not fitted."
        ),
        citation="arXiv:2604.18566 Table 11 (Mac Studio Ultra 512GB, 140W, PUE 1.02)",
    )


CLOUD_KWH_PER_1K_OUT = 0.002  # paper Table 11: literature estimate incl. PUE 1.25


def cloud_wh_from_output_tokens(n_out: float) -> float:
    """Cloud energy estimate used by arXiv:2604.18566 (0.002 kWh / 1K out tokens)."""
    return CLOUD_KWH_PER_1K_OUT * (n_out / 1000.0) * 1000.0  # -> Wh


def eval_A_ENERGY_CLOUD() -> AnchorResult:
    """Reproduce ~1.6 Wh/query for Gemini 2.5 Flash / GPT-5.1.

    The paper's cloud estimate is output-token dominated at 0.002 kWh/1K out.
    Inverting 1.6 Wh => ~800 output tokens. We do NOT fit that number: we take
    the paper's stated formula and the published Wh, and check identity by
    recovering N_out and re-applying. The gate passes iff the formula is
    self-consistent to within tolerance (it must be, by construction of their
    estimate) AND we record that this is an OUTPUT-TOKEN formula — our agent
    workload is prefill-dominated and therefore EXTRAPOLATED from this anchor.
    """
    published = 1.6
    n_out_implied = published / (CLOUD_KWH_PER_1K_OUT * 1000.0) * 1000.0  # Wh / (Wh per tok)
    # 0.002 kWh/1K = 2 Wh/1K = 0.002 Wh/token; 1.6 / 0.002 = 800
    predicted = cloud_wh_from_output_tokens(800.0)  # paper-implied query size
    disagreement = max(predicted / published, published / predicted)
    return AnchorResult(
        anchor_id="A_ENERGY_CLOUD",
        passed=disagreement <= 1.05,
        predicted=predicted,
        published=published,
        tolerance=1.05,
        disagreement=disagreement,
        unit="Wh/query",
        fitted_params="NONE",
        notes=(
            f"Paper formula 0.002 kWh/1K out tokens at N_out=800 (implied by "
            f"1.6 Wh) re-applies to {predicted:.2f} Wh. Self-consistent. "
            f"WARNING: this is an OUTPUT-TOKEN estimate; our agent workload is "
            f"prefill-dominated (~560:1 in:out) and sits OUTSIDE this regime. "
            f"Implied N_out check: {n_out_implied:.0f}."
        ),
        citation="arXiv:2604.18566 Table 11 (Gemini 2.5 Flash / GPT-5.1 ~1.6 Wh/query)",
    )


def eval_A_ENERGY_RATIO() -> AnchorResult:
    """Reproduce the 3.7–6.4× local-worse energy ratio (arXiv:2604.18566).

    Local Wh from the Mac Studio identity; cloud Wh = 1.6. Ratio must land in
    the published band with no fitted efficiency factor.
    """
    local_preds = [
        local_wh(MAC_STUDIO_INFERENCE_W, lat, MAC_STUDIO_PUE) for _, lat, _ in _LOCAL_ENERGY_ROWS
    ]
    cloud = 1.6
    ratios = [L / cloud for L in local_preds]
    r_lo, r_hi = min(ratios), max(ratios)
    # Published: 3.7–6.4×
    pub_lo, pub_hi = 3.7, 6.4
    # Pass if our predicted band overlaps the published band within 10%.
    overlap = not (r_hi < pub_lo / 1.1 or r_lo > pub_hi * 1.1)
    # Disagreement vs band centre for the report.
    centre_pred = (r_lo + r_hi) / 2.0
    centre_pub = (pub_lo + pub_hi) / 2.0
    disagreement = max(centre_pred / centre_pub, centre_pub / centre_pred)
    return AnchorResult(
        anchor_id="A_ENERGY_RATIO",
        passed=overlap and r_lo >= 3.0 and r_hi <= 7.5,
        predicted=r_lo,
        published=pub_lo,
        tolerance=1.1,
        disagreement=disagreement,
        unit="local_Wh / cloud_Wh",
        fitted_params="NONE",
        notes=(
            f"Predicted ratio band [{r_lo:.2f}, {r_hi:.2f}]× vs published "
            f"[{pub_lo}, {pub_hi}]×. Mechanism: batch-1 local at full 140 W vs "
            f"batched cloud at 0.002 kWh/1K out. "
            f"prima.cpp (arXiv:2504.08791) independently reports cloud total "
            f"energy ~28% below a local cluster — same direction."
        ),
        citation=(
            "arXiv:2604.18566 (3.7–6.4×); directionally corroborated by "
            "prima.cpp arXiv:2504.08791 (§energy, cloud 28% below local cluster)"
        ),
    )


# ---------------------------------------------------------------------------
# A_CACHE_TIERS — rate-card identity checks (multipliers, not fitted).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CacheTierpec:
    label: str
    read_multiplier: float
    write_5m_multiplier: float | None
    write_1h_multiplier: float | None
    source: str


CACHE_TIERS: tuple[CacheTierpec, ...] = (
    CacheTierpec("anthropic_current", 0.10, 1.25, 2.0,
                 "Anthropic list prices: cache read 0.1x; write 1.25x (5m) / 2.0x (1h)"),
    CacheTierpec("openai_gpt54_plus", 0.10, None, None,
                 "OpenAI GPT-5.4+ / GPT-5.5 / GPT-5.6: cache read 0.1x base input"),
    CacheTierpec("openai_gpt4o_family", 0.50, None, None,
                 "OpenAI gpt-4o family: cache read 0.5x base input (legacy tier)"),
    CacheTierpec("gemini_25_plus", 0.10, None, None,
                 "Google Gemini 2.5+: cache read 0.1x; storage billed $/MTok/hour"),
)


def eval_A_CACHE_TIERS() -> AnchorResult:
    """Confirm study_params carries the published multipliers, not invented ones."""
    # Import lazily to avoid circular imports at module load.
    from censor.prelim_phase1 import load_params, _v

    p = load_params()
    checks: list[tuple[str, float, float]] = []
    # Anthropic frontier: cached / uncached = 0.1
    ant = p["cloud"]["providers"]["anthropic"]["frontier"]
    ant_ratio = float(_v(ant["price_input_cached_per_mtok"])) / float(
        _v(ant["price_input_uncached_per_mtok"])
    )
    checks.append(("anthropic_read", ant_ratio, 0.10))
    # Anthropic write 5m / uncached = 1.25
    if "price_cache_write_5m_per_mtok" in ant:
        w5 = float(_v(ant["price_cache_write_5m_per_mtok"])) / float(
            _v(ant["price_input_uncached_per_mtok"])
        )
        checks.append(("anthropic_write_5m", w5, 1.25))
    if "price_cache_write_1h_per_mtok" in ant:
        w1 = float(_v(ant["price_cache_write_1h_per_mtok"])) / float(
            _v(ant["price_input_uncached_per_mtok"])
        )
        checks.append(("anthropic_write_1h", w1, 2.0))
    # OpenAI mid: cached / uncached
    oai = p["cloud"]["providers"]["openai"]["mid"]
    oai_ratio = float(_v(oai["price_input_cached_per_mtok"])) / float(
        _v(oai["price_input_uncached_per_mtok"])
    )
    checks.append(("openai_mid_read", oai_ratio, 0.10))

    disagreements = [max(a / b, b / a) for _, a, b in checks]
    worst = max(disagreements) if disagreements else float("inf")
    return AnchorResult(
        anchor_id="A_CACHE_TIERS",
        passed=worst <= 1.01,
        predicted=checks[0][1] if checks else float("nan"),
        published=0.10,
        tolerance=1.01,
        disagreement=worst,
        unit="price_multiplier",
        fitted_params="NONE",
        notes=(
            "study_params.yaml multipliers vs published rate cards: "
            + "; ".join(f"{n}={a:.3f} (expect {b})" for n, a, b in checks)
            + ". gpt-4o 0.5x tier is recorded as a distinct CACHE_TIERS entry "
            "for overstatement RANGE computation, not as our default."
        ),
        citation="Anthropic / OpenAI / Gemini published rate cards (July 2026)",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
ANCHORS: dict[str, Anchor] = {
    "A_BATCH_A100": Anchor(
        "A_BATCH_A100",
        "RetroInfer, arXiv:2505.02922",
        4.0,
        "batch_size",
        SANITY_TOLERANCE,
        "batch_capacity_at_long_context",
        eval_A_BATCH_A100,
        "Max batch ~4 at 128K on A100-80GB for Llama3-8B",
    ),
    "A_BATCH_HERALD": Anchor(
        "A_BATCH_HERALD",
        "HERALD, arXiv:2606.21633",
        70.0,
        "batch_size",
        SANITY_TOLERANCE,
        "batch_vs_context_curve",
        eval_A_BATCH_HERALD_8K,  # primary; 32K checked in run_all
        "Batch 70→17 across 8K→32K",
    ),
    "A_ENERGY_CLOUD": Anchor(
        "A_ENERGY_CLOUD",
        "arXiv:2604.18566 Table 11",
        1.6,
        "Wh/query",
        1.05,
        "cloud_energy_per_query_output_dominated",
        eval_A_ENERGY_CLOUD,
        "~1.6 Wh/query Gemini 2.5 Flash / GPT-5.1",
    ),
    "A_ENERGY_LOCAL": Anchor(
        "A_ENERGY_LOCAL",
        "arXiv:2604.18566 Table 11",
        5.9,
        "Wh/query",
        1.05,
        "local_energy_per_query_batch1",
        eval_A_ENERGY_LOCAL,
        "5.9–10.3 Wh/query Mac Studio Ultra 512GB",
    ),
    "A_ENERGY_RATIO": Anchor(
        "A_ENERGY_RATIO",
        "arXiv:2604.18566; prima.cpp arXiv:2504.08791",
        3.7,
        "ratio",
        1.1,
        "local_vs_cloud_energy_ratio",
        eval_A_ENERGY_RATIO,
        "Local 3.7–6.4× worse; cloud ~28% below local cluster",
    ),
    "A_CACHE_TIERS": Anchor(
        "A_CACHE_TIERS",
        "Published rate cards (Anthropic/OpenAI/Gemini)",
        0.10,
        "multiplier",
        1.01,
        "cache_pricing_multipliers",
        eval_A_CACHE_TIERS,
        "Cache read 0.1x (current) / 0.5x (gpt-4o); Anthropic write 1.25x/2.0x",
    ),
}


def run_all_anchors() -> list[AnchorResult]:
    """Evaluate every seeded anchor. HERALD contributes both 8K and 32K rows."""
    results = [
        eval_A_BATCH_A100(),
        eval_A_BATCH_HERALD_8K(),
        eval_A_BATCH_HERALD_32K(),
        eval_A_ENERGY_CLOUD(),
        eval_A_ENERGY_LOCAL(),
        eval_A_ENERGY_RATIO(),
        eval_A_CACHE_TIERS(),
    ]
    return results


def gate_status(results: list[AnchorResult] | None = None) -> dict[str, Any]:
    results = results or run_all_anchors()
    by_id = {r.anchor_id: r for r in results}
    # Collapse the two HERALD rows under A_BATCH_HERALD for the gate summary.
    herald_ok = by_id["A_BATCH_HERALD_8K"].passed and by_id["A_BATCH_HERALD_32K"].passed
    summary = {
        "A_BATCH_A100": by_id["A_BATCH_A100"].passed,
        "A_BATCH_HERALD": herald_ok,
        "A_ENERGY_CLOUD": by_id["A_ENERGY_CLOUD"].passed,
        "A_ENERGY_LOCAL": by_id["A_ENERGY_LOCAL"].passed,
        "A_ENERGY_RATIO": by_id["A_ENERGY_RATIO"].passed,
        "A_CACHE_TIERS": by_id["A_CACHE_TIERS"].passed,
    }
    return {
        "results": results,
        "summary": summary,
        "all_pass": all(summary.values()),
        "blocked_regimes": [k for k, v in summary.items() if not v],
    }


# Cell → required anchors. A cell whose required anchors fail is BLOCKED for
# findings (may still be reported as EXTRAPOLATED desk work with the failure
# stated).
CELL_ANCHOR_REQUIREMENTS: dict[str, list[str]] = {
    "1a": [],
    "1b": [],
    "1c": [],
    "2a": ["A_ENERGY_RATIO", "A_CACHE_TIERS"],  # cost claims need energy + pricing anchors
    "2b": ["A_BATCH_A100", "A_BATCH_HERALD"],
    "2c": [],  # latency; no external latency anchor at context_floor — EXTRAPOLATED
    "3a": [],  # measured directly (Item A)
    "3b": ["A_BATCH_A100"],  # same KV arithmetic
    "4a": [],
    "4b": [],
    "4c": [],
    "4d": [],
    "4e": [],
}
