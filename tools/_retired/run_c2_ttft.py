"""C-2 TTFT-bound context limit — largest n with turn-1 prefill under 10 s SLO.

Detached payload for tools/launch_c2.ps1. Bisects n_cached in [8000, 12000]
per KV arm (gpu_only_f16, gpu_only_u8, gpu_only_u4) on int4 weights.

Pass criterion: median(prefill_s over 3 repeats) <= 10.0.
Also records decode_tok_s at every probe so the decode SLO crossing
(decode_tok_s < 6) can be located in the same sweep when it falls inside
the search range.

Predictions are written into plan.json before the first probe.
"""

from __future__ import annotations

import argparse
import atexit
import json
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARMS = ("gpu_only_f16", "gpu_only_u8", "gpu_only_u4")
DEFAULT_MODEL_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
LOW_DEFAULT = 8_000
HIGH_DEFAULT = 12_000
RESOLUTION = 250
REPEATS = 3
PREFILL_SLO_S = 10.0
DECODE_SLO_TOK_S = 6.0

# Sealed 41e419bd turn-1 medians (coarse grid) — cited in pre-registration only.
SEALED_41E_TURN1_PREFILL_MEDIAN = {
    "gpu_only_f16": {8000: 7.1832, 12000: 13.5377},
    "gpu_only_u8": {8000: 7.1326, 12000: 13.5273},
    "gpu_only_u4": {8000: 7.1324, 12000: 13.5001},
}

WATCHDOG_SCRIPT_BODY = r"""param([string]$LogPath, [int]$IntervalS)
$ErrorActionPreference = "Continue"
if ($IntervalS -lt 30) { $IntervalS = 30 }
while ($true) {
    Start-Sleep -Seconds $IntervalS
    $utc = (Get-Date).ToUniversalTime().ToString("o")
    $procs = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    if ($procs.Count -eq 0) {
        $rec = [ordered]@{ utc = $utc; event = "watchdog_poll"; n_found = 0; n_killed = 0 }
        Add-Content -LiteralPath $LogPath -Value (ConvertTo-Json -InputObject $rec -Compress)
        continue
    }
    $pids = @($procs | ForEach-Object { [int]$_.Id })
    $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $left = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    $rec = [ordered]@{
        utc            = $utc
        event          = "watchdog_kill"
        n_found        = $pids.Count
        pids_found     = $pids
        n_killed       = $pids.Count - $left.Count
        pids_remaining = @($left | ForEach-Object { [int]$_.Id })
    }
    Add-Content -LiteralPath $LogPath -Value (ConvertTo-Json -InputObject $rec -Compress -Depth 4)
}
"""


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _start_wsh_watchdog(session_dir: Path, interval_s: int) -> dict[str, Any] | None:
    if interval_s <= 0:
        return None
    session_dir.mkdir(parents=True, exist_ok=True)
    kill_log = session_dir / "watchdog_kills.jsonl"
    watch_script = session_dir / "_wsh_watchdog.ps1"
    watch_script.write_text(WATCHDOG_SCRIPT_BODY, encoding="utf-8")
    init: dict[str, Any] = {
        "utc": _utc(),
        "event": "watchdog_start_kill",
        "interval_s": interval_s,
        "pids_found": [],
        "n_killed": 0,
    }
    try:
        listed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                (
                    "$p=@(Get-Process -Name WorkloadsSessionHost -EA SilentlyContinue); "
                    "$ids=@($p | ForEach-Object { [int]$_.Id }); "
                    "if($p.Count -gt 0){$p|Stop-Process -Force -EA SilentlyContinue; "
                    "Start-Sleep -Seconds 1}; "
                    "$left=@(Get-Process -Name WorkloadsSessionHost -EA SilentlyContinue); "
                    "Write-Output (('ids=' + ($ids -join ',')) + '; left=' + $left.Count)"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        init["start_kill_stdout"] = (listed.stdout or "").strip()
    except Exception as exc:
        init["start_kill_error"] = f"{type(exc).__name__}: {exc}"
    with kill_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(init, sort_keys=True) + "\n")
    creationflags = 0x00000200 if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NoLogo",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(watch_script),
            "-LogPath",
            str(kill_log),
            "-IntervalS",
            str(int(interval_s)),
        ],
        cwd=str(session_dir),
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)
    alive = proc.poll() is None
    meta = {
        "pid": proc.pid,
        "interval_s": int(interval_s),
        "kill_log": str(kill_log),
        "mechanism": "Popen_CREATE_NEW_PROCESS_GROUP",
        "alive_after_1s": alive,
    }
    if not alive:
        meta["refuse"] = "watchdog_exited_within_1s"
    else:

        def _stop() -> None:
            try:
                proc.terminate()
            except Exception:
                pass

        atexit.register(_stop)
    return meta


