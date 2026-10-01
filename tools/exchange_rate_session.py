"""P0 exchange-rate session. Gates, canary, seal, hang reaper.

Does not open a preregistration or an amendment file. Lengths and the budget
come from configs/exchange_rate.yaml.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.boot4_session import (  # noqa: E402
    _canary_model,
    _child_spec,
    _finish,
    _open_canary,
    _publish_cell_status,
    _utc,
    _write,
    cell_exit_code,
    load_harness,
    new_session_id,
    require_gates,
)

_CONFIG_PATH = ROOT / "configs" / "exchange_rate.yaml"
_REQUIRED = (
    "budget_s",
    "context_tokens",
    "smoke_context_tokens",
    "concurrencies",
    "smoke_concurrencies",
    "decode_new_tokens",
    "smoke_decode_new_tokens",
    "smoke_budget_s",
    "tta_max_new_tokens",
    "repeats",
    "devices",
    "enable_prefix_caching",
    "max_num_seqs",
    "max_num_batched_tokens",
    "model_spec",
)


def load_exchange_config() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        raise SystemExit(f"REFUSED -- missing {_CONFIG_PATH}")
    loaded = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit("REFUSED -- exchange_rate.yaml is not a mapping")
    missing = [key for key in _REQUIRED if key not in loaded]
    if missing:
        raise SystemExit("REFUSED -- exchange_rate.yaml missing " + ", ".join(missing))
    return loaded


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2.0


def _exchange_spec(base: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    spec = dict(base)
    device = plan["device"]
    kv = device.get("kv_cache_precision")
    if kv:
        sequence = []
        for entry in spec["load_sequence"]:
            props = dict(entry.get("properties") or {})
            props["KV_CACHE_PRECISION"] = str(kv)
            sequence.append({**entry, "properties": props})
        spec["load_sequence"] = sequence
    spec["exchange"] = {
        "context_tokens": int(plan["context_tokens"]),
        "concurrencies": [int(item) for item in plan["concurrencies"]],
        "decode_new_tokens": int(plan["decode_new_tokens"]),
        "budget_s": float(plan["budget_s"]),
        "tta_max_new_tokens": int(plan["tta_max_new_tokens"]),
        "enable_prefix_caching": bool(plan["enable_prefix_caching"]),
        "max_num_seqs": int(plan["max_num_seqs"]),
        "max_num_batched_tokens": int(plan["max_num_batched_tokens"]),
        "salt": str(plan["salt"]),
    }
    return spec


def _run_one(
    *,
    harness: dict[str, Any],
    cfg: dict[str, Any],
    device: dict[str, Any],
    work: Path,
    context_tokens: int,
    concurrencies: list[int],
    decode_new_tokens: int,
    budget_s: float,
    tag: str,
) -> dict[str, Any]:
    from seam.tools.delta_n import run_child

    base = _child_spec(harness, str(device["arm"]), work)
    spec = _exchange_spec(
        base,
        {
            "device": device,
            "context_tokens": context_tokens,
            "concurrencies": concurrencies,
            "decode_new_tokens": decode_new_tokens,
            "budget_s": budget_s,
            "tta_max_new_tokens": cfg["tta_max_new_tokens"],
            "enable_prefix_caching": cfg["enable_prefix_caching"],
            "max_num_seqs": cfg["max_num_seqs"],
            "max_num_batched_tokens": cfg["max_num_batched_tokens"],
            "salt": tag,
        },
    )
    command = [
        sys.executable,
        "-u",
        "-m",
        "seam.tools._exchange_rate_child",
        "--spec",
        str(work / f"{tag}.spec.json"),
        "--out",
        str(work / f"{tag}.result.json"),
    ]
    return run_child(
        root=ROOT,
        work_dir=work,
        spec=spec,
        timeout_s=float(harness["cfg"]["generation"]["timeout_s"]),
        tag=tag,
        command=command,
    )


def _point_from_record(
    record: dict[str, Any], *, device_id: str, n_tokens: int, repeat: int
) -> dict[str, Any]:
    child = record.get("child") or {}
    return {
        "device": device_id,
        "n": n_tokens,
        "repeat": repeat,
        "outcome": record.get("outcome"),
        "failure_kind": record.get("failure_mode") if record.get("outcome") != "pass" else None,
        "hung_after_result": record.get("hung_after_result"),
        "hang_duration_s": record.get("hang_duration_s"),
        "hang_disposition": record.get("hang_disposition"),
        "probes": child.get("probes") or [],
    }


def _measured_table(points: list[dict[str, Any]], *, budget_s: float) -> list[dict[str, Any]]:
    from seam.tools.exchange_rate_table import what_fits

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for point in points:
        if point.get("outcome") != "pass":
            continue
        grouped.setdefault((str(point["device"]), int(point["n"])), []).append(point)
    rows: list[dict[str, Any]] = []
    for (device, n_tokens), group in sorted(grouped.items()):
        prefills: list[float] = []
        decodes: list[float] = []
        thinking: list[float] = []
        retry_prefills: list[float] = []
        retry_decodes: list[float] = []
        ttas: list[float] = []
        tool_tokens: list[float] = []
        batch4: list[float] = []
        batch1: list[float] = []
        for point in group:
            for probe in point["probes"]:
                name = str(probe.get("name"))
                if name == "batch-1" and probe.get("prefill_s") is not None:
                    prefills.append(float(probe["prefill_s"]))
                if name == "batch-1" and probe.get("decode_tok_s") is not None:
                    decodes.append(float(probe["decode_tok_s"]))
                    batch1.append(float(probe["decode_tok_s"]))
                if name == "batch-4" and probe.get("decode_tok_s") is not None:
                    batch4.append(float(probe["decode_tok_s"]))
                if name == "thinking" and probe.get("decode_tok_s") is not None:
                    thinking.append(float(probe["decode_tok_s"]))
                if name == "retry" and probe.get("prefill_s") is not None:
                    retry_prefills.append(float(probe["prefill_s"]))
                if name == "retry" and probe.get("decode_tok_s") is not None:
                    retry_decodes.append(float(probe["decode_tok_s"]))
                if name == "greedy_tta" and probe.get("tta_s") is not None:
                    ttas.append(float(probe["tta_s"]))
                if (
                    name == "greedy_tta"
                    and probe.get("parsed_tool_call")
                    and probe.get("completion_tokens") is not None
                ):
                    tool_tokens.append(float(probe["completion_tokens"]))
        prefill = _median(prefills)
        decode = _median(decodes)
        tools = _median(tool_tokens)
        fit = None
        if prefill is not None and decode is not None and tools is not None:
            fit = what_fits(
                budget_s=budget_s,
                prefill_s=prefill,
                decode_tok_s=decode,
                tool_tokens=tools,
            )
        ratio = None
        if _median(batch1) not in (None, 0.0) and _median(batch4) is not None:
            ratio = float(_median(batch4) or 0.0) / float(_median(batch1) or 1.0)
        rows.append(
            {
                "device": device,
                "n": n_tokens,
                "prefill_s_median": prefill,
                "decode_tok_s_median": decode,
                "thinking_tok_s_median": _median(thinking),
                "retry_prefill_s_median": _median(retry_prefills),
                "retry_decode_tok_s_median": _median(retry_decodes),
                "greedy_tta_s_median": _median(ttas),
                "batch4_over_batch1": ratio,
                "what_fits": fit,
            }
        )
    return rows


def run_exchange_rate_smoke(*, model_spec: Path) -> int:
    cfg = load_exchange_config()
    harness = load_harness(model_spec)
    device = next(item for item in cfg["devices"] if item["id"] == "gpu")
    with tempfile.TemporaryDirectory(prefix="exchange-rate-smoke-") as tmp:
        record = _run_one(
            harness=harness,
            cfg=cfg,
            device=device,
            work=Path(tmp),
            context_tokens=int(cfg["smoke_context_tokens"]),
            concurrencies=[int(item) for item in cfg["smoke_concurrencies"]],
            decode_new_tokens=int(cfg["smoke_decode_new_tokens"]),
            budget_s=float(cfg["smoke_budget_s"]),
            tag="smoke",
        )
    print(
        json.dumps(
            {
                "event": "exchange_rate_smoke",
                "arm": device["arm"],
                "outcome": record.get("outcome"),
                "context_tokens": int(cfg["smoke_context_tokens"]),
                "failure_mode": record.get("failure_mode"),
                "probes": [
                    item.get("name") for item in ((record.get("child") or {}).get("probes") or [])
                ],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if record.get("outcome") == "pass" else 1


def run_exchange_rate(*, model_spec: Path, session_id: str, out_dir: Path) -> int:
    from tools.ttft_slo_canary import CanaryDriftAbort

    cfg = load_exchange_config()
    gates = require_gates()
    harness = load_harness(model_spec)
    out_dir.mkdir(parents=True, exist_ok=True)
    _publish_cell_status("running", session_id)
    devices = list(cfg["devices"])
    contexts = [int(item) for item in cfg["context_tokens"]]
    repeats = int(cfg["repeats"])
    planned = len(devices) * len(contexts) * repeats
    config_bytes = _CONFIG_PATH.read_bytes()
    plan: dict[str, Any] = {
        "kind": "exchange_rate",
        "session_id": session_id,
        "started_utc": _utc(),
        "model_spec": str(harness["model_spec"]),
        "model_name": harness["model_name"],
        "config_path": "configs/exchange_rate.yaml",
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "budget_s": float(cfg["budget_s"]),
        "context_tokens": contexts,
        "concurrencies": [int(item) for item in cfg["concurrencies"]],
        "repeats": repeats,
        "devices": [item["id"] for item in devices],
        "residency": str(cfg["residency"]),
        "planned_probe_count": planned,
        "gates": gates,
        "status": "running",
    }
    plan_path = out_dir / "plan.json"
    _write(plan_path, plan)
    guard = _open_canary(
        model_spec=_canary_model([harness["model_spec"]]),
        work=out_dir / "work",
        plan_path=plan_path,
        planned=planned,
    )
    plan["canary"] = guard.plan_fragment()
    _write(plan_path, plan)
    points: list[dict[str, Any]] = []
    probes_log: list[dict[str, Any]] = []
    try:
        guard.opening()
        for device in devices:
            for n_tokens in contexts:
                for repeat in range(repeats):
                    tag = f"{device['id']}-n{n_tokens}-r{repeat}"
                    record = _run_one(
                        harness=harness,
                        cfg=cfg,
                        device=device,
                        work=out_dir / "work",
                        context_tokens=n_tokens,
                        concurrencies=[int(item) for item in cfg["concurrencies"]],
                        decode_new_tokens=int(cfg["decode_new_tokens"]),
                        budget_s=float(cfg["budget_s"]),
                        tag=tag,
                    )
                    point = _point_from_record(
                        record,
                        device_id=str(device["id"]),
                        n_tokens=n_tokens,
                        repeat=repeat,
                    )
                    points.append(point)
                    _write(out_dir / "points" / f"{tag}.json", point)
                    probes_log.append({"wall_s": record.get("parent_wall_s")})
                    guard.after_probe(probes_log)
    except CanaryDriftAbort as exc:
        summary = {
            "kind": "exchange_rate",
            "session_id": session_id,
            "status": "FAIL_CANARY_DRIFT",
            "abort_reason": str(exc.detail),
            "points": points,
            "canaries": list(guard.canaries),
        }
        _write(out_dir / "summary.json", summary)
        raise SystemExit(f"REFUSED -- FAIL_CANARY_DRIFT: {exc.detail}") from exc

    failed = any(point.get("failure_kind") for point in points)
    summary = {
        "kind": "exchange_rate",
        "session_id": session_id,
        "status": "partial" if failed else "complete",
        "budget_s": float(cfg["budget_s"]),
        "points": points,
        "what_fits": _measured_table(points, budget_s=float(cfg["budget_s"])),
    }
    return _finish(guard=guard, out_dir=out_dir, summary=summary, plan=plan)


def main_ids() -> str:
    return new_session_id()


def exit_of(status: str) -> int:
    return cell_exit_code(status)
