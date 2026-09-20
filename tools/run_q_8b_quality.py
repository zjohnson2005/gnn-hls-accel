"""Q-8B: interleaved int4-4B vs int4-8B tier quality (fixed KV=f16).

Same 200 entries as W-3 / Q-KV. One session, block-interleaved arms so
machine state cannot explain arm differences. Placement: gpu_only_f16 for
both arms (KV f16 pinned; readback enforced).

This is a **tier comparison at fixed weight precision (int4)**.
Registry has no ``Qwen3-8B-int8-ov`` — do not silently substitute int8.
Model specs:
  int4_4B -> configs/models/Qwen3-4B-int4-ov.yaml
  int4_8B -> configs/models/Qwen3-8B-int4-ov.yaml
Quant recipe confound (stated, not papered over): 4B is INT4_SYM; 8B is
INT4_ASYM + scale_estimation (see FetchedModelSpec notes).

Predictions must already exist in derived/q8b/Q8B_PREDICTIONS.json.

Usage (default = single-pipe block interleave):
  .\\.venv-seam\\Scripts\\python.exe tools\\run_q_8b_quality.py --out derived/q8b/<run_id>
  # known-broken opt-in only:
  ... --allow-dual-resident
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

from seam.errors import SeamError  # noqa: E402
from seam.run_environment import RunEnvironmentSession  # noqa: E402
from tools.quality_row_persist import (  # noqa: E402
    DEGENERATE_CONSECUTIVE_N,
    DEGENERATE_CITING_RUN,
    DegenerateOutputGuard,
    persist_model_result_raw_per_turn,
)
from tools.run_h1_hybrid import (  # noqa: E402
    W3_ENTRIES_SHA256,
    W3_SEAL_REFS,
    assert_entry_set_matches_w3,
    assert_scorer_version,
    load_w3_entries,
)
from tools.run_q_kv_quality import (  # noqa: E402
    _contingency,
    _entry_emission_ok,
)

ARMS = ("int4_4B", "int4_8B")
PLACEMENT_ARM = "gpu_only_f16"
KV_EXPECTED = "f16"
ARM_MODEL_SPECS: dict[str, Path] = {
    "int4_4B": ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
    "int4_8B": ROOT / "configs" / "models" / "Qwen3-8B-int4-ov.yaml",
}
PRED_PATH = ROOT / "derived" / "q8b" / "Q8B_PREDICTIONS.json"
INTERLEAVE_SEED = 20260916
BLOCK_SIZE_DEFAULT = 5
# Dual-resident is known-broken on this iGPU (citing b1a291f0). Kept only behind
# an explicit opt-in flag; never the default.
DUAL_RESIDENT_KNOWN_BROKEN = True
DUAL_RESIDENT_CITING = "b1a291f0"


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
    if not pred.get("registered_utc"):
        raise SystemExit("REFUSED -- predictions missing registered_utc")
    if pred.get("weight_precision") != "int4":
        raise SystemExit(
            "REFUSED -- Q-8B is int4-vs-int4 tier; predictions.weight_precision must be int4"
        )
    if pred.get("no_int8_8b_in_registry") is not True:
        raise SystemExit(
            "REFUSED -- predictions must state no_int8_8b_in_registry=true "
            "(do not silently substitute int8)"
        )
    return pred


def _assert_kv_f16(meta: dict[str, Any], *, arm_id: str) -> dict[str, Any]:
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
        if not kv.get("match") or got != KV_EXPECTED:
            raise SystemExit(
                f"REFUSED -- KV_PRECISION_MISMATCH arm={arm_id} "
                f"expected={KV_EXPECTED!r} got={got!r} match={kv.get('match')!r}"
            )
        if not kv.get("enforced"):
            raise SystemExit(f"REFUSED -- {arm_id} KV pin not enforced; observed={kv!r}")
    return {"arm_id": arm_id, "expected": KV_EXPECTED, "loads": loads}


def _quality_row(row: dict[str, Any], *, arm_id: str) -> dict[str, Any]:
    score = row.get("score") if isinstance(row.get("score"), dict) else {}
    valid = score.get("valid")
    return {
        "entry_id": row.get("id"),
        "arm_id": arm_id,
        "tier": arm_id,
        "kv": KV_EXPECTED,
        "placement_arm": PLACEMENT_ARM,
        "model_spec": str(ARM_MODEL_SPECS[arm_id]),
        "trajectory_pass": bool(valid) if valid is not None else None,
        "score_error_type": score.get("error_type"),
        "score_error_message": score.get("error_message") or score.get("error"),
        "quality_scope": "local_probe",
        "model_result_decoded": row.get("model_result_decoded"),
        # Permanent: never drop raw (b1a291f0 diagnosis was blocked without it).
        "model_result_raw_per_turn": persist_model_result_raw_per_turn(row),
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


def _ledger_row(row: dict[str, Any], *, arm_id: str, arm_order: list[str]) -> dict[str, Any]:
    q = _quality_row(row, arm_id=arm_id)
    q.pop("model_result_decoded", None)
    turns = []
    for tm in row.get("turn_metrics") or []:
        turns.append(
            {
                "turn": tm.get("turn"),
                "n_decoded_steps": tm.get("n_decoded_steps"),
                "generated_tokens": tm.get("generated_tokens"),
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
    rng = random.Random(f"{seed}:q8b:{entry_id}")
    order = list(ARMS)
    rng.shuffle(order)
    return order


def analyze_paired(
    by_arm: dict[str, dict[str, dict[str, Any]]],
    entry_ids: list[str],
) -> dict[str, Any]:
    """Paired McNemar on emission_ok and trajectory_pass (4B vs 8B)."""
    a, b = ARMS
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
    em_a = [bool(by_arm[a][eid]["emission_ok"]) for eid in entry_ids]
    em_b = [bool(by_arm[b][eid]["emission_ok"]) for eid in entry_ids]
    cp_a = [bool(by_arm[a][eid].get("trajectory_pass")) for eid in entry_ids]
    cp_b = [bool(by_arm[b][eid].get("trajectory_pass")) for eid in entry_ids]
    key = f"{a}__vs__{b}"
    out["emission"][key] = _contingency(em_a, em_b)
    out["completion"][key] = _contingency(cp_a, cp_b)

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
        "tier_quality_axis_falsified": _agree(out["emission"]) and _agree(out["completion"]),
        "rule": (
            "Falsified if McNemar p>=0.05 (or 0 discordant) on BOTH emission and "
            "completion (int4-4B vs int4-8B agree within paired resolution)"
        ),
    }
    return out


def run_session(
    *,
    out_dir: Path,
    entries: list[dict[str, Any]],
    run_id: str,
    seal: bool,
    interleave_seed: int,
    allow_dual_resident: bool,
) -> dict[str, Any]:
    import openvino_genai as ov_genai

    import tools.bfcl_feasibility_probe as probe

    pred = _assert_predictions_pre_registered()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Gold selftest uses 4B tokenizer/path; entries are model-agnostic BFCL JSON.
    probe.apply_model_spec(ARM_MODEL_SPECS["int4_4B"])
    gold = probe.run_multi_turn_gold_selftest(entries)
    if int(gold.get("n_valid") or 0) != len(entries):
        raise SystemExit(
            f"REFUSED -- gold selftest {gold.get('n_valid')}/{gold.get('n')} "
            f"(need {len(entries)}/{len(entries)})"
        )
    _write_json(out_dir / "multi_turn_gold_selftest.json", gold)

    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = 512
    cfg.do_sample = False
    cfg.apply_chat_template = False

    avail0 = probe._host_available_mb()
    mb_start = avail0.get("available_mb")
    if mb_start is None:
        raise SystemExit("REFUSED -- available_mb_start unreadable at Q-8B session begin")
    env_session = RunEnvironmentSession.begin(
        session_design="interleaved",
        arm_order=list(ARMS),
        available_mb_start=float(mb_start),
        available_mb_start_method=str(avail0.get("available_method") or "probe._host_available_mb"),
    )

    pipes: dict[str, Any] = {}
    tokenizers: dict[str, Any] = {}
    load_metas: dict[str, Any] = {}
    kv_asserts: dict[str, Any] = {}
    reload_events: list[dict[str, Any]] = []
    # Default: single-pipe block interleave (Q8B-FIX). Dual-resident only behind
    # explicit --allow-dual-resident (known-broken on this iGPU; citing b1a291f0).
    pipeline_mode = "block_interleave_single_pipe"
    block_size = BLOCK_SIZE_DEFAULT

    def _bind_arm(arm_id: str) -> Path:
        spec = ARM_MODEL_SPECS[arm_id]
        probe.apply_model_spec(spec)
        return spec

    def _load_one(arm_id: str, *, reason: str) -> None:
        spec = _bind_arm(arm_id)
        t0 = time.perf_counter()
        pipe, meta, load_s = probe.load_arm_pipeline(PLACEMENT_ARM, enable_prefix_caching=None)
        wall = time.perf_counter() - t0
        kv_asserts[arm_id] = _assert_kv_f16(meta, arm_id=arm_id)
        pipes[arm_id] = pipe
        tokenizers[arm_id] = probe._hf_tokenizer()
        load_metas[arm_id] = {
            **meta,
            "load_s": load_s,
            "load_wall_s": wall,
            "model_spec": str(spec),
            "placement_arm": PLACEMENT_ARM,
        }
        ev = {
            "event": "model_load",
            "arm_id": arm_id,
            "model_spec": str(spec),
            "reason": reason,
            "load_s": load_s,
            "load_wall_s": wall,
            "excluded_from_decode_metrics": True,
            "utc": _utc_now(),
        }
        reload_events.append(ev)
        _write_json(out_dir / "reload_events.json", {"events": reload_events})
        print(
            f"LOAD_ARM_OK {arm_id} load_s={load_s:.2f} wall_s={wall:.2f} reason={reason}",
            flush=True,
        )

    def _drop_all() -> None:
        pipes.clear()
        tokenizers.clear()
        import gc

        gc.collect()

    if allow_dual_resident:
        print(
            "WARN --allow-dual-resident: KNOWN-BROKEN on this iGPU "
            f"(citing {DUAL_RESIDENT_CITING}); dual 4B+8B corrupts pipeline "
            "state after a few cells → exact 512-token empty burns",
            flush=True,
        )
        reload_events.append(
            {
                "event": "dual_resident_opt_in",
                "known_broken": True,
                "citing": DUAL_RESIDENT_CITING,
                "excluded_from_decode_metrics": True,
                "utc": _utc_now(),
            }
        )
        try:
            for arm_id in ARMS:
                print(f"LOAD_ARM {arm_id} (dual-resident explicit opt-in) …", flush=True)
                _load_one(arm_id, reason="dual_resident_opt_in")
            pipeline_mode = "dual_resident"
            block_size = 1
        except Exception as exc:
            print(
                f"DUAL_LOAD_FAILED {type(exc).__name__}: {exc}; "
                "using block_interleave_single_pipe (explicit; not silent)",
                flush=True,
            )
            _drop_all()
            pipeline_mode = "block_interleave_single_pipe"
            block_size = BLOCK_SIZE_DEFAULT
            reload_events.append(
                {
                    "event": "dual_resident_abandoned",
                    "verbatim": f"{type(exc).__name__}: {exc}",
                    "excluded_from_decode_metrics": True,
                    "utc": _utc_now(),
                }
            )
            _write_json(out_dir / "reload_events.json", {"events": reload_events})
    else:
        print(
            "PIPELINE_MODE block_interleave_single_pipe "
            "(default; dual-resident requires --allow-dual-resident)",
            flush=True,
        )
        reload_events.append(
            {
                "event": "pipeline_mode_selected",
                "pipeline_mode": pipeline_mode,
                "reason": "default_single_pipe_block_interleave",
                "dual_resident_known_broken": DUAL_RESIDENT_KNOWN_BROKEN,
                "dual_resident_citing": DUAL_RESIDENT_CITING,
                "excluded_from_decode_metrics": True,
                "utc": _utc_now(),
            }
        )
        _write_json(out_dir / "reload_events.json", {"events": reload_events})

    plan = {
        "kind": "q_8b_quality",
        "run_id": run_id,
        "measurement_kind": "MEASURED",
        "cloud_usd": 0.0,
        "arms": list(ARMS),
        "arm_model_specs": {k: str(v) for k, v in ARM_MODEL_SPECS.items()},
        "placement_arm": PLACEMENT_ARM,
        "kv_expected": KV_EXPECTED,
        "weight_precision": "int4",
        "no_int8_8b_in_registry": True,
        "quant_recipe_confound": {
            "int4_4B": "INT4_SYM",
            "int4_8B": "INT4_ASYM + scale_estimation (wikitext2)",
            "note": (
                "Tier comparison at fixed int4 weight precision; size confounded "
                "with quant recipe. Stated, not silently ignored."
            ),
        },
        "residency": "RESIDENT",
        "max_new_tokens": 512,
        "do_sample": False,
        "n_entries": len(entries),
        "w3_entry_pin": W3_ENTRIES_SHA256,
        "w3_seal_refs": list(W3_SEAL_REFS),
        "scorer": assert_scorer_version(),
        "interleave_seed": interleave_seed,
        "pipeline_mode": pipeline_mode,
        "block_size": block_size,
        "allow_dual_resident": bool(allow_dual_resident),
        "dual_resident_known_broken": DUAL_RESIDENT_KNOWN_BROKEN,
        "dual_resident_citing": DUAL_RESIDENT_CITING,
        "degenerate_guard": {
            "consecutive_n": DEGENERATE_CONSECUTIVE_N,
            "citing": DEGENERATE_CITING_RUN,
            "rule": "max_new_tokens burn with zero decodable steps",
        },
        "available_mb_start": avail0,
        "session_design": "interleaved",
        "arm_order": list(ARMS),
        "run_environment": {
            "available_mb_start": float(mb_start),
            "session_design": "interleaved",
            "arm_order": list(ARMS),
        },
        "interleave": (
            "per_entry_shuffle_dual_resident_pipes"
            if pipeline_mode == "dual_resident"
            else f"block_size={block_size}_arm_grouped_within_block_reload_on_switch"
        ),
        "reload_timing": {
            "recorded_in": "reload_events.json",
            "contaminates_cell_wall": False,
            "contaminates_turn_ttft_decode": False,
            "note": (
                "load_s / load_wall_s are separate events; cell_wall and turn "
                "ttft_s/decode_tok_s start after the active pipe is ready."
            ),
        },
        "predictions_path": str(PRED_PATH),
        "predictions_registered_utc": pred.get("registered_utc"),
        "q_kv_baseline": pred.get("q_kv_baseline"),
        "kv_readback_assert": kv_asserts,
        "load_metas": {k: v for k, v in load_metas.items()},
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
    current_arm: str | None = None
    deg_guard = DegenerateOutputGuard(max_new_tokens=int(cfg.max_new_tokens))

    def _ensure_arm(arm_id: str) -> None:
        nonlocal current_arm
        if arm_id in pipes and pipes[arm_id] is not None:
            # Re-bind globals so path asserts match the active IR.
            _bind_arm(arm_id)
            current_arm = arm_id
            return
        if pipeline_mode == "dual_resident":
            raise SystemExit(f"REFUSED -- dual mode missing pipe for {arm_id}")
        # Block-interleave: drop other arm, load this one (reload cost recorded).
        prev = current_arm
        _drop_all()
        print(
            f"LOAD_ARM {arm_id} (block-interleave switch from={prev}) …",
            flush=True,
        )
        _load_one(arm_id, reason=f"switch_from_{prev}")
        current_arm = arm_id
        _write_json(out_dir / "kv_readback_live.json", kv_asserts)

    def _run_cell(entry: dict[str, Any], arm_id: str, order: list[str]) -> None:
        eid = str(entry["id"])
        if (eid, arm_id) in done:
            print(f"SKIP {eid} {arm_id}", flush=True)
            return
        _ensure_arm(arm_id)
        print(f"CELL_START entry={eid} arm={arm_id} order={order}", flush=True)
        # Timing starts AFTER reload; load cost lives only in reload_events.
        t0 = time.perf_counter()
        row = probe.run_multi_turn_agent_entry(
            pipe=pipes[arm_id],
            tokenizer=tokenizers[arm_id],
            cfg=cfg,
            entry=entry,
            residency_mode="RESIDENT",
            ov_genai=ov_genai,
        )
        wall = time.perf_counter() - t0
        row["arm_id"] = arm_id
        row["kv"] = KV_EXPECTED
        led = _ledger_row(row, arm_id=arm_id, arm_order=order)
        led["cell_wall_s"] = wall
        led["reload_excluded_from_cell_wall"] = True
        digest = row.get("prompt_render_sha256")
        if isinstance(digest, str) and len(digest) == 64:
            led["prompt_render_sha256"] = digest
            env_session.add_prompt_digest(digest)
        qrow = _quality_row(row, arm_id=arm_id)
        deg = deg_guard.observe(row, entry_id=eid, arm_id=arm_id)
        qrow["degenerate_max_burn"] = bool(deg["degenerate_max_burn"])
        led["degenerate_max_burn"] = bool(deg["degenerate_max_burn"])
        by_arm[arm_id][eid] = led
        quality_rows.append(qrow)
        cell_log.append(
            {
                "entry_id": eid,
                "arm_id": arm_id,
                "kv": KV_EXPECTED,
                "arm_order": order,
                "wall_s": wall,
                "emission_ok": led["emission_ok"],
                "trajectory_pass": led["trajectory_pass"],
                "degenerate_max_burn": bool(deg["degenerate_max_burn"]),
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
            f"degenerate={deg['degenerate_max_burn']}",
            flush=True,
        )
        deg_guard.raise_if_refused()

    status = "complete"
    abort_reason: str | None = None
    abort_verbatim: str | None = None
    summary_out: dict[str, Any] | None = None

    try:
        if pipeline_mode == "dual_resident":
            for entry in entries:
                eid = str(entry["id"])
                order = _arm_order_for_entry(eid, seed=interleave_seed)
                for arm_id in order:
                    _run_cell(entry, arm_id, order)
        else:
            for block_start in range(0, len(entries), block_size):
                block = entries[block_start : block_start + block_size]
                rng = random.Random(f"{interleave_seed}:q8b:block:{block_start}")
                arm_cycle = list(ARMS)
                rng.shuffle(arm_cycle)
                for arm_id in arm_cycle:
                    for entry in block:
                        eid = str(entry["id"])
                        order = _arm_order_for_entry(eid, seed=interleave_seed)
                        _run_cell(entry, arm_id, order)

        missing = [
            (eid, arm)
            for eid in entry_ids
            for arm in ARMS
            if eid not in by_arm[arm]
        ]
        if missing:
            raise SystemExit(f"REFUSED -- incomplete matrix; missing {len(missing)} cells")

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
        plan["pipeline_mode"] = pipeline_mode
        plan["kv_readback_assert"] = kv_asserts
        plan["load_metas"] = {k: v for k, v in load_metas.items()}
        _write_json(out_dir / "plan.json", plan)
        _write_json(out_dir / "reload_events.json", {"events": reload_events})

        summary_out = {
            "kind": "q_8b_quality",
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
            "pipeline_mode": pipeline_mode,
            "n_reload_events": len(
                [e for e in reload_events if e.get("event") == "model_load"]
            ),
            "predictions_registered_utc": pred.get("registered_utc"),
            "scorer": assert_scorer_version(),
            "session_design": "interleaved",
            "arm_order": list(ARMS),
            "available_mb_start": run_environment["available_mb_start"],
            "available_mb_end": run_environment["available_mb_end"],
            "prompt_render_sha256": run_environment["prompt_render_sha256"],
            "run_environment": run_environment,
        }
    except BaseException as exc:
        status = "aborted"
        abort_reason = type(exc).__name__
        abort_verbatim = str(exc)
        raise
    finally:
        if summary_out is None:
            partial_env = plan.get("run_environment") or {
                "available_mb_start": float(mb_start),
                "session_design": "interleaved",
                "arm_order": list(ARMS),
            }
            summary_out = {
                "kind": "q_8b_quality",
                "run_id": run_id,
                "status": status,
                "abort_reason": abort_reason,
                "abort_verbatim": abort_verbatim,
                "measurement_kind": "MEASURED",
                "cloud_usd": 0.0,
                "n_entries": len(entry_ids),
                "n_cells_completed": len(done),
                "n_cells_planned": len(entry_ids) * len(ARMS),
                "session_wall_s": time.perf_counter() - t_session0,
                "finished_utc": _utc_now(),
                "pipeline_mode": pipeline_mode,
                "predictions_registered_utc": pred.get("registered_utc"),
                "session_design": "interleaved",
                "arm_order": list(ARMS),
                "available_mb_start": partial_env.get("available_mb_start"),
                "available_mb_end": partial_env.get("available_mb_end"),
                "run_environment": partial_env,
                "completed_cells": sorted([list(x) for x in done]),
                "degenerate_flagged": list(deg_guard.flagged),
            }
            plan["status"] = status
            plan["abort_reason"] = abort_reason
            plan["abort_verbatim"] = abort_verbatim
            _write_json(out_dir / "plan.json", plan)
            _write_json(out_dir / "reload_events.json", {"events": reload_events})
        _write_json(out_dir / "summary.json", summary_out)
        _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
        _write_json(out_dir / "turn_ledger.json", {"by_arm": by_arm, "entry_ids": entry_ids})
        _write_json(out_dir / "cell_log.json", {"cells": cell_log})

    assert summary_out is not None
    summary = summary_out

    if seal and status == "complete":
        tree = _sha256_tree(out_dir, exclude={".sealed"})
        seal_doc = {
            "run_id": run_id,
            "kind": "q_8b_quality",
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
        "# Q-8B results (int4-4B vs int4-8B, KV=f16, interleaved)",
        "",
        f"run_id: `{summary.get('run_id')}`",
        f"pipeline_mode: `{summary.get('pipeline_mode')}`",
        f"session_wall_s: {summary.get('session_wall_s')}",
        f"tree_sha256: `{summary.get('tree_sha256')}`",
        "",
        "## Tier note",
        "",
        "Fixed weight precision **int4**. No `Qwen3-8B-int8-ov` in registry — "
        "not an int8 substitution. Quant recipe confound: 4B INT4_SYM vs 8B INT4_ASYM.",
        "",
        "## Q-KV f16 baseline (cross-session absolute rates not comparable)",
        "",
        f"Cited for prediction context only: run `{pred.get('q_kv_baseline', {}).get('run_id')}` "
        f"gpu_only_f16 emission failures "
        f"{pred.get('q_kv_baseline', {}).get('emission_failures')}/200, "
        f"trajectory_pass {pred.get('q_kv_baseline', {}).get('trajectory_pass')}/200.",
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
        f"- emission arms agree: **{fals['emission_arms_agree']}**",
        f"- completion arms agree: **{fals['completion_arms_agree']}**",
        f"- tier quality-axis hypothesis falsified: **{fals['tier_quality_axis_falsified']}**",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Q-8B interleaved int4 tier quality")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--entries", type=Path, default=None)
    p.add_argument("--interleave-seed", type=int, default=INTERLEAVE_SEED)
    p.add_argument("--seal", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--allow-dual-resident",
        action="store_true",
        help=(
            "KNOWN-BROKEN on this iGPU (citing b1a291f0): keep both 4B and 8B "
            "pipes resident. Default is single-pipe block interleave with reload."
        ),
    )
    p.add_argument(
        "--force-block-interleave",
        action="store_true",
        help=(
            "Deprecated no-op: single-pipe block interleave is already the default. "
            "Retained so old launchers do not error."
        ),
    )
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
        (out / "Q8B_RESULTS.md").write_text(report, encoding="utf-8")
        print(report)
        return 0

    pred = _assert_predictions_pre_registered()
    run_id = args.run_id or str(uuid.uuid4())
    out_dir = args.out
    entries, entries_path = load_w3_entries(args.entries)
    assert_entry_set_matches_w3(entries_path)
    if len(entries) != 200:
        raise SystemExit(f"REFUSED -- need 200 entries, got {len(entries)}")

    print(f"Q8B_START run_id={run_id} out={out_dir}", flush=True)
    if args.force_block_interleave:
        print(
            "NOTE --force-block-interleave is deprecated (default is already "
            "single-pipe); ignoring",
            flush=True,
        )
    summary = run_session(
        out_dir=out_dir,
        entries=entries,
        run_id=run_id,
        seal=bool(args.seal),
        interleave_seed=int(args.interleave_seed),
        allow_dual_resident=bool(args.allow_dual_resident),
    )
    paired = json.loads((out_dir / "paired_analysis.json").read_text(encoding="utf-8-sig"))
    report = build_report(summary, paired, pred)
    (out_dir / "Q8B_RESULTS.md").write_text(report, encoding="utf-8")
    (ROOT / "derived" / "q8b" / "Q8B_RESULTS.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
