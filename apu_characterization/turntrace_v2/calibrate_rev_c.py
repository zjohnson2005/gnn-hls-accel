"""C-P2 local calibration against the pinned ≥16K CPU model lock."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from apu_characterization.turntrace_v2.calibrate_live import calibrate_prefill
from apu_characterization.turntrace_v2.cpu_dryrun import wait_for_server
from apu_characterization.turntrace_v2.engines import EngineIdentity
from apu_characterization.turntrace_v2.engines.llamacpp import LlamaCppServerEngine
from apu_characterization.turntrace_v2.model_lock import assert_model_lock

# Suite-domain grid: cpu_prebox through TT-DOC box target. Points above the
# server n_ctx (minus decode headroom) are skipped by calibrate_prefill.
REV_C_PREFILL_GRID = (1024, 2048, 4096, 8192, 12288, 16384, 20480)
REV_C_PREFILL_REPS = 5
R2_GATE = 0.99
# calibrate_prefill keeps n <= max_ctx - 64; pass headroom so 16384 is kept.
CALIBRATE_MAX_CTX_HEADROOM = 64


def run_rev_c_calibration(
    *,
    out_dir: Path,
    base_url: str = "http://127.0.0.1:8080",
    reps: int = REV_C_PREFILL_REPS,
    n_grid: tuple[int, ...] = REV_C_PREFILL_GRID,
    settle_s: float = 1.0,
    measure_max_tokens: int = 24,
) -> dict:
    lock = assert_model_lock(require_file=True)
    wait_for_server(base_url)
    n_ctx = int(lock["n_ctx_pinned"])
    identity = EngineIdentity(
        deployment_id="CPU0",
        model_id=str(lock["model_id"]),
        quantization=str(lock["quantization"]),
        engine=str(lock["engine"]),
        engine_version=str(lock["engine_version"]),
        hardware="cpu-host",
        reasoning_mode="off",
        provisional=True,
    )
    engine = LlamaCppServerEngine(base_url=base_url, identity=identity)
    if engine.should_remap_unsupported_roles():
        raise RuntimeError(
            "pinned rev C model must not enable TinyLlama tool→user remap"
        )
    props = {}
    try:
        props = engine.props()
    except Exception:
        props = {}
    observed_ctx = int(
        ((props.get("default_generation_settings") or {}).get("n_ctx")) or 0
    )
    if observed_ctx and observed_ctx < 16384:
        raise RuntimeError(
            f"llama-server n_ctx={observed_ctx} is below the rev C ≥16K pin"
        )
    # Prefer observed server ctx so 16K grid points survive the -64 filter.
    effective_max_ctx = max(n_ctx, observed_ctx or n_ctx) + CALIBRATE_MAX_CTX_HEADROOM

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = calibrate_prefill(
        engine,
        n_grid=n_grid,
        reps=reps,
        out_dir=out_dir,
        r2_gate=R2_GATE,
        seed=11,
        max_ctx=effective_max_ctx,
        measure_max_tokens=measure_max_tokens,
        settle_s=settle_s,
    )
    if not profile.acceptance_passed():
        raise SystemExit(
            "C-P2 prefill R² gate FAILED — investigate thermal/memory/load; "
            f"do not lower the bar. quadratic={profile.quadratic} "
            f"piecewise={profile.piecewise}"
        )
    if not profile.quadratic or not profile.quadratic.passed_r2_gate:
        raise SystemExit(
            "C-P2 requires the quadratic f(n) fit to pass R²≥0.99 so the "
            "conservative intercept booking can feed wall_budget.py"
        )

    profile_path = out_dir / "prefill_profile.json"
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    payload["model_lock_sha256"] = hashlib.sha256(
        Path(__file__)
        .resolve()
        .with_name("model_lock_rev_c.json")
        .read_bytes()
    ).hexdigest()
    payload["model_file_sha256"] = str(lock["sha256"])
    payload["n_ctx_pinned"] = n_ctx
    payload["observed_server_n_ctx"] = observed_ctx or None
    payload["grid_requested_rev_c"] = list(n_grid)
    payload["r2_gate"] = R2_GATE
    payload["conservative_intercept_booking"] = (
        "quadratic intercept books as necessary prefill (against the thesis)"
    )
    profile_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    report = {
        "validity": "debug_only",
        "provisional": True,
        "acceptance_passed": True,
        "quadratic_r2_held_out": profile.quadratic.r2_held_out,
        "piecewise_r2_held_out": (
            profile.piecewise.r2_held_out if profile.piecewise else None
        ),
        "grid_min": min(n for n, _ in profile.points),
        "grid_max": max(n for n, _ in profile.points),
        "n_points": len(profile.points),
        "model_id": identity.model_id,
        "quantization": identity.quantization,
        "model_file_sha256": lock["sha256"],
        "n_ctx_pinned": n_ctx,
        "prefill_profile": str(profile_path),
        "note": "CPU calibration is provisional forever; never headline.",
    }
    (out_dir / "calibrate_rev_c_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--reps", type=int, default=REV_C_PREFILL_REPS)
    args = parser.parse_args(argv)
    report = run_rev_c_calibration(
        out_dir=args.out, base_url=args.base_url, reps=args.reps
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
