def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--config-id", default=None)
    parser.add_argument("--platform", default="aipc-c1")
    parser.add_argument("--spec", type=Path, default=None)
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help=(
            "Override INFERENCE_NUM_THREADS for a child cell. Parent uses each "
            "MatrixConfig.inference_num_threads (A0a=8, A0b=4, A1-A6=4)."
        ),
    )
    parser.add_argument(
        "--blocks",
        type=int,
        default=_DEFAULT_BLOCKS,
        help=f"replicate blocks (default {_DEFAULT_BLOCKS}; use 1 for verification)",
    )
    parser.add_argument("--seed", type=int, default=20260803, help="shuffle seed (recorded)")
    parser.add_argument(
        "--cooldown-s",
        type=float,
        default=60.0,
        help="seconds between cells (default 60; longer than the invalid 30s matrix)",
    )
    parser.add_argument(
        "--allow-battery",
        action="store_true",
        help="OVERRIDE: run on battery (violates quiesce; do not use for publishable runs)",
    )
    parser.add_argument(
        "--allow-charging",
        action="store_true",
        help="OVERRIDE: allow charging!=false (violates ac-pinned charging-complete)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from out-stem.partial.json, skipping cells that already have generations",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        default=True,
        help="Permit dirty git tree for sealed manifest emit (recorded in manifest)",
    )
    args = parser.parse_args(argv)

    root = repo_root(Path(__file__).parent)
    spec_path = args.spec or (root / "configs" / "models" / "Qwen3-4B-int4-ov.yaml")

    if args.child:
        assert args.config_id is not None
        result = run_one(
            args.config_id, spec_path=spec_path, platform=args.platform, threads=args.threads
        )
        print(_RESULT_SENTINEL + json.dumps(result))
        return 0

    from seam.powerstate import (
        assert_profile,
        capture_battery_status_wmi,
        capture_power_state,
        is_charging_complete,
        raise_if_profile_mismatch,
    )

    forbidden_patterns = (
        "seam.tools.fetch_progress",
        "fetch_progress",
        "seam.tools.phase_e_cloud",
        "curl.exe",
        "wget",
        "TiWorker.exe",
        "UsoClient.exe",
        "OneDrive.exe",
        "MsMpEng.exe",
    )
    hard_refuse_patterns = (
        "seam.tools.fetch_progress",
        "fetch_progress",
        "seam.tools.phase_e_cloud",
        "curl.exe",
    )
    forbidden_hits = check_forbidden_processes(forbidden_patterns)
    hard_hits = [h for h in forbidden_hits if h["pattern"] in hard_refuse_patterns]
    if hard_hits:
        print("REFUSED: forbidden processes running:", json.dumps(hard_hits, indent=2))
        return 2

    platform_cfg = load_platform_config(args.platform, repo_root=root)
    power_cfg = platform_cfg.get("power") or {}
    ac_profile = (power_cfg.get("profiles") or {}).get("ac-pinned") or {}
    brightness_target = ac_profile.get("display_brightness_pct")
    charge_rate_max = ac_profile.get("charge_rate_max_mw")
    soc_complete = ac_profile.get("charging_complete_soc_pct")

    power = capture_power_state()
    batt_wmi = capture_battery_status_wmi()
    if power.on_battery and not args.allow_battery:
        print(
            "REFUSED: AC not connected (on_battery=True, "
            f"battery_pct={power.battery_pct}, charging={power.charging}). "
            "Quiesce requires AC. Plug in and re-run. This is a gate, not a suggestion."
        )
        refuse_path = root / "derived" / "mslice" / "affinity_matrix_refused_ac.json"
        refuse_path.parent.mkdir(parents=True, exist_ok=True)
        refuse_path.write_text(
            json.dumps(
                {
                    "refused": True,
                    "reason": "ac_not_connected",
                    "quiesce": {
                        "on_battery": power.on_battery,
                        "battery_pct": power.battery_pct,
                        "charging": power.charging,
                        "power_plan_name": power.power_plan_name,
                        "power_plan_guid": power.power_plan_guid,
                        "battery_status_wmi": batt_wmi.__dict__,
                    },
                    "thermal": {"regime": "confound"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {refuse_path}")
        return 3

    complete, complete_reason = is_charging_complete(
        power,
        batt_wmi,
        charge_rate_max_mw=float(charge_rate_max) if charge_rate_max is not None else None,
        charging_complete_soc_pct=float(soc_complete) if soc_complete is not None else None,
    )
    if not complete and not args.allow_charging:
        print(
            "REFUSED: ac-pinned requires charging complete. "
            f"reason={complete_reason}. Do NOT measure while charging. STOP."
        )
        refuse_path = root / "derived" / "mslice" / "affinity_matrix_refused_charging.json"
        refuse_path.parent.mkdir(parents=True, exist_ok=True)
        refuse_path.write_text(
            json.dumps(
                {
                    "refused": True,
                    "reason": "charging_not_complete",
                    "detail": complete_reason,
                    "quiesce": {
                        "on_battery": power.on_battery,
                        "battery_pct": power.battery_pct,
                        "charging": power.charging,
                        "battery_status_wmi": batt_wmi.__dict__,
                    },
                    "thermal": {"regime": "confound"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {refuse_path}")
        return 5

    profile_assertion = assert_profile("affinity_matrix", power, power_cfg=power_cfg)
    if profile_assertion.deviations and not args.allow_charging:
        print("REFUSED: ac-pinned profile mismatch:", profile_assertion.deviations)
        try:
            raise_if_profile_mismatch(profile_assertion)
        except Exception as exc:
            print(str(exc))
        return 5

    brightness_set = _set_display_brightness(
        int(brightness_target) if brightness_target is not None else None
    )
    quiesce_extra = _capture_quiesce_extras()
    quiesce_extra["display_brightness_target"] = brightness_target
    quiesce_extra["display_brightness_set"] = brightness_set
    quiesce_extra["display_brightness"] = brightness_set.get(
        "actual", quiesce_extra.get("display_brightness")
    )
    quiesce_extra["charging_complete"] = complete
    quiesce_extra["charging_complete_reason"] = complete_reason
    quiesce_extra["battery_status_wmi"] = {
        "charging": batt_wmi.charging,
        "discharging": batt_wmi.discharging,
        "charge_rate_mw": batt_wmi.charge_rate_mw,
        "discharge_rate_mw": batt_wmi.discharge_rate_mw,
        "remaining_capacity_mwh": batt_wmi.remaining_capacity_mwh,
        "voltage_mv": batt_wmi.voltage_mv,
        "power_online": batt_wmi.power_online,
    }

    all_cpus = set(_expected_cpus(CONFIGS["A0a"], platform_cfg))
    blocks, seed = schedule_blocks(list(CONFIGS), n_blocks=args.blocks, seed=args.seed)

    report: dict[str, Any] = {
        "spec_path": spec_path.as_posix(),
        "platform": args.platform,
        "config_threads": {cid: c.inference_num_threads for cid, c in CONFIGS.items()},
        "blocks": args.blocks,
        "shuffle_seed": seed,
        "schedule": blocks,
        "cooldown_s": args.cooldown_s,
        "min_phase_samples_declared": _MIN_PHASE_SAMPLES,
        "thermal": {
            "regime": "confound",
            "cooldown_mode": "time_based_unvalidated",
            "note": (
                "Cooldown is time-based; without a temperature ceiling it is unvalidated. "
                "Throttle detection uses frequency (PDH), within-cell drift, and block-position "
                "regression — not package temperature."
            ),
        },
        "quiesce": {
            "pinned_profile": "ac-pinned",
            "on_battery": power.on_battery,
            "battery_pct_start": power.battery_pct,
            "charging": power.charging,
            "charging_complete": complete,
            "charging_complete_reason": complete_reason,
            "power_source": "battery" if power.on_battery else "mains",
            "power_plan_name": power.power_plan_name,
            "power_plan_guid": power.power_plan_guid,
            "overlay_guid": power.overlay_guid,
            "battery_saver": power.battery_saver,
            **quiesce_extra,
        },
        "forbidden_process_check": {
            "patterns": list(forbidden_patterns),
            "hits": forbidden_hits,
            "hard_refuse_hits": hard_hits,
        },
        "runs": {cid: [] for cid in CONFIGS},
        "summary": {},
    }

    out_path = args.out or (root / "derived" / "mslice" / "affinity_matrix.json")
    checkpoint_path = out_path.with_name(out_path.stem + ".partial.json")

    skip_cells: set[tuple[int, str]] = set()
    if args.resume:
        if not checkpoint_path.exists():
            print(f"REFUSED: --resume but checkpoint missing: {checkpoint_path}")
            return 2
        prior = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        for key in ("blocks", "shuffle_seed", "schedule", "config_threads"):
            if prior.get(key) != report.get(key):
                print(
                    f"REFUSED: --resume mismatch on {key}: "
                    f"checkpoint={prior.get(key)!r} current={report.get(key)!r}"
                )
                return 2
        report["runs"] = prior.get("runs") or report["runs"]
        report["resumed_from"] = checkpoint_path.as_posix()
        skip_cells = _completed_cells(report["runs"])
        print(f"Resuming: {len(skip_cells)} cells already scored; skipping those.")
        report.pop("interrupted", None)

    awake_flags = _keep_awake_windows()
    if awake_flags is not None:
        report["quiesce"]["keep_awake"] = "SetThreadExecutionState(SYSTEM|AWAYMODE)"
        print("keep-awake: SetThreadExecutionState SYSTEM_REQUIRED|AWAYMODE_REQUIRED")

    interrupted: dict[str, Any] | None = None
    try:
        for block_index, block in enumerate(blocks):
            print(f"\n=== block {block_index + 1}/{len(blocks)} ===")
            for cell_index, config_id in enumerate(block):
                if (block_index, config_id) in skip_cells:
                    print(f"\n--- {config_id}: skip (checkpoint) ---")
                    continue
                power_now = capture_power_state()
                batt_now = capture_battery_status_wmi()
                if power_now.on_battery and not args.allow_battery:
                    interrupted = {
                        "reason": "ac_lost_mid_matrix",
                        "at_block": block_index,
                        "at_cell": config_id,
                        "battery_pct": power_now.battery_pct,
                        "charging": power_now.charging,
                    }
                    print(
                        "REFUSED mid-matrix: AC lost "
                        f"(block {block_index + 1}, next cell {config_id}, "
                        f"battery_pct={power_now.battery_pct}). Checkpoint preserved. STOP."
                    )
                    break
                still_complete, still_reason = is_charging_complete(
                    power_now,
                    batt_now,
                    charge_rate_max_mw=(
                        float(charge_rate_max) if charge_rate_max is not None else None
                    ),
                    charging_complete_soc_pct=(
                        float(soc_complete) if soc_complete is not None else None
                    ),
                )
                if not still_complete and not args.allow_charging:
                    interrupted = {
                        "reason": "charging_resumed_mid_matrix",
                        "at_block": block_index,
                        "at_cell": config_id,
                        "detail": still_reason,
                        "battery_pct": power_now.battery_pct,
                        "charging": power_now.charging,
                        "charge_rate_mw": batt_now.charge_rate_mw,
                    }
                    print(
                        "ABORT mid-matrix: charging resumed "
                        f"(block {block_index + 1}, next cell {config_id}, "
                        f"{still_reason}). Checkpoint preserved. STOP."
                    )
                    break
                cfg = CONFIGS[config_id]
                print(
                    f"\n--- {config_id}: {cfg.description} "
                    f"(threads={cfg.inference_num_threads}) ---"
                )
                outcome = _spawn(config_id, spec_path=spec_path, platform=args.platform)
                outcome["block"] = block_index
                outcome["cell_index"] = cell_index
                report["runs"][config_id].append(outcome)
                cell_ok = _run_is_ok(outcome)
                gens = outcome.get("generations") or []
                decode = gens[-1].get("r_decode_tok_s") if gens else None
                n_pref = gens[-1].get("n_prefill_util_samples") if gens else None
                print(f"  ok={cell_ok} decode_tok_s={decode} n_prefill_samples={n_pref}")
                if outcome.get("error"):
                    print(f"  ERROR: {outcome['error']}")
                    if outcome.get("returncode") in (4294967295, -1):
                        interrupted = {
                            "reason": "child_killed",
                            "at_block": block_index,
                            "at_cell": config_id,
                            "returncode": outcome.get("returncode"),
                            "stderr_tail": outcome.get("stderr"),
                        }
                        print("Child killed (likely OOM/sleep/AC). Checkpointing and STOP.")
                        _write_checkpoint(checkpoint_path, report)
                        break
                _write_checkpoint(checkpoint_path, report)
                if cell_index < len(block) - 1 or block_index < len(blocks) - 1:
                    print(f"  cooldown {args.cooldown_s}s …")
                    time.sleep(args.cooldown_s)
            if interrupted:
                break

        if interrupted:
            report["interrupted"] = interrupted
            report["quiesce"]["battery_pct_end"] = capture_power_state().battery_pct
            _write_checkpoint(checkpoint_path, report)
            refuse_path = out_path.with_name(out_path.stem + "_interrupted.json")
            refuse_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"wrote interrupted artifact {refuse_path}")
            print(f"wrote checkpoint {checkpoint_path}")
            return 4
    finally:
        _release_awake_windows(awake_flags)

    pooled = _pool_baselines(report["runs"])
    noise_band = compute_noise_band(pooled)
    a0a_ok = [r for r in report["runs"].get("A0a", []) if _run_is_ok(r)]
    a0a_decode = _aggregate_deltas(a0a_ok, "decode_delta_pct_per_cpu")
    loaded_thr = global_loaded_threshold_from_a0a(a0a_decode)
    report["noise_band"] = {
        "value": round(noise_band, 4),
        "formula": "2 * mean(per-core CV of pooled idle baseline means)",
        "pooled_baseline_n_per_core": {str(k): len(v) for k, v in pooled.items()},
    }
    report["loaded_threshold"] = {
        "value": round(loaded_thr, 4),
        "formula": "0.5 * median(A0a per-core decode delta)",
        "a0a_decode_delta_pct_per_cpu": {
            str(k): round(v, 4) for k, v in sorted(a0a_decode.items())
        },
        "applied_to": "every cell, both prefill and decode",
    }

    for config_id in CONFIGS:
        report["summary"][config_id] = _summarize_cell(
            config_id,
            report["runs"][config_id],
            noise_band=noise_band,
            all_cpus=all_cpus,
            platform_cfg=platform_cfg,
            loaded_threshold_value=loaded_thr,
        )

    report["decision"] = _mechanism_decision(report["summary"])
    report["throttle_detectors"] = _throttle_detectors(report)
    power_end = capture_power_state()
    batt_end = capture_battery_status_wmi()
    report["quiesce"]["battery_pct_end"] = power_end.battery_pct
    report["quiesce"]["charging_end"] = power_end.charging
    report["quiesce"]["battery_status_wmi_end"] = {
        "charging": batt_end.charging,
        "charge_rate_mw": batt_end.charge_rate_mw,
    }

    a0a_diag = report["summary"].get("A0a", {}).get("reference_diagnostics") or {}
    report["decision"]["a0a_diagnostics"] = a0a_diag
    report["decision"]["a0b_diagnostics"] = (
        report["summary"].get("A0b", {}).get("reference_diagnostics") or {}
    )

    verification = _verification_gates(report, min_phase_samples=_MIN_PHASE_SAMPLES)
    report["verification_gates"] = verification

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if checkpoint_path.exists():
        checkpoint_path.unlink()

    run_id = _emit_matrix_manifest(
        report=report,
        out_path=out_path,
        platform_cfg=platform_cfg,
        root=root,
        allow_dirty=bool(args.allow_dirty),
        seed=seed,
        n_blocks=args.blocks,
    )
    report["run_id"] = run_id
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== summary ===")
    for config_id, summ in report["summary"].items():
        cls = summ.get("classification") or {}
        print(
            f"  {config_id}: verdict={cls.get('verdict')} "
            f"prefill={cls.get('prefill')} decode={cls.get('decode')} "
            f"decode_mean={summ.get('r_decode_tok_s_mean')}"
        )
    print(f"\nLOADED_THRESHOLD={report['loaded_threshold']['value']}")
    print(f"NOISE_BAND={report['noise_band']['value']}")
    print(f"adopted mechanism: {report['decision']['adopted_mechanism']}")
    print(f"reason: {report['decision']['reason']}")
    print(f"mechanism effect (A3 vs A6): {report['decision']['mechanism_effect']}")
    print(f"throttle_detectors: {report['throttle_detectors']}")
    print(f"verification_gates: {verification}")
    print(f"run_id={run_id}")
    print(f"wrote {out_path}")
    if not verification.get("pass"):
        print("VERIFICATION GATES FAILED — STOP. Do not proceed to full matrix / adoption.")
        return 6
    return 0 if report["decision"]["adopted_mechanism"] != "none" else 1


def _set_display_brightness(target_pct: int | None) -> dict[str, Any]:
    """Set display brightness to the pinned target; record target and actual."""
    out: dict[str, Any] = {"target": target_pct, "actual": None, "ok": False}
    if target_pct is None:
        out["error"] = "no_target_declared"
        return out
    try:
        import subprocess as sp

        script = (
            f"$m = Get-CimInstance -Namespace root/WMI -ClassName "
            f"WmiMonitorBrightnessMethods | Select-Object -First 1; "
            f"Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness "
            f"-Arguments @{{Timeout=1; Brightness={int(target_pct)}}} | Out-Null; "
            f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness "
            f"| Select-Object -First 1).CurrentBrightness"
        )
        completed = sp.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            out["actual"] = float(completed.stdout.strip())
            out["ok"] = abs(out["actual"] - float(target_pct)) <= 1.0
        else:
            out["error"] = (completed.stderr or completed.stdout or "set_failed")[-500:]
    except Exception as exc:
        out["error"] = type(exc).__name__
    return out


def _capture_quiesce_extras() -> dict[str, Any]:
    """Brightness, Defender realtime, ambient — record by value; null when unavailable."""
    out: dict[str, Any] = {
        "display_brightness": None,
        "defender_realtime": None,
        "ambient_c": None,
        "ambient_method": None,
    }
    try:
        import subprocess as sp

        bright = sp.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness "
                "| Select-Object -First 1 -ExpandProperty CurrentBrightness)",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if bright.returncode == 0 and bright.stdout.strip():
            out["display_brightness"] = float(bright.stdout.strip())
    except Exception as exc:
        out["display_brightness_error"] = type(exc).__name__

    try:
        import subprocess as sp

        def_rt = sp.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-MpPreference).DisableRealtimeMonitoring",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if def_rt.returncode == 0 and def_rt.stdout.strip():
            disabled = def_rt.stdout.strip().lower() in {"true", "1"}
            out["defender_realtime"] = "disabled" if disabled else "enabled"
    except Exception as exc:
        out["defender_realtime_error"] = type(exc).__name__

    out["ambient_c"] = None
    out["ambient_method"] = "unavailable_pending_M2.3_LHM"
    out["package_temp_c"] = None
    out["throttle_detection"] = "frequency_based_authorized"
    return out


def _verification_gates(report: dict[str, Any], *, min_phase_samples: int) -> dict[str, Any]:
    """Part-2 gates. Failure is STOP — never descope."""
    failures: list[str] = []
    prefill_ok = True
    for cid, runs in (report.get("runs") or {}).items():
        for run in runs:
            if not _run_is_ok(run):
                prefill_ok = False
                failures.append(f"{cid}/block{run.get('block')}: run not ok")
                continue
            for gen in run.get("generations") or []:
                n_p = int(gen.get("n_prefill_util_samples") or 0)
                n_d = int(gen.get("n_decode_util_samples") or 0)
                if n_p < min_phase_samples or n_d < min_phase_samples:
                    prefill_ok = False
                    failures.append(
                        f"{cid}/block{run.get('block')}/gen{gen.get('gen_index')}: "
                        f"n_prefill={n_p} n_decode={n_d} < {min_phase_samples}"
                    )
                pref_delta = gen.get("prefill_delta_pct_per_cpu") or []
                # Prefill deltas on loaded cores should be positive for saturated work.
                if pref_delta and max(float(v) for v in pref_delta) <= 0:
                    failures.append(
                        f"{cid}/block{run.get('block')}/gen{gen.get('gen_index')}: "
                        "prefill deltas all non-positive"
                    )

    a0a = (report.get("summary") or {}).get("A0a", {}).get("reference_diagnostics") or {}
    a0a_loaded = int(a0a.get("loaded_core_count") or 0)
    if a0a_loaded <= 4:
        failures.append(f"A0a loaded_core_count={a0a_loaded} (need substantially >4)")

    quiesce = report.get("quiesce") or {}
    if quiesce.get("charging") is True or quiesce.get("charging_end") is True:
        failures.append("charging true during block")
    if not quiesce.get("charging_complete", False):
        failures.append("charging_complete false at start")

    lt = (report.get("loaded_threshold") or {}).get("value")
    nb = (report.get("noise_band") or {}).get("value")
    if lt is None:
        failures.append("LOADED_THRESHOLD missing")
    if nb is None:
        failures.append("NOISE_BAND missing")

    run_id = report.get("run_id")
    # run_id may be filled after this function; sealed check is separate.
    return {
        "pass": not failures,
        "failures": failures,
        "prefill_windows_ok": prefill_ok,
        "a0a_loaded_core_count": a0a_loaded,
        "loaded_threshold": lt,
        "noise_band": nb,
        "charging_complete": quiesce.get("charging_complete"),
        "min_phase_samples": min_phase_samples,
        "run_id_present_at_gate": bool(run_id),
    }


def _emit_matrix_manifest(
    *,
    report: dict[str, Any],
    out_path: Path,
    platform_cfg: Any,
    root: Path,
    allow_dirty: bool,
    seed: int,
    n_blocks: int,
) -> str:
    """Emit a sealed ``raw/<run_id>/`` manifest for the matrix / verification run."""
    from seam.manifest import emit
    from seam.model_provenance import load_local_spec, quantization_summary
    from seam.powerstate import manifest_power_state, capture_power_state

    spec = load_local_spec(Path(report["spec_path"]))
    power = capture_power_state()
    quiesce = report.get("quiesce") or {}

    def _write_outputs(run_dir: Any) -> dict[str, Any]:
        # Copy the derived report into the sealed run so raw_sha256 covers it.
        dest = run_dir.path / "affinity_matrix.json"
        dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {
            "n_blocks": n_blocks,
            "n_configs": len(CONFIGS),
            "shuffle_seed": seed,
            "loaded_threshold": report.get("loaded_threshold"),
            "noise_band": report.get("noise_band"),
            "adopted_mechanism": (report.get("decision") or {}).get("adopted_mechanism"),
            "verification_gates": report.get("verification_gates"),
            "derived_path": out_path.as_posix(),
        }

    handle = emit(
        config=platform_cfg,
        target="cpu-p",
        workload={
            "kind": "mslice_affinity_matrix",
            "benchmark": "a0a_a0b_a1_a6_confinement_matrix",
            "task_ids": list(CONFIGS),
            "seed": seed,
            "n_repeats": n_blocks,
        },
        condition_label="mslice_affinity_matrix_ac_pinned",
        repo_root=root,
        allow_dirty=allow_dirty,
        summary={
            "matrix_cells": list(CONFIGS),
            "cooldown_s": report.get("cooldown_s"),
            "thermal_regime": "confound",
            "decision": report.get("decision"),
        },
        model={
            "name": spec.get("name"),
            "revision": spec.get("revision"),
            "quantization": quantization_summary(spec),
            "ir_sha256": (spec.get("files") or {}).get("openvino_model.bin", {}).get("sha256"),
            "reasoning_mode": "off",
            "provenance": {
                "kind": "local_openvino_ir",
                "self_converted": spec.get("self_converted"),
                "source_repo": spec.get("source_repo"),
                "download_method": spec.get("download_method"),
                "export_command": None,
                "quantization_config": spec.get("quantization"),
                "ladder_position": None,
                "spec_path": report.get("spec_path"),
                "spec_sha256": None,
                "file_verification": spec.get("file_verification"),
            },
        },
        power_state=manifest_power_state(
            power,
            battery_pct_end=quiesce.get("battery_pct_end"),
            display_brightness=quiesce.get("display_brightness"),
            defender_realtime=quiesce.get("defender_realtime"),
        ),
        thermal={"regime": "confound", "excluded": False},
        before_integrity_hash=_write_outputs,
        self_check="pass" if (report.get("verification_gates") or {}).get("pass") else "fail",
    )
    return handle.run_id


def _throttle_detectors(report: dict[str, Any]) -> dict[str, Any]:
    """Three detectors: (a) PDH frequency, (b) within-cell gen1 vs gen2, (c) block-position."""
    freq_methods: set[str] = set()
    freq_min_pct: list[float] = []
    within_cell: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []

    for cid, runs in (report.get("runs") or {}).items():
        for run in runs:
            for gen in run.get("generations") or []:
                freq = (gen.get("sampler_overhead") or {}).get("frequency") or {}
                method = freq.get("method")
                if method:
                    freq_methods.add(str(method))
                summary = freq.get("summary") or {}
                for v in summary.get("min_pct_of_max_per_cpu") or []:
                    if isinstance(v, (int, float)):
                        freq_min_pct.append(float(v))
            gens = run.get("generations") or []
            if len(gens) >= 2:
                g1 = gens[0].get("r_decode_tok_s")
                g2 = gens[1].get("r_decode_tok_s")
                if g1 and g2:
                    drift = (float(g2) - float(g1)) / float(g1)
                    within_cell.append(
                        {
                            "config_id": cid,
                            "block": run.get("block"),
                            "decode_rel_drift_g2_vs_g1": round(drift, 4),
                        }
                    )
            if gens and run.get("block") is not None:
                block_rows.append(
                    {
                        "config_id": cid,
                        "block": int(run["block"]),
                        "decode_tok_s": statistics.fmean(
                            float(g["r_decode_tok_s"])
                            for g in gens
                            if g.get("r_decode_tok_s") is not None
                        ),
                    }
                )

    slope = None
    if len(block_rows) >= 4:
        xs = [r["block"] for r in block_rows]
        ys = [r["decode_tok_s"] for r in block_rows]
        x_mean = statistics.fmean(xs)
        y_mean = statistics.fmean(ys)
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
        den = sum((x - x_mean) ** 2 for x in xs)
        slope = (num / den) if den else None

    flagged = []
    if freq_min_pct and min(freq_min_pct) < 80.0:
        flagged.append("frequency_dip_below_80pct_of_max")
    large_drift = [d for d in within_cell if abs(d["decode_rel_drift_g2_vs_g1"]) > 0.15]
    if large_drift:
        flagged.append("within_cell_decode_drift_gt_15pct")
    if slope is not None and abs(slope) > 0.5:
        flagged.append("block_position_slope_gt_0.5_tok_s_per_block")

    return {
        "a_pdh_frequency": {
            "methods_seen": sorted(freq_methods),
            "n_min_pct_observations": len(freq_min_pct),
            "global_min_pct_of_max": min(freq_min_pct) if freq_min_pct else None,
        },
        "b_within_cell_drift": {
            "n_pairs": len(within_cell),
            "pairs": within_cell,
            "n_flagged_gt_15pct": len(large_drift),
        },
        "c_block_position": {
            "n_rows": len(block_rows),
            "slope_decode_tok_s_per_block": slope,
        },
        "flagged": flagged,
        "excluded_cells": [],
        "note": (
            "Cooldown is time-based and unvalidated without a temperature ceiling. "
            "Flagged cells are recorded; exclusion requires operator confirmation."
        ),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
