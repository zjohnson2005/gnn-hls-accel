"""Q-KV: interleaved KV precision vs BFCL multi-turn quality (local only).

Arms: gpu_only_f16, gpu_only_u8, gpu_only_u4 — RESIDENT, int4-4B.
Same 200 entries as W-3 6225d6e1. One session, per-entry arm permutation
so machine state cannot explain arm differences. KV readback enforced;
REFUSE on mismatch. Persists entry_quality.json (H1-FIX path) so completion
and emission land together.

Predictions must already exist in derived/q_kv/Q_KV_PREDICTIONS.json
(registered before this process generates).

Usage:
  .\\.venv-seam\\Scripts\\python.exe tools\\run_q_kv_quality.py --out derived/q_kv/<run_id>
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
from seam.run_environment import RunEnvironmentSession  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    W3_ENTRIES_SHA256,
    W3_SEAL_REFS,
    assert_entry_set_matches_w3,
    assert_scorer_version,
    load_w3_entries,
)

ARMS = ("gpu_only_f16", "gpu_only_u8", "gpu_only_u4")
KV_EXPECTED = {
    "gpu_only_f16": "f16",
    "gpu_only_u8": "u8",
    "gpu_only_u4": "u4",
}
PRED_PATH = ROOT / "derived" / "q_kv" / "Q_KV_PREDICTIONS.json"
MODEL_SPEC_DEFAULT = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
INTERLEAVE_SEED = 20260915


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
        raise SystemExit(
            f"REFUSED -- {PRED_PATH} missing; register predictions before measuring"
        )
    pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
    if pred.get("status") != "pre_registered_before_measurement":
        raise SystemExit(
            f"REFUSED -- predictions status must be pre_registered_before_measurement; "
            f"got {pred.get('status')!r}"
        )
    reg = pred.get("registered_utc")
    if not reg:
        raise SystemExit("REFUSED -- predictions missing registered_utc")
    return pred


def _assert_kv_readback(meta: dict[str, Any], *, arm_id: str, expected: str) -> dict[str, Any]:
    """Refuse unless loads[*].kv_cache_precision.readback.normalized == expected."""
    expected_n = expected.strip().lower()
    loads = meta.get("loads")
    if not isinstance(loads, list) or not loads:
        raise SystemExit(f"REFUSED -- {arm_id} load meta missing loads")
    for i, load in enumerate(loads):
        kv = (load or {}).get("kv_cache_precision")
        if not isinstance(kv, dict):
            raise SystemExit(f"REFUSED -- {arm_id} loads[{i}] missing kv_cache_precision")
        readback = kv.get("readback")
        if not isinstance(readback, dict) or "normalized" not in readback:
            raise SystemExit(
                f"REFUSED -- {arm_id} loads[{i}] readback.normalized missing: {kv!r}"
            )
        normalized = readback["normalized"]
        if normalized is None:
            raise SystemExit(
                f"REFUSED -- {arm_id} KV readback normalized is None "
                f"(device={readback.get('device')!r} error={readback.get('error')!r})"
            )
        got = str(normalized).lower()
        if not kv.get("match") or got != expected_n:
            raise SystemExit(
                f"REFUSED -- KV_PRECISION_MISMATCH arm={arm_id} "
                f"expected={expected_n!r} got={got!r} match={kv.get('match')!r}"
            )
        if not kv.get("enforced"):
            raise SystemExit(
                f"REFUSED -- {arm_id} KV pin not enforced; observed={kv!r}"
            )
    return {
        "arm_id": arm_id,
        "expected": expected_n,
        "loads": loads,
    }


def _entry_emission_ok(row: dict[str, Any]) -> bool:
    """True iff every measured turn emitted at least one parseable tool call."""
    metrics = row.get("turn_metrics") or []
    if not metrics:
        return False
    for tm in metrics:
        if int(tm.get("n_decoded_steps") or 0) <= 0:
            return False
    return True


def _quality_row(row: dict[str, Any], *, arm_id: str, kv: str) -> dict[str, Any]:
    score = row.get("score") if isinstance(row.get("score"), dict) else {}
    valid = score.get("valid")
    return {
        "entry_id": row.get("id"),
        "arm_id": arm_id,
        "kv": kv,
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
        "tool_exec_error_any": any(
            bool(tm.get("tool_exec_error")) for tm in (row.get("turn_metrics") or [])
        ),
    }


def _ledger_row(row: dict[str, Any], *, arm_id: str, kv: str, arm_order: list[str]) -> dict[str, Any]:
    q = _quality_row(row, arm_id=arm_id, kv=kv)
    # Compact ledger omits decoded (lives in entry_quality.json).
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
                "t_tool_exec": tm.get("t_tool_exec"),
                "t_template_build": tm.get("t_template_build"),
                "t_tokenize": tm.get("t_tokenize"),
                "t_generate": tm.get("t_generate"),
                "t_other": tm.get("t_other"),
                "tool_exec_error": bool(tm.get("tool_exec_error", False)),
                "tool_exec_error_class": tm.get("tool_exec_error_class"),
                "per_turn_accuracy": tm.get("per_turn_accuracy"),
            }
        )
    q["turns"] = turns
    q["arm_order_this_entry"] = list(arm_order)
    return q


def _arm_order_for_entry(entry_id: str, *, seed: int) -> list[str]:
    rng = random.Random(f"{seed}:{entry_id}")
    order = list(ARMS)
    rng.shuffle(order)
    return order


def _contingency(a: list[bool], b: list[bool]) -> dict[str, Any]:
    """2x2: rows=a, cols=b; cells both_pass, a_only, b_only, both_fail."""
    both_pass = sum(1 for x, y in zip(a, b) if x and y)
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if (not x) and y)
    both_fail = sum(1 for x, y in zip(a, b) if (not x) and (not y))
    mcn = mcnemar_exact_two_sided(a, b)
    return {
        "n": len(a),
        "table_2x2": {
            "both_pass": both_pass,
            "first_only": a_only,
            "second_only": b_only,
            "both_fail": both_fail,
            "layout": "[[both_pass, first_only], [second_only, both_fail]] "
            "(row=first arm pass/fail, col=second arm pass/fail)",
        },
        "mcnemar": mcn,
    }


def analyze_paired(
    by_arm: dict[str, dict[str, dict[str, Any]]],
    entry_ids: list[str],
) -> dict[str, Any]:
    """Paired McNemar on emission_ok and trajectory_pass."""
    pairs = [("gpu_only_f16", "gpu_only_u8"), ("gpu_only_f16", "gpu_only_u4"), ("gpu_only_u8", "gpu_only_u4")]
    out: dict[str, Any] = {"emission": {}, "completion": {}, "per_arm": {}}
    for arm in ARMS:
        rows = [by_arm[arm][eid] for eid in entry_ids]
        n_em_fail = sum(1 for r in rows if not r["emission_ok"])
        n_pass = sum(1 for r in rows if r.get("trajectory_pass") is True)
        out["per_arm"][arm] = {
            "n": len(rows),
            "emission_failures": n_em_fail,
            "emission_ok": len(rows) - n_em_fail,
            "emission_failure_rate": n_em_fail / len(rows) if rows else None,
            "trajectory_pass": n_pass,
            "trajectory_pass_rate": n_pass / len(rows) if rows else None,
        }
    for a, b in pairs:
        em_a = [bool(by_arm[a][eid]["emission_ok"]) for eid in entry_ids]
        em_b = [bool(by_arm[b][eid]["emission_ok"]) for eid in entry_ids]
        cp_a = [bool(by_arm[a][eid].get("trajectory_pass")) for eid in entry_ids]
        cp_b = [bool(by_arm[b][eid].get("trajectory_pass")) for eid in entry_ids]
        key = f"{a}__vs__{b}"
        out["emission"][key] = _contingency(em_a, em_b)
        out["completion"][key] = _contingency(cp_a, cp_b)
    # Falsification: all pairwise p>=0.05 or zero discordant on BOTH endpoints.
    def _agree(block: dict[str, Any]) -> bool:
        for v in block.values():
            m = v["mcnemar"]
            if int(m["discordant"]) == 0:
                continue
            if float(m["p_value"]) < 0.05:
                return False
        return True

    out["falsification"] = {
        "emission_arms_agree": _agree(out["emission"]),
        "completion_arms_agree": _agree(out["completion"]),
        "kv_quality_axis_falsified": _agree(out["emission"]) and _agree(out["completion"]),
        "rule": "Falsified if all pairwise McNemar p>=0.05 (or 0 discordant) on BOTH emission and completion",
    }
    return out


def run_session(
    *,
    out_dir: Path,
    entries: list[dict[str, Any]],
    model_spec: Path,
    run_id: str,
    seal: bool,
    interleave_seed: int,
) -> dict[str, Any]:
    import openvino_genai as ov_genai

    import tools.bfcl_feasibility_probe as probe

    pred = _assert_predictions_pre_registered()
    out_dir.mkdir(parents=True, exist_ok=True)

    probe.apply_model_spec(model_spec)
    gold = probe.run_multi_turn_gold_selftest(entries)
    if int(gold.get("n_valid") or 0) != len(entries):
        raise SystemExit(
            f"REFUSED -- gold selftest {gold.get('n_valid')}/{gold.get('n')} "
            f"(need {len(entries)}/{len(entries)})"
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
        raise SystemExit("REFUSED -- available_mb_start unreadable at Q-KV session begin")
    env_session = RunEnvironmentSession.begin(
        session_design="interleaved",
        arm_order=list(ARMS),
        available_mb_start=float(mb_start),
        available_mb_start_method=str(avail0.get("available_method") or "probe._host_available_mb"),
    )
    pipes: dict[str, Any] = {}
    load_metas: dict[str, Any] = {}
    kv_asserts: dict[str, Any] = {}
    pipeline_mode = "triple_resident"
    block_size = 1

    def _load_one(arm_id: str) -> None:
        pipe, meta, load_s = probe.load_arm_pipeline(arm_id, enable_prefix_caching=None)
        kv_asserts[arm_id] = _assert_kv_readback(
            meta, arm_id=arm_id, expected=KV_EXPECTED[arm_id]
        )
        pipes[arm_id] = pipe
        load_metas[arm_id] = {**meta, "load_s": load_s}
        print(f"LOAD_ARM_OK {arm_id} load_s={load_s:.2f}", flush=True)

    def _drop_all() -> None:
        pipes.clear()
        import gc

        gc.collect()

    # Prefer three resident pipes (true per-cell interleave, no reload).
    # On OOM / low headroom, fall back to block-interleaved single pipe:
    # every ``block_size`` entries, run all three arms (arm-grouped within the
    # block) so machine drift cannot favor one KV across the corpus.
    try_triple = float(avail0.get("available_mb") or 0) >= 7000.0
    if try_triple:
        try:
            for arm_id in ARMS:
                print(f"LOAD_ARM {arm_id} …", flush=True)
                _load_one(arm_id)
        except Exception as exc:
            print(f"TRIPLE_LOAD_FAILED {type(exc).__name__}: {exc}; falling back", flush=True)
            _drop_all()
            pipeline_mode = "block_interleave_single_pipe"
            block_size = 5
    else:
        print(
            f"AVAILABLE_MB={avail0.get('available_mb')} < 7000; "
            "using block_interleave_single_pipe",
            flush=True,
        )
        pipeline_mode = "block_interleave_single_pipe"
        block_size = 5

    plan = {
        "kind": "q_kv_quality",
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
        "interleave": (
            "per_entry_shuffle_three_resident_pipes"
            if pipeline_mode == "triple_resident"
            else f"block_size={block_size}_arm_grouped_within_block_single_pipe"
        ),
        "predictions_path": str(PRED_PATH),
        "predictions_registered_utc": pred.get("registered_utc"),
        "w3_unset_kv_note": pred.get("w3_unset_kv_readback"),
        "kv_readback_assert": kv_asserts,
        "load_metas": {k: v for k, v in load_metas.items()},
        "started_utc": _utc_now(),
        "seal": bool(seal),
    }
    _write_json(out_dir / "plan.json", plan)

    # by_arm[arm][entry_id] = ledger row
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
    current_arm: str | None = None

    def _ensure_arm(arm_id: str) -> None:
        nonlocal current_arm
        if arm_id in pipes and pipes[arm_id] is not None:
            current_arm = arm_id
            return
        if pipeline_mode == "triple_resident":
            raise SystemExit(f"REFUSED -- triple mode missing pipe for {arm_id}")
        # Single-pipe: drop other arms, load this one, re-assert KV.
        _drop_all()
        print(f"LOAD_ARM {arm_id} (single-pipe switch) …", flush=True)
        _load_one(arm_id)
        current_arm = arm_id
        # Persist updated kv asserts into plan sidecar.
        _write_json(out_dir / "kv_readback_live.json", kv_asserts)

    def _run_cell(entry: dict[str, Any], arm_id: str, order: list[str]) -> None:
        eid = str(entry["id"])
        if (eid, arm_id) in done:
            print(f"SKIP {eid} {arm_id}", flush=True)
            return
        _ensure_arm(arm_id)
        kv = KV_EXPECTED[arm_id]
        print(f"CELL_START entry={eid} arm={arm_id} order={order}", flush=True)
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
        row["arm_id"] = arm_id
        row["kv"] = kv
        led = _ledger_row(row, arm_id=arm_id, kv=kv, arm_order=order)
        led["cell_wall_s"] = wall
        digest = row.get("prompt_render_sha256")
        if isinstance(digest, str) and len(digest) == 64:
            led["prompt_render_sha256"] = digest
            env_session.add_prompt_digest(digest)
        by_arm[arm_id][eid] = led
        quality_rows.append(_quality_row(row, arm_id=arm_id, kv=kv))
        cell_log.append(
            {
                "entry_id": eid,
                "arm_id": arm_id,
                "kv": kv,
                "arm_order": order,
                "wall_s": wall,
                "emission_ok": led["emission_ok"],
                "trajectory_pass": led["trajectory_pass"],
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
            f"emission_ok={led['emission_ok']} traj={led['trajectory_pass']}",
            flush=True,
        )

    if pipeline_mode == "triple_resident":
        for entry in entries:
            eid = str(entry["id"])
            order = _arm_order_for_entry(eid, seed=interleave_seed)
            for arm_id in order:
                _run_cell(entry, arm_id, order)
    else:
        # Block interleave: within each block, arm-major (3 loads / block_size entries).
        for block_start in range(0, len(entries), block_size):
            block = entries[block_start : block_start + block_size]
            # Rotate which arm runs first across blocks (seeded).
            rng = random.Random(f"{interleave_seed}:block:{block_start}")
            arm_cycle = list(ARMS)
            rng.shuffle(arm_cycle)
            for arm_id in arm_cycle:
                for entry in block:
                    eid = str(entry["id"])
                    order = _arm_order_for_entry(eid, seed=interleave_seed)
                    _run_cell(entry, arm_id, order)

    # Require full matrix before analysis seal.
    missing = [
        (eid, arm)
        for eid in entry_ids
        for arm in ARMS
        if eid not in by_arm[arm]
    ]
    if missing:
        raise SystemExit(f"REFUSED -- incomplete matrix; missing {len(missing)} cells")

    # Resume path: re-fold per-cell prompt digests recorded in the ledger.
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
        "kind": "q_kv_quality",
        "run_id": run_id,
        "status": "complete",
        "measurement_kind": "MEASURED",
        "cloud_usd": 0.0,
        "n_entries": len(entry_ids),
        "n_cells": len(entry_ids) * len(ARMS),
        "session_wall_s": time.perf_counter() - t_session0,
        "finished_utc": _utc_now(),
        "per_arm": paired["per_arm"],
        "falsification": paired["falsification"],
        "predictions_registered_utc": pred.get("registered_utc"),
        "w3_unset_kv": pred.get("w3_unset_kv_readback"),
        "scorer": assert_scorer_version(),
        "session_design": "interleaved",
        "arm_order": list(ARMS),
        "available_mb_start": run_environment["available_mb_start"],
        "available_mb_end": run_environment["available_mb_end"],
        "prompt_render_sha256": run_environment["prompt_render_sha256"],
        "run_environment": run_environment,
    }
    _write_json(out_dir / "summary.json", summary)
    _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
    _write_json(out_dir / "turn_ledger.json", {"by_arm": by_arm, "entry_ids": entry_ids})
    _write_json(out_dir / "cell_log.json", {"cells": cell_log})

    if seal:
        tree = _sha256_tree(out_dir, exclude={".sealed"})
        seal_doc = {
            "run_id": run_id,
            "kind": "q_kv_quality",
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

    return summary


def build_report(summary: dict[str, Any], paired: dict[str, Any], pred: dict[str, Any]) -> str:
    lines = [
        "# Q-KV results",
        "",
        f"run_id: `{summary.get('run_id')}`",
        f"session_wall_s: {summary.get('session_wall_s')}",
        f"tree_sha256: `{summary.get('tree_sha256')}`",
        "",
        "## W-3 unset KV",
        "",
        f"Readback in seal 6225d6e1: **{pred.get('w3_unset_kv_readback', {}).get('normalized')}** "
        f"(requested={pred.get('w3_unset_kv_readback', {}).get('requested')}, "
        f"enforced={pred.get('w3_unset_kv_readback', {}).get('enforced')}). "
        "Treated as unknown precision, not f16.",
        "",
        "## Per-arm emission and completion",
        "",
        "| arm | emission failures | emission ok | trajectory_pass |",
        "|---|---:|---:|---:|",
    ]
    for arm in ARMS:
        p = paired["per_arm"][arm]
        lines.append(
            f"| `{arm}` | {p['emission_failures']}/200 | {p['emission_ok']}/200 | "
            f"{p['trajectory_pass']}/200 |"
        )
    lines += ["", "## Paired McNemar — emission", ""]
    for key, blk in paired["emission"].items():
        t = blk["table_2x2"]
        m = blk["mcnemar"]
        lines.append(f"### {key}")
        lines.append(
            f"2×2: both_pass={t['both_pass']}, first_only={t['first_only']}, "
            f"second_only={t['second_only']}, both_fail={t['both_fail']}"
        )
        lines.append(
            f"McNemar: discordant={m['discordant']}, "
            f"first_only={m['first_only']}, second_only={m['second_only']}, "
            f"p={m['p_value']:.6g}"
        )
        lines.append("")
    lines += ["## Paired McNemar — completion", ""]
    for key, blk in paired["completion"].items():
        t = blk["table_2x2"]
        m = blk["mcnemar"]
        lines.append(f"### {key}")
        lines.append(
            f"2×2: both_pass={t['both_pass']}, first_only={t['first_only']}, "
            f"second_only={t['second_only']}, both_fail={t['both_fail']}"
        )
        lines.append(
            f"McNemar: discordant={m['discordant']}, "
            f"first_only={m['first_only']}, second_only={m['second_only']}, "
            f"p={m['p_value']:.6g}"
        )
        lines.append("")
    fals = paired["falsification"]
    lines += [
        "## Verdict",
        "",
        f"- emission arms agree (falsify KV-emission): **{fals['emission_arms_agree']}**",
        f"- completion arms agree: **{fals['completion_arms_agree']}**",
        f"- KV quality-axis hypothesis falsified: **{fals['kv_quality_axis_falsified']}**",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Q-KV interleaved KV quality")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--model-spec", type=Path, default=MODEL_SPEC_DEFAULT)
    p.add_argument("--entries", type=Path, default=None)
    p.add_argument("--interleave-seed", type=int, default=INTERLEAVE_SEED)
    p.add_argument("--seal", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--analyze-only",
        type=Path,
        default=None,
        help="Re-analyze an existing out dir (no hardware)",
    )
    args = p.parse_args(argv)

    if args.analyze_only is not None:
        out = args.analyze_only
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8-sig"))
        paired = json.loads((out / "paired_analysis.json").read_text(encoding="utf-8-sig"))
        pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
        report = build_report(summary, paired, pred)
        # Headline H-1 + pruning decided in report extension below.
        report = _extend_report_decisions(report, paired, pred)
        (out / "Q_KV_RESULTS.md").write_text(report, encoding="utf-8")
        print(report)
        return 0

    pred = _assert_predictions_pre_registered()
    run_id = args.run_id or str(uuid.uuid4())
    out_dir = args.out
    entries, entries_path = load_w3_entries(args.entries)
    assert_entry_set_matches_w3(entries_path)
    if len(entries) != 200:
        raise SystemExit(f"REFUSED -- need 200 entries, got {len(entries)}")

    print(f"Q_KV_START run_id={run_id} out={out_dir}", flush=True)
    summary = run_session(
        out_dir=out_dir,
        entries=entries,
        model_spec=args.model_spec,
        run_id=run_id,
        seal=bool(args.seal),
        interleave_seed=int(args.interleave_seed),
    )
    paired = json.loads((out_dir / "paired_analysis.json").read_text(encoding="utf-8-sig"))
    report = _extend_report_decisions(build_report(summary, paired, pred), paired, pred)
    (out_dir / "Q_KV_RESULTS.md").write_text(report, encoding="utf-8")
    # Also copy to derived/q_kv/ for the track index.
    (ROOT / "derived" / "q_kv" / "Q_KV_RESULTS.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def _extend_report_decisions(
    report: str, paired: dict[str, Any], pred: dict[str, Any]
) -> str:
    """Append H-1 config recommendation and u8-vs-u4 pruning verdict."""
    per = paired["per_arm"]
    # Prefer highest emission_ok, then highest trajectory_pass, then denser KV.
    ranked = sorted(
        ARMS,
        key=lambda a: (
            per[a]["emission_ok"],
            per[a]["trajectory_pass"],
            {"gpu_only_u4": 3, "gpu_only_u8": 2, "gpu_only_f16": 1}[a],
        ),
        reverse=True,
    )
    headline = ranked[0]
    u8 = per["gpu_only_u8"]
    u4 = per["gpu_only_u4"]
    em = paired["emission"]["gpu_only_u8__vs__gpu_only_u4"]["mcnemar"]
    cp = paired["completion"]["gpu_only_u8__vs__gpu_only_u4"]["mcnemar"]
    # first=u8, second=u4 in key gpu_only_u8__vs__gpu_only_u4
    # first_only = u8 pass / u4 fail; second_only = u8 fail / u4 pass
    # Pruning ("u8 dominated by u4") assumed quality-neutral. It does not survive
    # if u4 is significantly worse than u8 on emission or completion.
    u4_worse_em = em["first_only"] > em["second_only"] and float(em["p_value"]) < 0.05
    u4_worse_cp = cp["first_only"] > cp["second_only"] and float(cp["p_value"]) < 0.05
    pruning_survives = not (u4_worse_em or u4_worse_cp)
    # Also: if u8 clearly better on emission rate absolute and McNemar significant.
    lines = [
        report.rstrip(),
        "",
        "## H-1 headline config",
        "",
        f"Recommended KV arm for H-1 local quality: **`{headline}`** "
        f"(rank by emission_ok, then trajectory_pass, then denser KV as tie-break).",
        f"- u8 emission failures: {u8['emission_failures']}/200; "
        f"completion {u8['trajectory_pass']}/200",
        f"- u4 emission failures: {u4['emission_failures']}/200; "
        f"completion {u4['trajectory_pass']}/200",
        "",
        "## u8-dominated-by-u4 pruning",
        "",
        f"u4 significantly worse emission than u8 (McNemar): **{u4_worse_em}** "
        f"(p={em['p_value']:.6g}, u8_only={em['first_only']}, u4_only={em['second_only']})",
        f"u4 significantly worse completion than u8 (McNemar): **{u4_worse_cp}** "
        f"(p={cp['p_value']:.6g})",
        f"**Pruning survives: {pruning_survives}** "
        "(survives only if u4 is not significantly worse than u8 on emission or completion).",
        "",
        "## Predictions vs measured",
        "",
        f"Predicted failures f16/u8/u4: 45 / 65 / ≥65; "
        f"measured: {per['gpu_only_f16']['emission_failures']} / "
        f"{per['gpu_only_u8']['emission_failures']} / "
        f"{per['gpu_only_u4']['emission_failures']}.",
        f"Predicted completion f16/u8/u4: 20 / 14 / ≤14; "
        f"measured: {per['gpu_only_f16']['trajectory_pass']} / "
        f"{per['gpu_only_u8']['trajectory_pass']} / "
        f"{per['gpu_only_u4']['trajectory_pass']}.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
