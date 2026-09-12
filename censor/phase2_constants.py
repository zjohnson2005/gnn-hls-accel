"""Phase-2 engine constants (F1–F4 friction parameters). No unsourced numbers.

Renamed from ``censor/params.py`` to avoid collision with the preliminary
study parameter set at ``censor/study_params.yaml``. Do not import this module
from Phase-1 (tiers / prelim) code.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from censor.schema import SourcedFloat


@dataclass
class F1Params:
    """Decision-cost parameters (paid regardless of routing quality)."""

    enabled: bool = True
    orch_floor_ms_lo: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            3.9,
            "CAP-01 protocol_cap01_v2.json floor_anchor.promoted_reference_bands_ms.langgraph[0]; "
            "TurnTrace/CAP-01 measured orchestration floor",
        )
    )
    orch_floor_ms_hi: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            7.0,
            "CAP-01 protocol_cap01_v2.json floor_anchor.promoted_reference_bands_ms.langgraph[1]; "
            "TurnTrace/CAP-01 measured orchestration floor",
        )
    )
    # Point used in deterministic cost; midpoint of measured band.
    orch_floor_ms: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            5.45,
            "midpoint of CAP-01 langgraph floor band [3.9, 7.0] ms",
        )
    )
    router_type: str = "embedding"
    router_cost_ms: dict[str, SourcedFloat] = field(
        default_factory=lambda: {
            "rule": SourcedFloat(
                1.0,
                "practitioner router latency survey (rule-based): ~1 ms; "
                "see params.ROUTER_COST_CITATION",
            ),
            "embedding": SourcedFloat(
                5.0,
                "practitioner router latency survey (embedding similarity): ~5 ms; "
                "see params.ROUTER_COST_CITATION",
            ),
            "classifier": SourcedFloat(
                75.0,
                "practitioner router latency survey (small classifier): ~75 ms; "
                "see params.ROUTER_COST_CITATION",
            ),
            "llm": SourcedFloat(
                430.0,
                "practitioner router latency survey (LLM-as-router): ~430 ms; "
                "see params.ROUTER_COST_CITATION",
            ),
        }
    )
    # Decision energy: router + orch at assumed package power.
    decision_power_w: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            15.0,
            "conservative host package draw during light CPU orchestration "
            "(order-of-magnitude; Phase 5 RAPL calibration replaces)",
        )
    )
    # Local model latency used only to FLAG router > local crossover.
    local_model_latency_ms_lo: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            5.4,
            "user-stated TurnTrace crossover band lower edge (5.4–8.4 ms) "
            "where orchestration floor meets short local model calls",
        )
    )
    local_model_latency_ms_hi: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            8.4,
            "user-stated TurnTrace crossover band upper edge (5.4–8.4 ms)",
        )
    )


# Citation block for router costs (practitioner literature / public writeups).
ROUTER_COST_CITATION = (
    "Router latency defaults (rule≈1 ms, embedding≈5 ms, classifier≈75 ms, "
    "LLM≈430 ms) are order-of-magnitude figures from published hybrid-routing "
    "practitioner measurements and open router benchmarks (e.g. RouteLLM-style "
    "classifier/embedding routers vs generative LLM routers). Exact host "
    "calibration is Phase 5; these values are labeled as practitioner-sourced "
    "priors, not this corpus's measurements."
)


@dataclass
class F2Params:
    """KV-switch / re-prefill switching cost parameters."""

    enabled: bool = True
    # Cloud prefill time model when logged prefill isolate is absent.
    cloud_prefill_ms_per_token: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            0.05,
            "OA-01 nonstreaming corpus lacks prefill isolate; "
            "0.05 ms/token is a conservative cloud prefill prior "
            "consistent with TurnTrace C1 openai-processing-ms / token ratios "
            "on short contexts (order 0.03–0.1 ms/tok)",
        )
    )
    local_prefill_ms_per_token: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            0.4,
            "local GPU/NPU prefill prior ~0.4 ms/token for mid-size local "
            "models under common llama.cpp/vLLM deployments; Phase 5 replaces "
            "with box-calibrated f(n)",
        )
    )
    cloud_usd_per_1m_input: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            2.0,
            "OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.input",
        )
    )
    cloud_usd_per_1m_cached_input: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            0.5,
            "OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.cached_input",
        )
    )
    cloud_usd_per_1m_output: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            8.0,
            "OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.output",
        )
    )
    # Warm continuation bills only necessary (new) tokens at full price;
    # redundant prefix at cached rate when staying on cloud.
    warm_uses_cached_rate: bool = True


@dataclass
class F3Params:
    """Cloud capacity / rate-limit ceiling."""

    enabled: bool = True
    max_speedup: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            1.19,
            "TLP-01 Tier-C rate-limit floor speedup on MT-RS-01 "
            "(apu_characterization/out/tlp01/t2/t2_ladder_report.md: 1.19x)",
        )
    )
    # Naive oracle concurrency fantasy when F3 is disabled.
    assumed_concurrency: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            8.0,
            "illustrative naive 'unlimited cloud parallelism' assumption "
            "used only when F3 is OFF; not a measurement",
        )
    )


@dataclass
class F4Params:
    """Local sustained-throughput degradation (Phase 2 stub)."""

    enabled: bool = True
    capacity_factor: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            1.0,
            "UNMEASURED Phase-2 stub: no degradation; Phase 5 replaces with "
            "measured discharge/recharge curves",
        )
    )
    measurement_status: str = "UNMEASURED"


@dataclass
class InferenceParams:
    """Per-tier inference cost model for oracle / baselines."""

    local_decode_ms_per_token: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            8.0,
            "local decode prior ~8 ms/token (small/mid local model); "
            "Phase 5 box calibration replaces",
        )
    )
    local_prefill_ms_per_token: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            0.4,
            "same source as F2Params.local_prefill_ms_per_token",
        )
    )
    local_usd_per_kwh: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            0.12,
            "US average retail electricity order-of-magnitude (EIA-style); "
            "used only for local USD proxy",
        )
    )
    local_power_w: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            100.0,
            "illustrative GPU/NPU package draw during generation; "
            "Phase 5 RAPL/NVML replaces",
        )
    )
    cloud_usd_per_1m_input: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            2.0,
            "OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.input",
        )
    )
    cloud_usd_per_1m_cached_input: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            0.5,
            "OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.cached_input",
        )
    )
    cloud_usd_per_1m_output: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            8.0,
            "OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.output",
        )
    )
    cloud_prefill_ms_per_token: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            0.05,
            "same prior as F2Params.cloud_prefill_ms_per_token "
            "(TurnTrace C1 processing-ms/token order)",
        )
    )
    cloud_decode_ms_per_token: SourcedFloat = field(
        default_factory=lambda: SourcedFloat(
            25.0,
            "practitioner cloud decode prior ~25 ms/output-token when "
            "streaming isolate absent (OA-01 nonstreaming); used only as "
            "fallback when logged_latency_ms is missing",
        )
    )


@dataclass
class CostModelParams:
    f1: F1Params = field(default_factory=F1Params)
    f2: F2Params = field(default_factory=F2Params)
    f3: F3Params = field(default_factory=F3Params)
    f4: F4Params = field(default_factory=F4Params)
    inference: InferenceParams = field(default_factory=InferenceParams)
    # Primary waterfall metric: wall-clock seconds (USD tracked alongside).
    primary_metric: str = "seconds"

    def with_friction_mask(self, enabled: dict[str, bool]) -> "CostModelParams":
        """Return a copy with F1–F4 enable bits set from ``enabled``."""
        return replace(
            self,
            f1=replace(self.f1, enabled=enabled.get("F1", self.f1.enabled)),
            f2=replace(self.f2, enabled=enabled.get("F2", self.f2.enabled)),
            f3=replace(self.f3, enabled=enabled.get("F3", self.f3.enabled)),
            f4=replace(self.f4, enabled=enabled.get("F4", self.f4.enabled)),
        )

    def to_audit_dict(self) -> dict[str, Any]:
        """Serialize all sourced constants for artifact audit."""

        def _sf(x: SourcedFloat) -> dict[str, Any]:
            return {"value": x.value, "source": x.source}

        return {
            "ROUTER_COST_CITATION": ROUTER_COST_CITATION,
            "f1": {
                "enabled": self.f1.enabled,
                "orch_floor_ms": _sf(self.f1.orch_floor_ms),
                "orch_floor_ms_lo": _sf(self.f1.orch_floor_ms_lo),
                "orch_floor_ms_hi": _sf(self.f1.orch_floor_ms_hi),
                "router_type": self.f1.router_type,
                "router_cost_ms": {k: _sf(v) for k, v in self.f1.router_cost_ms.items()},
                "decision_power_w": _sf(self.f1.decision_power_w),
                "local_model_latency_ms_lo": _sf(self.f1.local_model_latency_ms_lo),
                "local_model_latency_ms_hi": _sf(self.f1.local_model_latency_ms_hi),
            },
            "f2": {
                "enabled": self.f2.enabled,
                "cloud_prefill_ms_per_token": _sf(self.f2.cloud_prefill_ms_per_token),
                "local_prefill_ms_per_token": _sf(self.f2.local_prefill_ms_per_token),
                "cloud_usd_per_1m_input": _sf(self.f2.cloud_usd_per_1m_input),
                "cloud_usd_per_1m_cached_input": _sf(self.f2.cloud_usd_per_1m_cached_input),
                "cloud_usd_per_1m_output": _sf(self.f2.cloud_usd_per_1m_output),
            },
            "f3": {
                "enabled": self.f3.enabled,
                "max_speedup": _sf(self.f3.max_speedup),
                "assumed_concurrency": _sf(self.f3.assumed_concurrency),
            },
            "f4": {
                "enabled": self.f4.enabled,
                "capacity_factor": _sf(self.f4.capacity_factor),
                "measurement_status": self.f4.measurement_status,
            },
            "inference": {
                "local_decode_ms_per_token": _sf(self.inference.local_decode_ms_per_token),
                "local_prefill_ms_per_token": _sf(self.inference.local_prefill_ms_per_token),
                "local_usd_per_kwh": _sf(self.inference.local_usd_per_kwh),
                "local_power_w": _sf(self.inference.local_power_w),
                "cloud_usd_per_1m_input": _sf(self.inference.cloud_usd_per_1m_input),
                "cloud_usd_per_1m_cached_input": _sf(
                    self.inference.cloud_usd_per_1m_cached_input
                ),
                "cloud_usd_per_1m_output": _sf(self.inference.cloud_usd_per_1m_output),
                "cloud_prefill_ms_per_token": _sf(
                    self.inference.cloud_prefill_ms_per_token
                ),
                "cloud_decode_ms_per_token": _sf(
                    self.inference.cloud_decode_ms_per_token
                ),
            },
        }