def _pre_registered_predictions() -> dict[str, Any]:
    """Pre-registration written into plan.json before the first probe.

    Both the withdrawn ordering claim and its replacement stay in the record.
    """
    return {
        "source": ("docs/README_characterizations.md Finding 2 / sealed 41e419bd"),
        "amended_utc_note": (
            "PRE-DATA amendment before any C-2 probe: ordering claim withdrawn; "
            "replaced by turn-1 agreement within resolution."
        ),
        "sealed_41e419bd_turn1_prefill_median_s": SEALED_41E_TURN1_PREFILL_MEDIAN,
        "coarse_bracket": {
            "n_ok_side": 8000,
            "n_fail_side": 12000,
            "note": (
                "All three arms under SLO at 8000 (~7.1–7.2 s) and over at "
                "12000 (~13.5 s) on sealed turn-1 medians."
            ),
        },
        "withdrawn_prediction": {
            "status": "WITHDRAWN",
            "withdrawn_before_any_probe": True,
            "claim": (
                "TTFT-bound limit orders f16 > u8 >= u4. Prefill is "
                "compute-bound; quantized arms pay dequantization, so f16 "
                "reaches a higher n before crossing the 10 s SLO."
            ),
            "order": "f16 > u8 >= u4",
            "falsified_if_when_active": [
                "the three TTFT limits agree within the 250-token resolution",
                "u4 exceeds f16",
            ],
            "withdrawal_reason": (
                "That ordering was inferred from the 15–27% f16 advantage in "
                "41e419bd Finding 2, which is a TURN-2 DELTA PREFILL "
                "measurement. C-2 bisects on TURN-1 bulk prefill. Finding 2's "
                "direct statement about turn-1 is that arms agree within 1%."
            ),
        },
        "primary_prediction": {
            "status": "ACTIVE",
            "claim": (
                "The three turn-1 TTFT limits AGREE within the 250-token "
                "resolution. KV precision does not move the cold-start "
                "context limit."
            ),
            "order": "f16 ~= u8 ~= u4 (within +/- 250 tokens)",
            "falsified_if": [
                "any pair of TTFT limits differs by more than 250 tokens",
            ],
            "consequence_if_holds": (
                "KV precision affects neither capability (memory does not "
                "bind, C-1) nor the cold-start SLO limit. Its only remaining "
                "value on this hardware is the headroom it frees, which "
                "nothing needs. That makes it the weakest of the six axes on "
                "this machine, and it should be reported that way rather "
                "than on its nominal purpose."
            ),
        },
        "separate_experiment_not_c2": {
            "name": "turn2_delta_prefill_ttft_limit",
            "status": "NOT_STARTED",
            "displacing": True,
            "note": (
                "The turn-2 delta-prefill limit binds under RESIDENT and is "
                "where the 15–27% f16 advantage lives. At n=12,000 turn-2 was "
                "roughly 0.16 of turn-1, so its 10 s crossing sits well above "
                "12,000 and needs a wider search. There the ordering "
                "f16 > u8 >= u4 is still the prediction, and it matters more, "
                "because residency is the configuration the workload actually "
                "runs in. Recorded here so it is not silently folded into C-2."
            ),
            "prediction_if_run": "f16 > u8 >= u4",
        },
        "slo": {
            "prefill_s_max": PREFILL_SLO_S,
            "decode_tok_s_min": DECODE_SLO_TOK_S,
            "pass_uses_median_of_repeats": True,
            "repeats": REPEATS,
        },
        "record_note": ("Both withdrawn and replacement predictions stay in the record."),
    }


