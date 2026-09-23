"""DET-PROBE: turn-0 TTFT and output-token hashes, local only.

Pre-registration: derived/h1_hybrid/DET_PROBE_PREREG.json (must be committed
and clean before the first generate). No cloud calls.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
import time
import uuid
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREREG = ROOT / "derived" / "h1_hybrid" / "DET_PROBE_PREREG.json"
W3_ENTRIES = (
    ROOT
    / "derived"
    / "bfcl_feasibility"
    / "w3_weight_quality"
    / "sealed_6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a"
    / "artifacts"
    / "multi_turn_probe_entries.json"
)
MODEL_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
N_ENTRIES = 20
MAX_NEW = 512


def _git_bytes(args: list[str]) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(f"REFUSED -- git {' '.join(args)} failed: {err}")
    return proc.stdout


def _require_committed_prereg() -> str:
    if not PREREG.is_file():
        raise SystemExit(f"REFUSED -- missing prereg {PREREG}")
    dirty = _git_bytes(["status", "--porcelain", "--", str(PREREG)]).decode("utf-8")
    if dirty.strip():
        raise SystemExit("REFUSED -- DET_PROBE_PREREG.json is not a clean committed file")
    rev = _git_bytes(["log", "-1", "--format=%H", "--", str(PREREG)]).decode("utf-8").strip()
    if not rev:
        raise SystemExit("REFUSED -- DET_PROBE_PREREG.json is not committed")
    return rev


def _run_gates(out_dir: Path) -> Path:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "seam.measurement_gates",
            "--repo-root",
            str(ROOT),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    gate_path = out_dir / "gates.json"
    gate_path.write_text(proc.stdout or proc.stderr, encoding="utf-8")
    print(proc.stdout, flush=True)
    if proc.returncode != 0:
        err = (proc.stderr or "")[-2000:]
        raise SystemExit(f"REFUSED -- measurement gates failed (exit {proc.returncode}). {err}")
    return gate_path


def _turn0_messages(entry: dict[str, Any]) -> list[dict[str, Any]]:
    question = entry["question"][0]
    if isinstance(question, dict):
        return [dict(question)]
    return [dict(m) for m in question if isinstance(m, dict)]


def _finish_chat(pipe: Any) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pipe.finish_chat()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _cfg(ov_genai: Any, decoding: str) -> Any:
    import tools.bfcl_feasibility_probe as probe

    if decoding == "harness_default":
        return probe._generation_cfg(ov_genai, max_new_tokens=MAX_NEW, apply_chat_template=True)
    if decoding != "greedy":
        raise SystemExit(f"REFUSED -- unknown decoding {decoding!r}")
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = MAX_NEW
    cfg.do_sample = False
    cfg.apply_chat_template = True
    return cfg


def _output_ids(result: Any, text: str, hf_tokenizer: Any) -> tuple[list[int], str]:
    raw = getattr(result, "tokens", None)
    if raw is not None:
        try:
            ids = [int(x) for x in raw]
        except (TypeError, ValueError):
            ids = []
        if ids:
            return ids, "result.tokens"
    encoded = hf_tokenizer(text, add_special_tokens=False)["input_ids"]
    return [int(x) for x in encoded], "hf_tokenizer_text"


def _sha256_ids(ids: list[int]) -> str:
    payload = json.dumps(ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _generate(pipe: Any, ov_genai: Any, history: Any, cfg: Any, hf_tokenizer: Any) -> dict[str, Any]:
    from seam.backends.local_openvino import (
        _extract_metrics,
        _make_ttft_streamer,
        resolve_ttft_ns,
    )

    streamer = _make_ttft_streamer(ov_genai)
    t0 = time.perf_counter_ns()
    streamer.t0_ns = t0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = pipe.generate(history, cfg, streamer)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "ttft_s": None,
            "output_token_sha256": None,
            "n_output_tokens": None,
            "token_id_source": None,
        }
    texts = getattr(result, "texts", None)
    text = str(texts[0]) if texts else str(result)
    metrics = getattr(result, "perf_metrics", None)
    metrics_ttft_ns, _prompt_tokens, _generated = _extract_metrics(metrics)
    ttft_ns, ttft_source = resolve_ttft_ns(metrics_ttft_ns, streamer.ttft_ns)
    ids, source = _output_ids(result, text, hf_tokenizer)
    ttft_s = (ttft_ns / 1e9) if ttft_ns else None
    return {
        "ok": True,
        "error": None,
        "ttft_s": ttft_s,
        "ttft_source": ttft_source,
        "output_token_sha256": _sha256_ids(ids),
        "n_output_tokens": len(ids),
        "token_id_source": source,
    }


def _load(enable_prefix_caching: bool | None) -> tuple[Any, Any, Any, dict[str, Any]]:
    import openvino_genai as ov_genai

    import tools.bfcl_feasibility_probe as probe

    probe.apply_model_spec(MODEL_SPEC)
    pipe, meta, load_s = probe.load_arm_pipeline(
        "gpu_only_u8",
        enable_prefix_caching=enable_prefix_caching,
    )
    meta = dict(meta)
    meta["load_s"] = load_s
    hf = probe._hf_tokenizer()
    return pipe, ov_genai, hf, meta


def _run_condition(
    *,
    pipe: Any,
    ov_genai: Any,
    hf: Any,
    entries: list[dict[str, Any]],
    condition: str,
    decoding: str,
    flush: bool,
    sink: Any,
) -> list[dict[str, Any]]:
    import tools.bfcl_feasibility_probe as probe

    rows: list[dict[str, Any]] = []
    if condition == "harness_default_noflush":
        between = _finish_chat(pipe)
        print(f"BETWEEN_CONDITIONS finish_chat={between}", flush=True)
    for entry in entries:
        eid = str(entry["id"])
        messages = _turn0_messages(entry)
        tools = probe.tools_for_entry(entry)
        cfg = _cfg(ov_genai, decoding)
        for call_i in (1, 2, 3):
            finish_err = _finish_chat(pipe) if flush else None
            history = probe.build_bfcl_chat_history(ov_genai, messages, tools)
            t0 = time.perf_counter()
            rec = _generate(pipe, ov_genai, history, cfg, hf)
            rec.update(
                {
                    "entry_id": eid,
                    "condition": condition,
                    "call": call_i,
                    "flush": flush,
                    "decoding": decoding,
                    "finish_chat_error": finish_err,
                    "wall_s": time.perf_counter() - t0,
                }
            )
            rows.append(rec)
            sink.write(json.dumps(rec, sort_keys=True) + "\n")
            sink.flush()
            print(
                f"{condition} {eid} call={call_i} ok={rec['ok']} "
                f"ttft_s={rec['ttft_s']} sha={rec['output_token_sha256']}",
                flush=True,
            )
    return rows


def _median(vals: list[float]) -> float | None:
    return statistics.median(vals) if vals else None


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by.setdefault(str(row["condition"]), []).append(row)
    out: dict[str, Any] = {}
    for condition, group in by.items():
        per_entry: dict[str, list[dict[str, Any]]] = {}
        for row in group:
            per_entry.setdefault(str(row["entry_id"]), []).append(row)
        n_entries = len(per_entry)
        all_equal = 0
        match_call1 = 0
        match_call1_n = 0
        ttft_by_call: dict[int, list[float]] = {1: [], 2: [], 3: []}
        ttft_all: list[float] = []
        for _eid, calls in per_entry.items():
            calls_sorted = sorted(calls, key=lambda r: int(r["call"]))
            shas = [c.get("output_token_sha256") for c in calls_sorted]
            oks = [bool(c.get("ok")) for c in calls_sorted]
            if len(shas) == 3 and all(oks) and shas[0] == shas[1] == shas[2]:
                all_equal += 1
            if len(calls_sorted) == 3 and oks[0]:
                for later in calls_sorted[1:]:
                    match_call1_n += 1
                    if later.get("ok") and later.get("output_token_sha256") == shas[0]:
                        match_call1 += 1
            for c in calls_sorted:
                if c.get("ttft_s") is not None:
                    ttft_all.append(float(c["ttft_s"]))
                    ttft_by_call[int(c["call"])].append(float(c["ttft_s"]))
        first_id = next(iter(per_entry))
        first_calls = sorted(per_entry[first_id], key=lambda r: int(r["call"]))
        out[condition] = {
            "n_entries": n_entries,
            "n_calls": len(group),
            "n_ok": sum(1 for r in group if r.get("ok")),
            "hash_all_three_equal_rate": (all_equal / n_entries) if n_entries else None,
            "hash_match_call1_rate": (match_call1 / match_call1_n) if match_call1_n else None,
            "ttft_median_s": _median(ttft_all),
            "ttft_median_by_call_s": {str(k): _median(v) for k, v in ttft_by_call.items()},
            "first_entry_id": first_id,
            "first_entry_ttft_s": [c.get("ttft_s") for c in first_calls],
            "first_entry_sha256": [c.get("output_token_sha256") for c in first_calls],
        }
    return out


def capture_run_git(*, allow_dirty: bool = False, root: Path | None = None) -> dict[str, Any]:
    """HEAD, dirty flag, and sha256 of ``git diff HEAD``. A dirty tree is refused."""
    from seam.errors import DirtyTreeError
    from tools.h1_seal_git import seal_git_record

    try:
        return seal_git_record(allow_dirty=allow_dirty, root=root or ROOT)
    except DirtyTreeError as exc:
        raise SystemExit(f"REFUSED -- {exc}") from exc


def main() -> int:
    git_rec = capture_run_git(allow_dirty=False)
    from seam.locks import ExclusiveLock

    # After the clean-tree check. A lock file created earlier would itself dirty the tree.
    with ExclusiveLock(ROOT / ".locks" / "machine.lock"):
        return _main_body(git_rec)


def _main_body(git_rec: dict[str, Any]) -> int:
    prereg_rev = _require_committed_prereg()
    run_id = str(uuid.uuid4())
    out_dir = ROOT / "derived" / "h1_hybrid" / f"det_probe_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=False)
    print(f"RUN_ID {run_id}", flush=True)
    print(f"OUT {out_dir}", flush=True)
    gate_path = _run_gates(out_dir)
    print(f"GATES_PASS {gate_path}", flush=True)

    entries_all = json.loads(W3_ENTRIES.read_text(encoding="utf-8-sig"))
    entries = list(entries_all[:N_ENTRIES])
    if len(entries) != N_ENTRIES:
        raise SystemExit(f"REFUSED -- expected {N_ENTRIES} entries, got {len(entries)}")

    plan = {
        "run_id": run_id,
        "prereg": str(PREREG.relative_to(ROOT)).replace("\\", "/"),
        "prereg_git": prereg_rev,
        "n_entries": N_ENTRIES,
        "entry_ids": [str(e["id"]) for e in entries],
        "model_spec": str(MODEL_SPEC.relative_to(ROOT)).replace("\\", "/"),
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "kv": "u8",
        "max_new_tokens": MAX_NEW,
        "cloud": False,
        "git": git_rec,
    }
    (out_dir / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rows: list[dict[str, Any]] = []
    calls_path = out_dir / "calls.jsonl"
    with calls_path.open("w", encoding="utf-8") as sink:
        print("LOAD flush pipeline enable_prefix_caching=False", flush=True)
        pipe, ov_genai, hf, meta_off = _load(False)
        (out_dir / "load_flush.json").write_text(
            json.dumps(meta_off, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        for condition, decoding in (
            ("greedy_flush", "greedy"),
            ("harness_default_flush", "harness_default"),
        ):
            rows.extend(
                _run_condition(
                    pipe=pipe,
                    ov_genai=ov_genai,
                    hf=hf,
                    entries=entries,
                    condition=condition,
                    decoding=decoding,
                    flush=True,
                    sink=sink,
                )
            )
        del pipe
        print("LOAD noflush pipeline SchedulerConfig omitted", flush=True)
        pipe, ov_genai, hf, meta_on = _load(None)
        (out_dir / "load_noflush.json").write_text(
            json.dumps(meta_on, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        for condition, decoding in (
            ("greedy_noflush", "greedy"),
            ("harness_default_noflush", "harness_default"),
        ):
            rows.extend(
                _run_condition(
                    pipe=pipe,
                    ov_genai=ov_genai,
                    hf=hf,
                    entries=entries,
                    condition=condition,
                    decoding=decoding,
                    flush=False,
                    sink=sink,
                )
            )
        del pipe

    summary = {
        "run_id": run_id,
        "prereg_git": prereg_rev,
        "conditions": _summarize(rows),
    }
    (out_dir / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary["conditions"], indent=2), flush=True)
    print(f"DONE {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
