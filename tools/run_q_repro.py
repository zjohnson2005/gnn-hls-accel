"""Q-REPRO: does W-3 quality reproduce under KV-unset vs pinned f16?

Arms (interleaved, 200 entries each, local only):
  A gpu_only      — KV unset / dynamic (exact W-3 config)
  B gpu_only_f16  — KV f16 pinned (Q-KV control)

Arm A: log KV readback every cell. Predictions must exist in
derived/q_repro/Q_REPRO_PREDICTIONS.json before generation.

Usage:
  .\\.venv-seam\\Scripts\\python.exe tools\\run_q_repro.py --out derived/q_repro/<run_id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apu_characterization.cap01.statistics import mcnemar_exact_two_sided  # noqa: E402
from seam.ov_kv_precision import read_kv_cache_precision  # noqa: E402
from seam.run_environment import RunEnvironmentSession  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    W3_ENTRIES_SHA256,
    W3_SEAL_REFS,
    assert_entry_set_matches_w3,
    assert_scorer_version,
    load_w3_entries,
)

ARMS = ("gpu_only", "gpu_only_f16")
# None => unset (W-3); string => pinned expected normalized name.
KV_EXPECTED: dict[str, str | None] = {
    "gpu_only": None,
    "gpu_only_f16": "f16",
}
PRED_PATH = ROOT / "derived" / "q_repro" / "Q_REPRO_PREDICTIONS.json"
MODEL_SPEC_DEFAULT = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
INTERLEAVE_SEED = 20260915
W3_EMISSION_FAILURES = 45
W3_TRAJECTORY_PASS = 20
QKV_F16_EMISSION_FAILURES = 62
QKV_F16_TRAJECTORY_PASS = 10


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def _sha256_tree(root: Path, *, exclude: set[str]) -> str:
    h = hashlib.sha256()
    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.name not in exclude),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for p in files:
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _assert_predictions_pre_registered() -> dict[str, Any]:
    if not PRED_PATH.is_file():
        raise SystemExit(f"REFUSED -- {PRED_PATH} missing; register before measuring")
    pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
    if pred.get("status") != "pre_registered_before_measurement":
        raise SystemExit(f"REFUSED -- bad predictions status {pred.get('status')!r}")
    if not pred.get("registered_utc"):
        raise SystemExit("REFUSED -- predictions missing registered_utc")
    return pred


def _kv_assert_from_meta(meta: dict[str, Any], *, arm_id: str) -> dict[str, Any]:
    """Pinned arms: refuse on mismatch. Unset arm: record readback, no enforce."""
    expected = KV_EXPECTED[arm_id]
    loads = meta.get("loads")
    if not isinstance(loads, list) or not loads:
        raise SystemExit(f"REFUSED -- {arm_id} load meta missing loads")
    out_loads: list[dict[str, Any]] = []
    for i, load in enumerate(loads):
        kv = (load or {}).get("kv_cache_precision")
        if not isinstance(kv, dict):
            raise SystemExit(f"REFUSED -- {arm_id} loads[{i}] missing kv_cache_precision")
        readback = kv.get("readback")
        if not isinstance(readback, dict) or "normalized" not in readback:
            raise SystemExit(f"REFUSED -- {arm_id} loads[{i}] readback incomplete: {kv!r}")
        if readback.get("normalized") is None and not readback.get("ok"):
            raise SystemExit(
                f"REFUSED -- {arm_id} KV readback failed: {readback.get('error')!r}"
            )
        got = (
            str(readback["normalized"]).lower()
            if readback.get("normalized") is not None
            else None
        )
        if expected is None:
            # W-3 path: unset. Accept whatever normalized is; must not claim enforced.
            if kv.get("enforced"):
                raise SystemExit(
                    f"REFUSED -- arm A gpu_only unexpectedly enforced KV: {kv!r}"
                )
            if kv.get("requested") is not None:
                raise SystemExit(
                    f"REFUSED -- arm A gpu_only requested KV should be None: {kv!r}"
                )
        else:
            if not kv.get("match") or got != expected:
                raise SystemExit(
                    f"REFUSED -- KV_PRECISION_MISMATCH arm={arm_id} "
                    f"expected={expected!r} got={got!r}"
                )
            if not kv.get("enforced"):
                raise SystemExit(f"REFUSED -- {arm_id} KV not enforced: {kv!r}")
        out_loads.append(kv)
    return {
        "arm_id": arm_id,
        "expected": expected,
        "loads_kv": out_loads,
        "normalized": out_loads[0].get("readback", {}).get("normalized"),
    }


def _cell_kv_readback_gpu() -> dict[str, Any]:
    """Fresh-Core device readback (may differ from load Core; both logged)."""
    import openvino as ov

    return read_kv_cache_precision("GPU", core=ov.Core())


def _entry_emission_ok(row: dict[str, Any]) -> bool:
    metrics = row.get("turn_metrics") or []
    if not metrics:
        return False
    return all(int(tm.get("n_decoded_steps") or 0) > 0 for tm in metrics)


def _quality_row(
    row: dict[str, Any],
    *,
    arm_id: str,
    kv_label: str,
    kv_readback_cell: dict[str, Any] | None,
    kv_readback_load: dict[str, Any] | None,
) -> dict[str, Any]:
    score = row.get("score") if isinstance(row.get("score"), dict) else {}
    valid = score.get("valid")
    return {
        "entry_id": row.get("id"),
        "arm_id": arm_id,
        "kv": kv_label,
        "trajectory_pass": bool(valid) if valid is not None else None,
        "score_error_type": score.get("error_type"),
        "score_error_message": score.get("error_message") or score.get("error"),
        "quality_scope": "local_probe",
        "model_result_decoded": row.get("model_result_decoded"),
        "emission_ok": _entry_emission_ok(row),
        "stop_reason": row.get("stop_reason"),
        "force_quit": bool(row.get("force_quit")),
        "n_user_turns": row.get("n_user_turns"),
        "n_completed_turns": row.get("n_completed_turns"),
        "wall_s": row.get("wall_s"),
        "kv_readback_load": kv_readback_load,
        "kv_readback_cell": kv_readback_cell,
    }


def _ledger_row(
    row: dict[str, Any],
    *,
    arm_id: str,
    kv_label: str,
    arm_order: list[str],
    kv_readback_cell: dict[str, Any] | None,
    kv_readback_load: dict[str, Any] | None,
) -> dict[str, Any]:
    q = _quality_row(
        row,
        arm_id=arm_id,
        kv_label=kv_label,
        kv_readback_cell=kv_readback_cell,
        kv_readback_load=kv_readback_load,
    )
    q.pop("model_result_decoded", None)
    turns = []
    for tm in row.get("turn_metrics") or []:
        turns.append(
            {
                "turn": tm.get("turn"),
                "n_decoded_steps": tm.get("n_decoded_steps"),
                "emitted_parseable_tool_call": int(tm.get("n_decoded_steps") or 0) > 0,
                "ttft_s": tm.get("ttft_s"),
                "decode_tok_s": tm.get("decode_tok_s"),
                "turn_wall_s": tm.get("turn_wall_s"),
                "tool_exec_error": bool(tm.get("tool_exec_error", False)),
                "tool_exec_error_class": tm.get("tool_exec_error_class"),
            }
        )
    q["turns"] = turns
    q["arm_order_this_entry"] = list(arm_order)
    return q


def _arm_order_for_entry(entry_id: str, *, seed: int) -> list[str]:
    rng = random.Random(f"{seed}:repro:{entry_id}")
    order = list(ARMS)
    rng.shuffle(order)
    return order


def _contingency(a: list[bool], b: list[bool]) -> dict[str, Any]:
    both_pass = sum(1 for x, y in zip(a, b) if x and y)
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if (not x) and y)
    both_fail = sum(1 for x, y in zip(a, b) if (not x) and (not y))
    return {
        "n": len(a),
        "table_2x2": {
            "both_pass": both_pass,
            "first_only": a_only,
            "second_only": b_only,
            "both_fail": both_fail,
        },
        "mcnemar": mcnemar_exact_two_sided(a, b),
    }


def analyze_paired(
    by_arm: dict[str, dict[str, dict[str, Any]]], entry_ids: list[str]
) -> dict[str, Any]:
    out: dict[str, Any] = {"per_arm": {}, "emission": {}, "completion": {}}
    for arm in ARMS:
        rows = [by_arm[arm][eid] for eid in entry_ids]
        n_fail = sum(1 for r in rows if not r["emission_ok"])
        n_pass = sum(1 for r in rows if r.get("trajectory_pass") is True)
        out["per_arm"][arm] = {
            "n": len(rows),
            "emission_failures": n_fail,
            "emission_ok": len(rows) - n_fail,
            "trajectory_pass": n_pass,
        }
    a, b = ARMS
    em_a = [bool(by_arm[a][eid]["emission_ok"]) for eid in entry_ids]
    em_b = [bool(by_arm[b][eid]["emission_ok"]) for eid in entry_ids]
    cp_a = [bool(by_arm[a][eid].get("trajectory_pass")) for eid in entry_ids]
    cp_b = [bool(by_arm[b][eid].get("trajectory_pass")) for eid in entry_ids]
    out["emission"][f"{a}__vs__{b}"] = _contingency(em_a, em_b)
    out["completion"][f"{a}__vs__{b}"] = _contingency(cp_a, cp_b)

    pa = out["per_arm"]["gpu_only"]
    pb = out["per_arm"]["gpu_only_f16"]
    # Classify against pre-registered outcomes (report only; no adjustment).
    a_near_w3_em = abs(pa["emission_failures"] - W3_EMISSION_FAILURES) <= 5
    a_near_w3_cp = abs(pa["trajectory_pass"] - W3_TRAJECTORY_PASS) <= 3
    a_near_qkv_em = abs(pa["emission_failures"] - QKV_F16_EMISSION_FAILURES) <= 5
    b_near_qkv_em = abs(pb["emission_failures"] - QKV_F16_EMISSION_FAILURES) <= 5
    if a_near_w3_em and a_near_w3_cp and b_near_qkv_em:
        verdict = "A_reproduces_W3_B_like_QKV_f16"
    elif a_near_qkv_em:
        verdict = "A_like_QKV_f16_W3_does_not_reproduce"
    else:
        verdict = "neither_registered_outcome_clean_match"
    out["outcome_class"] = verdict
    out["outcome_notes"] = {
        "A_emission_failures": pa["emission_failures"],
        "A_trajectory_pass": pa["trajectory_pass"],
        "B_emission_failures": pb["emission_failures"],
        "B_trajectory_pass": pb["trajectory_pass"],
        "W3_targets": {"emission_failures": W3_EMISSION_FAILURES, "trajectory_pass": W3_TRAJECTORY_PASS},
        "QKV_f16_targets": {
            "emission_failures": QKV_F16_EMISSION_FAILURES,
            "trajectory_pass": QKV_F16_TRAJECTORY_PASS,
        },
    }
    # Arm A readback summary
    norms = []
    for eid in entry_ids:
        cell = by_arm["gpu_only"][eid].get("kv_readback_load") or {}
        n = None
        if isinstance(cell, dict):
            n = cell.get("normalized")
            if n is None and isinstance(cell.get("readback"), dict):
                n = cell["readback"].get("normalized")
        if n is not None:
            norms.append(str(n))
    out["arm_a_kv_readback_normalized_counts"] = {
        k: norms.count(k) for k in sorted(set(norms))
    }
    return out


def build_report(
    summary: dict[str, Any], paired: dict[str, Any], pred: dict[str, Any]
) -> str:
    lines = [
        "# Q-REPRO results",
        "",
        f"run_id: `{summary.get('run_id')}`",
        f"session_wall_s: {summary.get('session_wall_s')}",
        f"tree_sha256: `{summary.get('tree_sha256')}`",
        "",
        "## Seal diff (pre-run)",
        "",
        "See `derived/q_repro/SEAL_DIFF_6225d6e1_vs_137f6f46.md`.",
        "",
        "## Per-arm",
        "",
        "| arm | emission failures | trajectory_pass |",
        "|---|---:|---:|",
    ]
    for arm in ARMS:
        p = paired["per_arm"][arm]
        lines.append(
            f"| `{arm}` | {p['emission_failures']}/200 | {p['trajectory_pass']}/200 |"
        )
    lines += [
        "",
        f"W-3 baseline: {W3_EMISSION_FAILURES} failures, {W3_TRAJECTORY_PASS} completions.",
        f"Q-KV f16: {QKV_F16_EMISSION_FAILURES} failures, {QKV_F16_TRAJECTORY_PASS} completions.",
        "",
        f"Arm A KV readback normalized counts: "
        f"{paired.get('arm_a_kv_readback_normalized_counts')}",
        "",
        f"**Outcome class:** `{paired.get('outcome_class')}`",
        "",
        "## Paired McNemar",
        "",
    ]
    for endpoint in ("emission", "completion"):
        for key, blk in paired[endpoint].items():
            t = blk["table_2x2"]
            m = blk["mcnemar"]
            lines.append(f"### {endpoint} {key}")
            lines.append(
                f"2x2: both_pass={t['both_pass']}, first_only={t['first_only']}, "
                f"second_only={t['second_only']}, both_fail={t['both_fail']}"
            )
            lines.append(
                f"McNemar: discordant={m['discordant']}, p={m['p_value']:.6g}"
            )
            lines.append("")
    oc = paired.get("outcome_class")
    if oc == "A_reproduces_W3_B_like_QKV_f16":
        lines.append(
            "Interpretation: dynamic KV is materially different from pinned f16."
        )
    elif oc == "A_like_QKV_f16_W3_does_not_reproduce":
        lines.append(
            "Interpretation: W-3 does not reproduce. Quality instrument is not "
            "stable across sessions; sealed quality numbers (including emission "
            "OR 4.57 from 6225d6e1/1d8db970) need a stability statement before "
            "the paper."
        )
    else:
        lines.append(
            "Interpretation: neither clean registered outcome; report numbers as measured."
        )
    lines.append("")
    return "\n".join(lines)


def run_session(
    *,
    out_dir: Path,
    entries: list[dict[str, Any]],
    model_spec: Path,
    run_id: str,
    seal: bool,
    interleave_seed: int,
) -> dict[str, Any]:
    import openvino as ov
    import openvino_genai as ov_genai

    import tools.bfcl_feasibility_probe as probe

    pred = _assert_predictions_pre_registered()
    out_dir.mkdir(parents=True, exist_ok=True)
    probe.apply_model_spec(model_spec)
    gold = probe.run_multi_turn_gold_selftest(entries)
    if int(gold.get("n_valid") or 0) != len(entries):
        raise SystemExit(
            f"REFUSED -- gold {gold.get('n_valid')}/{gold.get('n')} need {len(entries)}"
        )
    _write_json(out_dir / "multi_turn_gold_selftest.json", gold)

    tokenizer = probe._hf_tokenizer()
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = 512
    cfg.do_sample = False
    cfg.apply_chat_template = False

    avail0 = probe._host_available_mb()
    mb_start = avail0.get("available_mb")
    if mb_start is None:
        raise SystemExit("REFUSED -- available_mb_start unreadable at Q-REPRO session begin")
    env_session = RunEnvironmentSession.begin(
        session_design="interleaved",
        arm_order=list(ARMS),
        available_mb_start=float(mb_start),
        available_mb_start_method=str(avail0.get("available_method") or "probe._host_available_mb"),
    )
    pipes: dict[str, Any] = {}
    load_metas: dict[str, Any] = {}
    kv_asserts: dict[str, Any] = {}
    load_kv_blobs: dict[str, Any] = {}
    pipeline_mode = "block_interleave_single_pipe"
    block_size = 5
    if float(avail0.get("available_mb") or 0) >= 7000.0:
        # Still prefer single-pipe for two arms on this host unless plenty of headroom;
        # try dual resident briefly.
        pipeline_mode = "dual_resident_try"

    def _drop_all() -> None:
        pipes.clear()
        import gc

        gc.collect()

    def _load_one(arm_id: str) -> None:
        pipe, meta, load_s = probe.load_arm_pipeline(arm_id, enable_prefix_caching=None)
        kv_asserts[arm_id] = _kv_assert_from_meta(meta, arm_id=arm_id)
        load_kv_blobs[arm_id] = kv_asserts[arm_id]
        pipes[arm_id] = pipe
        load_metas[arm_id] = {
            **meta,
            "load_s": load_s,
            "openvino": ov.__version__,
            "openvino_genai": getattr(ov_genai, "__version__", "unknown"),
        }
        print(
            f"LOAD_ARM_OK {arm_id} load_s={load_s:.2f} "
            f"kv_normalized={kv_asserts[arm_id].get('normalized')!r}",
            flush=True,
        )

    if pipeline_mode == "dual_resident_try":
        try:
            for arm_id in ARMS:
                print(f"LOAD_ARM {arm_id} …", flush=True)
                _load_one(arm_id)
            pipeline_mode = "dual_resident"
        except Exception as exc:
            print(f"DUAL_LOAD_FAILED {type(exc).__name__}: {exc}; single-pipe", flush=True)
            _drop_all()
            pipeline_mode = "block_interleave_single_pipe"
            block_size = 5
    else:
        print(
            f"AVAILABLE_MB={avail0.get('available_mb')}; using block_interleave_single_pipe",
            flush=True,
        )

    plan = {
        "kind": "q_repro",
        "run_id": run_id,
        "measurement_kind": "MEASURED",
        "cloud_usd": 0.0,
        "arms": list(ARMS),
        "kv_expected": dict(KV_EXPECTED),
        "residency": "RESIDENT",
        "placement": "gpu_only",
        "model_spec": str(model_spec),
        "max_new_tokens": 512,
        "do_sample": False,
        "n_entries": len(entries),
        "w3_entry_pin": W3_ENTRIES_SHA256,
        "w3_seal_refs": list(W3_SEAL_REFS),
        "scorer": assert_scorer_version(),
        "interleave_seed": interleave_seed,
        "pipeline_mode": pipeline_mode,
        "block_size": block_size,
        "available_mb_start": avail0,
        "session_design": "interleaved",
        "arm_order": list(ARMS),
        "run_environment": {
            "available_mb_start": float(mb_start),
            "session_design": "interleaved",
            "arm_order": list(ARMS),
        },
        "stack": {
            "openvino": ov.__version__,
            "openvino_genai": getattr(ov_genai, "__version__", "unknown"),
        },
        "predictions_path": str(PRED_PATH),
        "predictions_registered_utc": pred.get("registered_utc"),
        "seal_diff": "derived/q_repro/SEAL_DIFF_6225d6e1_vs_137f6f46.md",
        "started_utc": _utc_now(),
        "seal": bool(seal),
    }
    _write_json(out_dir / "plan.json", plan)

    by_arm: dict[str, dict[str, dict[str, Any]]] = {a: {} for a in ARMS}
    quality_rows: list[dict[str, Any]] = []
    cell_log: list[dict[str, Any]] = []
    ckpt_path = out_dir / "checkpoint.json"
    done: set[tuple[str, str]] = set()
    if ckpt_path.is_file():
        ckpt = json.loads(ckpt_path.read_text(encoding="utf-8-sig"))
        for pair in ckpt.get("completed_cells") or []:
            done.add((str(pair[0]), str(pair[1])))
        for arm, rows in (ckpt.get("by_arm") or {}).items():
            if arm in by_arm:
                by_arm[arm].update(rows)
        quality_rows = list(ckpt.get("quality_rows") or [])
        cell_log = list(ckpt.get("cell_log") or [])
        print(f"RESUME cells_done={len(done)}", flush=True)

    entry_ids = [str(e["id"]) for e in entries]
    t_session0 = time.perf_counter()

    def _ensure_arm(arm_id: str) -> None:
        if arm_id in pipes and pipes[arm_id] is not None:
            return
        if pipeline_mode == "dual_resident":
            raise SystemExit(f"REFUSED -- dual mode missing pipe {arm_id}")
        _drop_all()
        print(f"LOAD_ARM {arm_id} (single-pipe switch) …", flush=True)
        _load_one(arm_id)
        _write_json(out_dir / "kv_readback_live.json", kv_asserts)

    def _run_cell(entry: dict[str, Any], arm_id: str, order: list[str]) -> None:
        eid = str(entry["id"])
        if (eid, arm_id) in done:
            print(f"SKIP {eid} {arm_id}", flush=True)
            return
        _ensure_arm(arm_id)
        kv_label = "dynamic_unset" if KV_EXPECTED[arm_id] is None else str(KV_EXPECTED[arm_id])
        kv_load = load_kv_blobs.get(arm_id)
        kv_cell = None
        if arm_id == "gpu_only":
            kv_cell = _cell_kv_readback_gpu()
        print(f"CELL_START entry={eid} arm={arm_id}", flush=True)
        t0 = time.perf_counter()
        row = probe.run_multi_turn_agent_entry(
            pipe=pipes[arm_id],
            tokenizer=tokenizer,
            cfg=cfg,
            entry=entry,
            residency_mode="RESIDENT",
            ov_genai=ov_genai,
        )
        wall = time.perf_counter() - t0
        led = _ledger_row(
            row,
            arm_id=arm_id,
            kv_label=kv_label,
            arm_order=order,
            kv_readback_cell=kv_cell,
            kv_readback_load=kv_load,
        )
        led["cell_wall_s"] = wall
        digest = row.get("prompt_render_sha256")
        if isinstance(digest, str) and len(digest) == 64:
            led["prompt_render_sha256"] = digest
            env_session.add_prompt_digest(digest)
        by_arm[arm_id][eid] = led
        quality_rows.append(
            _quality_row(
                row,
                arm_id=arm_id,
                kv_label=kv_label,
                kv_readback_cell=kv_cell,
                kv_readback_load=kv_load,
            )
        )
        cell_log.append(
            {
                "entry_id": eid,
                "arm_id": arm_id,
                "kv": kv_label,
                "wall_s": wall,
                "emission_ok": led["emission_ok"],
                "trajectory_pass": led["trajectory_pass"],
                "kv_readback_cell_normalized": (
                    (kv_cell or {}).get("normalized") if kv_cell else None
                ),
                "kv_readback_load_normalized": (
                    (kv_load or {}).get("normalized") if kv_load else None
                ),
                "utc": _utc_now(),
            }
        )
        done.add((eid, arm_id))
        _write_json(
            ckpt_path,
            {
                "completed_cells": sorted([list(x) for x in done]),
                "by_arm": by_arm,
                "quality_rows": quality_rows,
                "cell_log": cell_log,
                "updated_utc": _utc_now(),
            },
        )
        _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
        _write_json(out_dir / "turn_ledger.json", {"by_arm": by_arm, "entry_ids": entry_ids})
        print(
            f"CELL_DONE entry={eid} arm={arm_id} wall_s={wall:.1f} "
            f"emission_ok={led['emission_ok']} traj={led['trajectory_pass']} "
            f"kv_cell={(kv_cell or {}).get('normalized')!r}",
            flush=True,
        )

    if pipeline_mode == "dual_resident":
        for entry in entries:
            order = _arm_order_for_entry(str(entry["id"]), seed=interleave_seed)
            for arm_id in order:
                _run_cell(entry, arm_id, order)
    else:
        for block_start in range(0, len(entries), block_size):
            block = entries[block_start : block_start + block_size]
            rng = random.Random(f"{interleave_seed}:repro:block:{block_start}")
            arm_cycle = list(ARMS)
            rng.shuffle(arm_cycle)
            for arm_id in arm_cycle:
                for entry in block:
                    order = _arm_order_for_entry(str(entry["id"]), seed=interleave_seed)
                    _run_cell(entry, arm_id, order)

    missing = [
        (eid, arm)
        for eid in entry_ids
        for arm in ARMS
        if eid not in by_arm[arm]
    ]
    if missing:
        raise SystemExit(f"REFUSED -- incomplete matrix; missing {len(missing)}")

    if env_session.prompt_update_count == 0:
        for arm_rows in by_arm.values():
            for led in arm_rows.values():
                digest = led.get("prompt_render_sha256")
                if isinstance(digest, str) and len(digest) == 64:
                    env_session.add_prompt_digest(digest)

    paired = analyze_paired(by_arm, entry_ids)
    _write_json(out_dir / "paired_analysis.json", paired)
    run_environment = env_session.finalize()
    plan["run_environment"] = run_environment
    plan["prompt_render_sha256"] = run_environment["prompt_render_sha256"]
    _write_json(out_dir / "plan.json", plan)
    summary = {
        "kind": "q_repro",
        "run_id": run_id,
        "status": "complete",
        "measurement_kind": "MEASURED",
        "cloud_usd": 0.0,
        "n_entries": len(entry_ids),
        "n_cells": len(entry_ids) * len(ARMS),
        "session_wall_s": time.perf_counter() - t_session0,
        "finished_utc": _utc_now(),
        "per_arm": paired["per_arm"],
        "outcome_class": paired["outcome_class"],
        "arm_a_kv_readback_normalized_counts": paired["arm_a_kv_readback_normalized_counts"],
        "predictions_registered_utc": pred.get("registered_utc"),
        "stack": plan["stack"],
        "scorer": assert_scorer_version(),
        "session_design": "interleaved",
        "arm_order": list(ARMS),
        "available_mb_start": run_environment["available_mb_start"],
        "available_mb_end": run_environment["available_mb_end"],
        "prompt_render_sha256": run_environment["prompt_render_sha256"],
        "run_environment": run_environment,
    }
    report = build_report(summary, paired, pred)
    (out_dir / "Q_REPRO_RESULTS.md").write_text(report, encoding="utf-8")
    (ROOT / "derived" / "q_repro" / "Q_REPRO_RESULTS.md").write_text(report, encoding="utf-8")
    _write_json(out_dir / "summary.json", summary)
    _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
    _write_json(out_dir / "turn_ledger.json", {"by_arm": by_arm, "entry_ids": entry_ids})
    _write_json(out_dir / "cell_log.json", {"cells": cell_log})
    if seal:
        tree = _sha256_tree(out_dir, exclude={".sealed"})
        seal_doc = {
            "run_id": run_id,
            "kind": "q_repro",
            "sealed_utc": _utc_now(),
            "tree_sha256": tree,
            "status": "complete",
            "measurement_kind": "MEASURED",
        }
        (out_dir / ".sealed").write_text(
            json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        summary["tree_sha256"] = tree
        _write_json(out_dir / "summary.json", summary)
        report = build_report(summary, paired, pred)
        (out_dir / "Q_REPRO_RESULTS.md").write_text(report, encoding="utf-8")
        (ROOT / "derived" / "q_repro" / "Q_REPRO_RESULTS.md").write_text(
            report, encoding="utf-8"
        )
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"))
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Q-REPRO W-3 dynamic vs f16")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--model-spec", type=Path, default=MODEL_SPEC_DEFAULT)
    p.add_argument("--entries", type=Path, default=None)
    p.add_argument("--interleave-seed", type=int, default=INTERLEAVE_SEED)
    p.add_argument("--seal", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--analyze-only", type=Path, default=None)
    args = p.parse_args(argv)

    if args.analyze_only is not None:
        out = args.analyze_only
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8-sig"))
        paired = json.loads((out / "paired_analysis.json").read_text(encoding="utf-8-sig"))
        pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
        report = build_report(summary, paired, pred)
        (out / "Q_REPRO_RESULTS.md").write_text(report, encoding="utf-8")
        print(report.encode("ascii", errors="replace").decode("ascii"))
        return 0

    run_id = args.run_id or str(uuid.uuid4())
    entries, entries_path = load_w3_entries(args.entries)
    assert_entry_set_matches_w3(entries_path)
    if len(entries) != 200:
        raise SystemExit(f"REFUSED -- need 200 entries, got {len(entries)}")
    print(f"Q_REPRO_START run_id={run_id} out={args.out}", flush=True)
    run_session(
        out_dir=args.out,
        entries=entries,
        model_spec=args.model_spec,
        run_id=run_id,
        seal=bool(args.seal),
        interleave_seed=int(args.interleave_seed),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