def _probe_metrics(result: dict[str, Any]) -> dict[str, Any]:
    gen = result.get("generation") or {}
    return {
        "outcome": result.get("outcome"),
        "completed": bool(result.get("completed")),
        "prefill_s": gen.get("prefill_s"),
        "decode_tok_s": gen.get("decode_tok_s"),
        "r_prefill_tok_s": gen.get("r_prefill_tok_s"),
        "wall_s": gen.get("wall_s"),
        "prompt_tokens_reported": gen.get("prompt_tokens_reported"),
        "peak_commit_bytes": gen.get("peak_commit_bytes"),
        "peak_rss_bytes": gen.get("peak_rss_bytes"),
        "available_mb_min": gen.get("available_mb_min"),
        "exception": result.get("exception"),
        "failure_mode": result.get("failure_mode"),
    }


def _probe_once(
    *,
    root: Path,
    cfg: dict[str, Any],
    arm: dict[str, Any],
    model_dir: str,
    p_cpus: list[int],
    work_dir: Path,
    prompt: dict[str, Any],
    n_tokens: int,
    repeat_i: int,
) -> dict[str, Any]:
    from seam.tools.ceiling_a import _child_spec_for_arm
    from seam.tools.delta_n import measured_repeat

    child_spec = _child_spec_for_arm(
        cfg=cfg,
        arm=arm,
        model_dir=model_dir,
        prompt=prompt,
        p_cpus=p_cpus,
    )
    tag = f"{arm['id']}.n{n_tokens}.r{repeat_i}"
    record = measured_repeat(
        root=root,
        cfg=cfg,
        p_cpus=p_cpus,
        work_dir=work_dir,
        child_spec=child_spec,
        label=f"c2/{arm['id']}/{n_tokens}/{repeat_i}",
        tag=tag,
    )
    result = record.get("result") or {}
    metrics = _probe_metrics(result)
    return {
        "arm_id": arm["id"],
        "n_tokens": n_tokens,
        "repeat_index": repeat_i,
        "admissible": record.get("admissible"),
        "started_utc": record.get("started_utc"),
        "ended_utc": record.get("ended_utc"),
        **metrics,
    }


def _summarize_probe(reps: list[dict[str, Any]]) -> dict[str, Any]:
    prefills = [r["prefill_s"] for r in reps if r.get("prefill_s") is not None]
    decodes = [r["decode_tok_s"] for r in reps if r.get("decode_tok_s") is not None]
    outcomes = [r.get("outcome") for r in reps]
    generate_ok = all(o == "pass" for o in outcomes) and len(outcomes) == len(reps)
    if len(prefills) != len(reps):
        slo_ok = False
        prefill_median = None
    else:
        prefill_median = float(statistics.median(prefills))
        slo_ok = generate_ok and prefill_median <= PREFILL_SLO_S
    decode_median = float(statistics.median(decodes)) if decodes else None
    return {
        "n_tokens": reps[0]["n_tokens"] if reps else None,
        "n_repeats": len(reps),
        "generate_ok": generate_ok,
        "slo_ok": slo_ok,
        "prefill_s_median": prefill_median,
        "prefill_s_min": min(prefills) if prefills else None,
        "prefill_s_max": max(prefills) if prefills else None,
        "decode_tok_s_median": decode_median,
        "decode_tok_s_min": min(decodes) if decodes else None,
        "decode_tok_s_max": max(decodes) if decodes else None,
        "decode_slo_ok": (decode_median is not None and decode_median >= DECODE_SLO_TOK_S),
        "repeats": reps,
    }


