"""D4: synthetic CallRecord generator with known ground-truth latency decomposition."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Literal

from apu_characterization.turntrace_v2.schema import CallRecord, StepFeatures

StepKind = Literal["locate", "edit", "verify", "reason"]


@dataclass(frozen=True)
class SynthConfig:
    name: str
    n_trajectories: int = 20
    turns_per_traj: int = 12
    prefill_a: float = 1e-8
    prefill_b: float = 2e-3
    prefill_c: float = 0.5
    prefill_noise: float = 0.05
    decode_rates: dict[str, float] | None = None  # tokens/sec by step kind
    decode_len_mean: dict[str, float] | None = None
    decode_len_sigma: dict[str, float] | None = None
    network_mu: float = 3.0  # lognormal
    network_sigma: float = 0.4
    spike_prob: float = 0.05
    spike_ms: float = 250.0
    seed: int = 0


DEFAULT_CONFIGS = (
    SynthConfig(name="low_variance", network_sigma=0.2, spike_prob=0.01, seed=1),
    SynthConfig(name="heavy_tail_reason", seed=2),
    SynthConfig(
        name="spiky_network",
        network_sigma=0.6,
        spike_prob=0.15,
        spike_ms=400.0,
        seed=3,
    ),
    # D2: explicit variable tokens_out per step type (incl. heavy-tailed reason).
    SynthConfig(
        name="variable_decode_lengths",
        seed=4,
        decode_len_mean={
            "locate": 20.0,
            "edit": 60.0,
            "verify": 12.0,
            "reason": 180.0,
        },
        decode_len_sigma={
            "locate": 0.35,
            "edit": 0.45,
            "verify": 0.25,
            "reason": 0.9,
        },
    ),
)


def _f(n: int, cfg: SynthConfig) -> float:
    return cfg.prefill_a * (n**2) + cfg.prefill_b * n + cfg.prefill_c


def generate_corpus(cfg: SynthConfig) -> tuple[list[CallRecord], dict]:
    rng = random.Random(cfg.seed)
    decode_rates = cfg.decode_rates or {
        "locate": 60.0,
        "edit": 50.0,
        "verify": 55.0,
        "reason": 35.0,
    }
    len_mean = cfg.decode_len_mean or {
        "locate": 40.0,
        "edit": 80.0,
        "verify": 30.0,
        "reason": 200.0,  # heavy-tailed reasoning
    }
    len_sigma = cfg.decode_len_sigma or {
        "locate": 0.2,
        "edit": 0.3,
        "verify": 0.2,
        "reason": 0.8,
    }
    kinds: list[StepKind] = ["locate", "edit", "verify", "reason"]
    records: list[CallRecord] = []
    truth = {
        "config": cfg.name,
        "f_params": {"a": cfg.prefill_a, "b": cfg.prefill_b, "c": cfg.prefill_c},
        "decode_rates": decode_rates,
        "network": {"mu": cfg.network_mu, "sigma": cfg.network_sigma},
        "spike_prob": cfg.spike_prob,
        "spike_ms": cfg.spike_ms,
    }
    for t in range(cfg.n_trajectories):
        traj_id = f"synth-{cfg.name}-{t:03d}"
        ctx = 256
        for i in range(cfg.turns_per_traj):
            kind = kinds[i % len(kinds)]
            new_tokens = 32 + (i * 8)
            ctx = ctx + new_tokens
            t_prefill_true = _f(ctx, cfg) + rng.gauss(0.0, cfg.prefill_noise)
            t_prefill_true = max(0.01, t_prefill_true)
            out_tokens = max(1, int(rng.lognormvariate(math.log(len_mean[kind]), len_sigma[kind])))
            rate = decode_rates[kind]
            t_decode_true = 1000.0 * out_tokens / rate
            t_network = rng.lognormvariate(cfg.network_mu, cfg.network_sigma)
            if rng.random() < cfg.spike_prob:
                t_network += cfg.spike_ms
            orch_pre, orch_post = 2.0, 1.5
            # Predictions at issue (known decomposition for acceptance).
            pred_prefill = _f(ctx, cfg)
            pred_decode = 1000.0 * len_mean[kind] / rate
            necessary = new_tokens
            redundant = max(0, ctx - necessary)
            t_necessary = _f(necessary, cfg)
            t_redundant = max(0.0, t_prefill_true - t_necessary)
            wall = (orch_pre + t_prefill_true + t_decode_true + t_network + orch_post) / 1000.0
            t0 = 1_000_000.0 + t * 1000 + i
            features = StepFeatures(
                is_tool_call=kind != "reason",
                tool_class="read_only" if kind in ("locate", "verify") else (
                    "state_mutating" if kind == "edit" else "none"
                ),
                repeat_count=(i // len(kinds)) + 1,
                loop_membership=kind in ("edit", "verify"),
                fanout_siblings=0,
                trajectory_position=i / max(1, cfg.turns_per_traj - 1),
            )
            records.append(
                CallRecord(
                    trajectory_id=traj_id,
                    turn_index=i,
                    harness_id="synthetic",
                    deployment_id="SYN",
                    step_type_semantic=kind,
                    step_features=features,
                    t_orch_pre_ms=orch_pre,
                    t_orch_post_ms=orch_post,
                    t_network_ms=t_network,
                    network_method="measured",
                    t_prefill_ms=t_prefill_true,
                    prefill_method="direct",
                    t_decode_ms=t_decode_true,
                    context_tokens_in=ctx,
                    engine_tokens_in=ctx,
                    requested_tokens_in=ctx,
                    token_reconciliation_delta=0,
                    tokens_out=out_tokens,
                    call_shape_ratio=ctx / out_tokens,
                    cache_state="disabled",
                    prefix_hit_tokens=0,
                    prefill_necessary_tokens=necessary,
                    prefill_redundant_tokens=redundant,
                    t_prefill_necessary_ms=t_necessary,
                    t_prefill_redundant_ms=t_redundant,
                    retemplated_tokens=0,
                    pred_context_tokens=ctx,
                    pred_cache_state="disabled",
                    pred_decode_tokens=len_mean[kind],
                    pred_t_prefill_ms=pred_prefill,
                    pred_t_decode_ms=pred_decode,
                    energy_j=None,
                    model_id="synthetic",
                    quantization="n/a",
                    reasoning_mode="on" if kind == "reason" else "off",
                    engine="synth",
                    engine_version="1",
                    wall_clock_start=t0,
                    wall_clock_end=t0 + wall,
                    audit_flags=[],
                )
            )
    return records, truth
