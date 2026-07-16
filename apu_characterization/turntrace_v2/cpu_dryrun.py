"""P1 CPU dry-run orchestrator: calibrate → trajectories → derive → replay → gate artifacts."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from apu_characterization.turntrace_v2.calibrate_live import (
    DEFAULT_PREFILL_GRID_CPU,
    calibrate_decode,
    calibrate_prefill,
    verify_cache_behavior,
)
from apu_characterization.turntrace_v2.coverage import assert_coverage_or_raise, domain_bounds
from apu_characterization.turntrace_v2.derive import derive_call_records, derive_trajectory_record
from apu_characterization.turntrace_v2.engines import CompletionResult, EngineIdentity
from apu_characterization.turntrace_v2.engines.llamacpp import LlamaCppServerEngine
from apu_characterization.turntrace_v2.export import export_parquet
from apu_characterization.turntrace_v2.labeling import validate_taxonomy
from apu_characterization.turntrace_v2.mock_engine import MockEngine
from apu_characterization.turntrace_v2.replay import load_bundle, swapped_step_replay
from apu_characterization.turntrace_v2.workload.toy_agent import ToyAgentConfig, run_toy_trajectory


def wait_for_server(base_url: str, *, timeout_s: float = 180.0) -> None:
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(1.0)
    raise RuntimeError(f"llama-server not healthy at {base_url}: {last_err}")


def _load_prefill(cal_dir: Path):
    from apu_characterization.turntrace_v2.calibration import PrefillProfile

    raw = json.loads((cal_dir / "prefill_profile.json").read_text(encoding="utf-8"))
    prefill = PrefillProfile(
        model_id=raw["model_id"],
        quantization=raw["quantization"],
        engine=raw["engine"],
        hardware=raw["hardware"],
    )
    for pt in raw["points"]:
        prefill.add_observation(int(pt["n"]), float(pt["t_prefill_ms"]))
    prefill.fit(held_out_fraction=0.2, r2_gate=0.99, seed=7)
    envelope = raw.get("token_reconciliation") or {}
    if (cal_dir / "token_reconciliation_envelope.json").is_file():
        envelope = json.loads(
            (cal_dir / "token_reconciliation_envelope.json").read_text(encoding="utf-8")
        )
    return prefill, envelope


def _mock_adapter(identity: EngineIdentity):
    mock = MockEngine()

    class _Adapter:
        def __init__(self) -> None:
            self.identity = identity

        def complete(self, prompt, **kwargs):
            text = prompt if isinstance(prompt, str) else " ".join(
                str(m.get("content", "")) for m in prompt
            )
            max_tokens = int(kwargs.get("max_tokens") or 8)
            r = mock.complete(text or "x", max_tokens=max_tokens)
            ids = list(range(r["context_tokens_in"]))
            return CompletionResult(
                text=r["text"],
                engine_tokens_in=r["context_tokens_in"],
                tokens_out=r["tokens_out"],
                t_prefill_ms=r["t_prefill_ms"],
                t_decode_ms=r["t_decode_ms"],
                t_network_ms=0.0,
                network_method="measured",
                prefill_method="direct",
                cache_state=r["cache_state"],
                prefix_hit_tokens=r["prefix_hit_tokens"],
                model_id=identity.model_id,
                quantization=identity.quantization,
                engine=identity.engine,
                engine_version=identity.engine_version,
                reasoning_mode="off",
                tokenizer_id="whitespace_v0",
                requested_tokens_in=r["context_tokens_in"],
                engine_token_ids=ids,
            )

        def tokenize(self, text: str):
            return list(range(len(text.split())))

        def tokenize_messages(self, messages):
            text = " ".join(str(m.get("content", "")) for m in messages)
            return self.tokenize(text)

        def close(self):
            return None

    return _Adapter()


def run_cpu_dryrun(
    *,
    out_dir: Path,
    base_url: str = "http://127.0.0.1:8080",
    n_trajectories: int = 5,
    n_turns: int = 6,
    prefill_reps: int = 10,
    skip_live: bool = False,
    reuse_calibration: bool = False,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cal_dir = out_dir / "calibration"
    traj_dir = out_dir / "trajectories"
    bundle_dir = out_dir / "bundles"
    corpus_dir = out_dir / "corpus"

    token_delta_lo: float | None = None
    token_delta_hi: float | None = None

    if skip_live:
        from apu_characterization.turntrace_v2.calibration import synthesize_prefill_sweep

        # Extended synthetic grid covering small-n domain.
        prefill = synthesize_prefill_sweep(
            seed=1,
            n_grid=DEFAULT_PREFILL_GRID_CPU,
            reps=10,
        )
        engine = None
        identity = EngineIdentity(
            deployment_id="CPU0",
            model_id="mock-fallback",
            quantization="n/a",
            engine="mock",
            engine_version="0",
            hardware="ci",
            reasoning_mode="off",
            provisional=True,
        )
        cache_report = {"passed": True, "note": "skipped_live", "provisional": True}
        decode = None
    else:
        wait_for_server(base_url)
        identity = EngineIdentity(
            deployment_id="CPU0",
            model_id="tinyllama-1.1b-chat-v1.0",
            quantization="Q4_K_M",
            engine="llama.cpp",
            engine_version="b10012-win-cpu",
            hardware="cpu-host",
            reasoning_mode="off",
            provisional=True,
        )
        engine = LlamaCppServerEngine(base_url=base_url, identity=identity)
        try:
            props = engine.props()
        except Exception:
            props = {}
        if reuse_calibration and (cal_dir / "prefill_profile.json").is_file():
            prefill, envelope = _load_prefill(cal_dir)
            token_delta_lo = envelope.get("lo")
            token_delta_hi = envelope.get("hi")
            cache_report = (
                json.loads((cal_dir / "cache_verification.json").read_text(encoding="utf-8"))
                if (cal_dir / "cache_verification.json").is_file()
                else {"passed": False, "note": "missing"}
            )
            decode = None
        else:
            prefill = calibrate_prefill(
                engine,
                n_grid=DEFAULT_PREFILL_GRID_CPU,
                reps=prefill_reps,
                out_dir=cal_dir,
                seed=7,
                max_ctx=2048,
                # Match trajectory duty cycle: chat-shaped prompts + decode work
                # so f(n) is not optimistically cold relative to corpus collection.
                measure_max_tokens=24,
                settle_s=0.15,
            )
            if not prefill.acceptance_passed():
                raise SystemExit(
                    "CPU prefill R² gate FAILED — treat as pipeline/load bug, not hardware. "
                    f"quadratic={prefill.quadratic} piecewise={prefill.piecewise}"
                )
            decode = calibrate_decode(
                engine,
                kv_depths=(0, 512, 1536),
                out_dir=cal_dir,
                seed=7,
            )
            cache_report = verify_cache_behavior(engine, prefill, out_dir=cal_dir, seed=7)
            if not cache_report.get("passed"):
                raise SystemExit(f"cache verification FAILED: {cache_report}")
            envelope = json.loads(
                (cal_dir / "token_reconciliation_envelope.json").read_text(encoding="utf-8")
            )
            token_delta_lo = envelope["lo"]
            token_delta_hi = envelope["hi"]
            (cal_dir / "engine_props.json").write_text(
                json.dumps({"props": props, "identity": identity.__dict__}, indent=2, sort_keys=True),
                encoding="utf-8",
            )

    grid_min, grid_max = domain_bounds(prefill)

    # Pilot one turn to estimate workload context bounds, then coverage-check.
    pilot_eng = engine if engine is not None else _mock_adapter(identity)
    pilot_events, _, _ = run_toy_trajectory(
        pilot_eng,  # type: ignore[arg-type]
        config=ToyAgentConfig(
            trajectory_id="pilot-coverage",
            n_turns=n_turns,
            max_tokens=24,
            f_prefill=prefill.predict_ms,
        ),
        bundle_dir=bundle_dir / "_pilot",
    )
    pilot_ns = [int(e.engine_tokens_in or 0) for e in pilot_events]
    coverage = assert_coverage_or_raise(
        prefill,
        expected_context_lo=min(pilot_ns),
        expected_context_hi=max(pilot_ns),
    )
    (out_dir / "coverage_check.json").write_text(
        json.dumps(coverage.__dict__, indent=2), encoding="utf-8"
    )
    # Cool down after pilot so corpus prefills are not thermally biased vs f(n).
    time.sleep(2.0)

    all_calls = []
    all_traj = []
    labeled_for_tax = []
    for i in range(n_trajectories):
        traj_id = f"cpu-dryrun-{i:03d}"
        eng = engine if engine is not None else _mock_adapter(identity)
        # Last trajectory uses variable max_tokens (D2).
        max_tokens = None if i == n_trajectories - 1 else 24
        events, bundle, bundle_path = run_toy_trajectory(
            eng,  # type: ignore[arg-type]
            config=ToyAgentConfig(
                trajectory_id=traj_id,
                n_turns=n_turns,
                max_tokens=max_tokens,
                f_prefill=prefill.predict_ms,
            ),
            bundle_dir=bundle_dir,
        )
        calls = derive_call_records(
            events,
            f_prefill=prefill.predict_ms,
            grid_min=grid_min,
            grid_max=grid_max,
            token_delta_lo=token_delta_lo,
            token_delta_hi=token_delta_hi,
        )
        traj = derive_trajectory_record(
            calls,
            workload_id="toy_agent_cpu_dryrun",
            cache_mode="cache-disabled",
            task_success=True,
            success_metric="toy_pass",
            replay_bundle_path=str(bundle_path),
            headline=True,
        )
        all_calls.extend(calls)
        all_traj.append(traj)
        labeled_for_tax.append([(c.step_type_semantic, c.step_features, "ok") for c in calls])
        traj_dir.mkdir(parents=True, exist_ok=True)
        (traj_dir / f"{traj_id}.events.json").write_text(
            json.dumps([e.__dict__ for e in events], default=str, indent=2),
            encoding="utf-8",
        )
        time.sleep(1.0)

    export_parquet(all_calls, all_traj, corpus_dir)
    tax = validate_taxonomy(labeled_for_tax, min_support=2)
    (out_dir / "d5_taxonomy_cpu_provisional.json").write_text(
        json.dumps(
            {
                "agreement_rate": tax.agreement_rate,
                "assigned_types": tax.assigned_types,
                "prefer_mined_for_layer1": tax.prefer_mined_for_layer1,
                "notes": tax.notes,
                "provisional": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    swap_results = []
    for traj in all_traj[:3]:
        assert traj.replay_bundle_path
        archived = load_bundle(Path(traj.replay_bundle_path))
        mock = MockEngine()
        result = swapped_step_replay(
            archived,
            swap_turn=max(1, archived.turns[-1].turn_index // 2),
            model_fn=mock.as_model_fn(fixed_output="swapped-cpu-dryrun"),
            model_id="swap-mock",
            reasoning_mode="on",
            tool_executor=lambda name, args, turn: turn.tool_results[0]
            if turn.tool_results
            else {"ok": True},
        )
        swap_results.append(
            {
                "trajectory_id": result.trajectory_id,
                "success": result.success,
                "swap_turn": result.swap_turn,
                "tool_replay_modes": result.tool_replay_modes,
            }
        )

    # Exit-criteria accounting (in-domain only for drift / residual).
    in_domain = [
        c
        for c in all_calls
        if grid_min <= c.engine_tokens_in <= grid_max
        and "attribution_out_of_domain" not in c.audit_flags
    ]
    drift = sum(1 for c in in_domain if "profile_drift" in c.audit_flags)
    neg = sum(1 for c in in_domain if "negative_prefill_residual" in c.audit_flags)
    anom = sum(1 for c in all_calls if "token_accounting_anomaly" in c.audit_flags)
    out_lens = {c.tokens_out for c in all_calls}

    report = {
        "phase": "P1",
        "provisional": True,
        "deployment_id": "CPU0",
        "prefill_acceptance_passed": prefill.acceptance_passed(),
        "cache_verification": cache_report,
        "coverage": coverage.__dict__,
        "grid_min": grid_min,
        "grid_max": grid_max,
        "n_trajectories": len(all_traj),
        "n_calls": len(all_calls),
        "n_in_domain": len(in_domain),
        "in_domain_profile_drift": drift,
        "in_domain_negative_residual": neg,
        "token_accounting_anomaly": anom,
        "tokens_out_unique": sorted(out_lens),
        "swap_results": swap_results,
        "all_swaps_ok": all(r["success"] for r in swap_results),
        "exit_criteria": {
            "r2": prefill.acceptance_passed(),
            "drift_le_2": drift <= 2,
            "zero_neg_residual": neg == 0,
            "zero_token_anomaly": anom == 0,
            "cache_passed": bool(cache_report.get("passed")),
            "zero_implausible_cold": not cache_report.get("implausible_flags"),
            "swaps_3": all(r["success"] for r in swap_results) and len(swap_results) >= 3,
            "variable_output_seen": len(out_lens) > 1,
        },
        "note": "CPU dry-run numbers are permanently provisional; never enter headline stats.",
    }
    if decode is not None:
        report["decode_points"] = len(decode.points)
    (out_dir / "cpu_dryrun_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    (corpus_dir / "corpus_metadata.json").write_text(
        json.dumps(
            {
                "provisional": True,
                "cell": "CPU0",
                "headline_eligible": False,
                "reason": "cpu_dryrun_plumbing_only",
                "grid_min": grid_min,
                "grid_max": grid_max,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ec = report["exit_criteria"]
    failures = [k for k, v in ec.items() if not v]
    if failures:
        raise SystemExit(f"P1 exit criteria FAILED: {failures} report={report}")
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TurnTrace v2 P1 CPU dry-run")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/turntrace_v2/cpu_dryrun"),
    )
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    p.add_argument("--n-trajectories", type=int, default=5)
    p.add_argument("--n-turns", type=int, default=6)
    p.add_argument("--prefill-reps", type=int, default=10)
    p.add_argument("--skip-live", action="store_true")
    p.add_argument("--reuse-calibration", action="store_true")
    args = p.parse_args(argv)
    report = run_cpu_dryrun(
        out_dir=args.out,
        base_url=args.base_url,
        n_trajectories=args.n_trajectories,
        n_turns=args.n_turns,
        prefill_reps=args.prefill_reps,
        skip_live=args.skip_live,
        reuse_calibration=args.reuse_calibration,
    )
    print(json.dumps({"ok": True, "report": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