def bisect_arm(
    *,
    root: Path,
    cfg: dict[str, Any],
    arm: dict[str, Any],
    model_dir: str,
    p_cpus: list[int],
    work_dir: Path,
    prompt_cache: dict[int, dict[str, Any]],
    unit: str,
    low: int,
    high: int,
    resolution: int,
    repeats: int,
    probes_log: list[dict[str, Any]],
) -> dict[str, Any]:
    from transformers import AutoTokenizer

    from seam.tools.delta_n import prompt_for

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    lo, hi = int(low), int(high)
    probe_summaries: list[dict[str, Any]] = []

    def probe_n(n: int) -> dict[str, Any]:
        prompt = prompt_for(
            root=root, tokenizer=tokenizer, n_tokens=n, unit=unit, cache=prompt_cache
        )
        reps = []
        for r in range(repeats):
            print(
                f"[c2] probe arm={arm['id']} n={n} repeat={r}",
                flush=True,
            )
            rep = _probe_once(
                root=root,
                cfg=cfg,
                arm=arm,
                model_dir=model_dir,
                p_cpus=p_cpus,
                work_dir=work_dir,
                prompt=prompt,
                n_tokens=n,
                repeat_i=r,
            )
            reps.append(rep)
            probes_log.append(rep)
        summary = _summarize_probe(reps)
        # Drop bulky repeats from the arm-level summary list (full in probes_log).
        lean = {k: v for k, v in summary.items() if k != "repeats"}
        lean["pass"] = bool(summary["slo_ok"])
        probe_summaries.append(lean)
        print(
            f"[c2] summary arm={arm['id']} n={n} "
            f"prefill_med={summary['prefill_s_median']} "
            f"decode_med={summary['decode_tok_s_median']} "
            f"slo_ok={summary['slo_ok']}",
            flush=True,
        )
        return lean

    low_probe = probe_n(lo)
    if not low_probe["pass"]:
        return {
            "arm_id": arm["id"],
            "status": "REFUSED_LOW_OVER_SLO",
            "low": lo,
            "high": hi,
            "low_probe": low_probe,
            "probes": probe_summaries,
            "note": f"low={lo} median prefill not under {PREFILL_SLO_S}s SLO",
        }

    high_probe = probe_n(hi)
    if high_probe["pass"]:
        return {
            "arm_id": arm["id"],
            "status": "aborted",
            "abort_reason": "no_slo_crossing_in_range",
            "search": {"low_init": low, "high_init": high, "resolution": resolution},
            "ttft_limit_n": hi,
            "highest_slo_ok_n": hi,
            "first_slo_fail": None,
            "probes": probe_summaries,
            "note": (f"high={hi} still under {PREFILL_SLO_S}s SLO; " "no TTFT crossing in range."),
        }

    best_pass = lo
    first_fail: dict[str, Any] | None = high_probe
    while (hi - lo) > resolution:
        mid = (lo + hi) // 2
        mid = max(lo + 1, mid)
        if mid >= hi:
            break
        probe = probe_n(mid)
        if probe["pass"]:
            best_pass = mid
            lo = mid
        else:
            first_fail = probe
            hi = mid

    return {
        "arm_id": arm["id"],
        "status": "complete",
        "search": {"low_init": low, "high_init": high, "resolution": resolution},
        "ttft_limit_n": best_pass,
        "highest_slo_ok_n": best_pass,
        "first_slo_fail_n": (first_fail or {}).get("n_tokens"),
        "first_slo_fail": first_fail,
        "probes": probe_summaries,
    }


def _decode_crossing(arm_result: dict[str, Any]) -> dict[str, Any]:
    levels = []
    for p in arm_result.get("probes") or []:
        if p.get("decode_tok_s_median") is None:
            continue
        levels.append(
            {
                "n": p["n_tokens"],
                "decode_tok_s_median": p["decode_tok_s_median"],
                "ok": bool(p.get("decode_slo_ok")),
            }
        )
    levels.sort(key=lambda x: int(x["n"]))
    last_ok = None
    first_fail = None
    for L in levels:
        if L["ok"]:
            last_ok = L
            first_fail = None
        elif last_ok is not None and first_fail is None:
            first_fail = L
    if last_ok and first_fail:
        status = "bracketed"
    elif levels and all(L["ok"] for L in levels):
        status = "never_crossed_in_observed_range"
    elif levels and not any(L["ok"] for L in levels):
        status = "already_failed_at_lowest_observed"
    else:
        status = "insufficient_data"
    return {
        "metric": "decode_tok_s",
        "threshold": DECODE_SLO_TOK_S,
        "status": status,
        "n_ok_side": last_ok,
        "n_fail_side": first_fail,
        "levels": levels,
    }


def _eval_primary(arm_results: list[dict[str, Any]], resolution: int) -> dict[str, Any]:
    """Evaluate the ACTIVE primary prediction: limits agree within resolution."""
    limits: dict[str, int | None] = {}
    for r in arm_results:
        if r.get("status") != "complete":
            limits[r["arm_id"]] = None
            continue
        limits[r["arm_id"]] = int(r["ttft_limit_n"])
    f16, u8, u4 = (limits.get(a) for a in ARMS)
    if None in (f16, u8, u4):
        return {
            "evaluable": False,
            "limits": limits,
            "active_claim": "turn1_limits_agree_within_resolution",
            "reason": "one or more arms did not complete with a TTFT limit",
        }
    assert f16 is not None and u8 is not None and u4 is not None
    pairs = {
        "f16_u8": abs(f16 - u8),
        "f16_u4": abs(f16 - u4),
        "u8_u4": abs(u8 - u4),
    }
    span = max(f16, u8, u4) - min(f16, u8, u4)
    disagreeing = {k: v for k, v in pairs.items() if v > resolution}
    agree = len(disagreeing) == 0
    # Withdrawn ordering retained as forensic only (not the claim under test).
    withdrawn_order_holds = (f16 > u8) and (u8 >= u4)
    return {
        "evaluable": True,
        "active_claim": "turn1_limits_agree_within_resolution",
        "limits": limits,
        "pair_abs_diffs_tokens": pairs,
        "span_tokens": span,
        "agree_within_resolution": agree,
        "primary_prediction_held": agree,
        "falsified": not agree,
        "falsification_notes": (
            [
                f"pair {k} differs by {v} tokens (> {resolution})"
                for k, v in sorted(disagreeing.items())
            ]
            if disagreeing
            else []
        ),
        "withdrawn_ordering_forensic": {
            "order": "f16 > u8 >= u4",
            "held_on_this_data": withdrawn_order_holds,
            "note": "Not the active claim; retained because both versions stay in the record.",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model-spec", type=Path, default=DEFAULT_MODEL_SPEC)
    parser.add_argument("--low", type=int, default=LOW_DEFAULT)
    parser.add_argument("--high", type=int, default=HIGH_DEFAULT)
    parser.add_argument("--resolution", type=int, default=RESOLUTION)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--watchdog-interval-s", type=int, default=60)
    parser.add_argument("--arms", default=",".join(ARMS))
    args = parser.parse_args(argv)

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    model_spec = args.model_spec if args.model_spec.is_absolute() else ROOT / args.model_spec

    from seam.config import resolve_config
    from seam.model_provenance import load_local_spec
    from seam.tools.delta_n import _DELTA_N_PATH, _MEASUREMENT_PATH, _PLATFORM_PATH

    resolved = resolve_config(
        [ROOT / _PLATFORM_PATH, ROOT / _MEASUREMENT_PATH, ROOT / _DELTA_N_PATH],
        repo_root=ROOT,
    )
    cfg = resolved.data
    spec = load_local_spec(model_spec)
    model_dir = str(spec["ir_dir"])
    if not Path(model_dir).is_dir():
        raise SystemExit(f"REFUSED -- model IR missing: {model_dir}")
    if "arms" not in cfg:
        raise SystemExit("REFUSED -- resolved config missing arms")
    if "topology" not in cfg or "p_cpus" not in cfg["topology"]:
        raise SystemExit("REFUSED -- resolved config missing topology.p_cpus")
    arms_by_id = {a["id"]: a for a in cfg["arms"]}
    arm_ids = [a.strip() for a in str(args.arms).split(",") if a.strip()]
    for aid in arm_ids:
        if aid not in arms_by_id:
            raise SystemExit(f"REFUSED -- unknown arm {aid}")
        if aid == "gpu_only_f16":
            props = arms_by_id[aid].get("properties") or {}
            if str(props.get("KV_CACHE_PRECISION") or "").lower() != "f16":
                raise SystemExit(
                    "REFUSED -- gpu_only_f16 must request KV_CACHE_PRECISION=f16 " f"(got {props})"
                )

    predictions = _pre_registered_predictions()
    watch = _start_wsh_watchdog(out_dir, int(args.watchdog_interval_s))
    if watch and watch.get("refuse"):
        raise SystemExit(f"REFUSED -- {watch['refuse']}")

    plan = {
        "kind": "c2_ttft_bound_limit",
        "session_id": args.session_id,
        "started_utc": _utc(),
        "model_spec": str(model_spec),
        "ir_sha256": spec.get("ir_sha256"),
        "arms": arm_ids,
        "search": {
            "low": int(args.low),
            "high": int(args.high),
            "resolution_tokens": int(args.resolution),
            "repeats_per_probe": int(args.repeats),
            "criterion": (
                f"largest n with median(prefill_s) <= {PREFILL_SLO_S} "
                f"over {args.repeats} repeats"
            ),
            "also_record": "decode_tok_s per probe / median per n",
        },
        "pre_registered_predictions": predictions,
        "watchdog": watch,
        "status": "running",
    }
    # PRE-REGISTER: written before the first probe.
    (out_dir / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "event": "c2.plan_written",
                "session_id": args.session_id,
                "prediction_order": predictions["primary_prediction"]["order"],
                "withdrawn_order": predictions["withdrawn_prediction"]["order"],
                "active_claim": predictions["primary_prediction"]["claim"][:80],
            },
            sort_keys=True,
        ),
        flush=True,
    )

    p_cpus = [int(c) for c in cfg["topology"]["p_cpus"]]
    unit = str((cfg.get("ladder") or {}).get("filler_unit") or "")
    if not unit:
        raise SystemExit("REFUSED -- ladder.filler_unit missing")
    work_dir = out_dir / "work"
    work_dir.mkdir(exist_ok=True)
    prompt_cache: dict[int, dict[str, Any]] = {}
    probes_log: list[dict[str, Any]] = []
    arm_results: list[dict[str, Any]] = []

    for aid in arm_ids:
        print(f"[c2] BEGIN arm={aid}", flush=True)
        res = bisect_arm(
            root=ROOT,
            cfg=cfg,
            arm=arms_by_id[aid],
            model_dir=model_dir,
            p_cpus=p_cpus,
            work_dir=work_dir,
            prompt_cache=prompt_cache,
            unit=unit,
            low=int(args.low),
            high=int(args.high),
            resolution=int(args.resolution),
            repeats=int(args.repeats),
            probes_log=probes_log,
        )
        res["decode_crossing"] = _decode_crossing(res)
        arm_results.append(res)
        (out_dir / "probes.ndjson").write_text(
            "".join(json.dumps(p, sort_keys=True) + "\n" for p in probes_log),
            encoding="utf-8",
        )
        (out_dir / "arm_results.json").write_text(
            json.dumps(arm_results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    primary = _eval_primary(arm_results, int(args.resolution))
    aborted = [r for r in arm_results if r.get("status") == "aborted"]
    refused = [r for r in arm_results if str(r.get("status", "")).startswith("REFUSED")]
    if any(r.get("status") == "complete" for r in arm_results) and not aborted and not refused:
        session_status = "complete"
        abort_reason = None
    elif aborted and not any(r.get("status") == "complete" for r in arm_results):
        session_status = "aborted"
        abort_reason = aborted[0].get("abort_reason")
    elif refused and not any(r.get("status") == "complete" for r in arm_results):
        session_status = "refused"
        abort_reason = None
    else:
        session_status = "partial"
        abort_reason = aborted[0].get("abort_reason") if aborted else None

    summary = {
        "kind": "c2_ttft_bound_limit",
        "session_id": args.session_id,
        "ended_utc": _utc(),
        "status": session_status,
        "abort_reason": abort_reason,
        "pre_registered_predictions": predictions,
        "arm_results": arm_results,
        "primary_claim_eval": primary,
        "ttft_limits": {r["arm_id"]: r.get("ttft_limit_n") for r in arm_results},
        "decode_crossings": {r["arm_id"]: r.get("decode_crossing") for r in arm_results},
        "per_probe_medians": {
            r["arm_id"]: [
                {
                    "n": p["n_tokens"],
                    "prefill_s_median": p.get("prefill_s_median"),
                    "decode_tok_s_median": p.get("decode_tok_s_median"),
                    "slo_ok": p.get("pass") or p.get("slo_ok"),
                }
                for p in (r.get("probes") or [])
            ]
            for r in arm_results
        },
        "n_probes": len(probes_log),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    plan["status"] = session_status
    plan["abort_reason"] = abort_reason
    plan["ended_utc"] = summary["ended_utc"]
    plan["arm_results"] = arm_results
    plan["primary_claim_eval"] = primary
    (out_dir / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "ok": session_status == "complete",
                "status": session_status,
                "ttft_limits": summary["ttft_limits"],
                "primary_claim_eval": primary,
                "session_id": args.session_id,
                "out": str(out_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if session_status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
