"""Deterministic MCP-01 aggregation over immutable completed runs."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .audit import CATEGORIES, audit_aggregate, audit_diagnostics, audit_run, endpoint_totals
from .contracts import PROTOCOL_VERSION, protocol_sha256
from .runner import COMPLETE_MARKER, is_complete


def find_completed_runs(run_root: Path) -> list[Path]:
    """Return completed seed directories in stable lexical order."""
    return sorted(
        marker.parent
        for marker in Path(run_root).glob(f"*/*/*/{COMPLETE_MARKER}")
        if is_complete(marker.parent)
    )


def analyze_runs(
    run_dirs: Iterable[Path],
    *,
    workers: int | None = None,
) -> dict[str, Any]:
    """Analyze completed directories; any parallelism is process-only."""
    paths = sorted({Path(path).resolve() for path in run_dirs}, key=lambda path: path.as_posix())
    incomplete = [str(path) for path in paths if not is_complete(path)]
    if incomplete:
        raise ValueError(f"analysis accepts completed run directories only: {incomplete}")
    if not paths:
        return reduce_records([])

    worker_count = (
        workers
        if workers is not None
        else min(len(paths), os.cpu_count() or 1, 8)
    )
    if worker_count < 1:
        raise ValueError("workers must be at least 1")
    if worker_count > 1 and len(paths) > 1:
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            records = list(pool.map(_analyze_one, paths))
    else:
        records = [_analyze_one(path) for path in paths]
    records.sort(key=lambda item: (item["transport"], item["cell_id"], item["seed"]))
    return reduce_records(records)


def analyze_root(run_root: Path, *, workers: int | None = None) -> dict[str, Any]:
    return analyze_runs(find_completed_runs(run_root), workers=workers)


def record_steady_cpu_ns_per_message(record: Mapping[str, Any]) -> float:
    """Process CPU per message excluding SESSION_SETUP amortization."""
    if "steady_combined_cpu_ns_per_message" in record:
        value = record["steady_combined_cpu_ns_per_message"]
        if isinstance(value, Mapping):
            return float(value.get("median", 0.0))
        return float(value)
    combined = float(record.get("combined_cpu_ns_per_message", 0.0))
    setup_total = float(record.get("session_setup_cpu_ns", 0.0))
    # Fallback when only amortized SESSION_SETUP is present.
    setup_per_message = float(
        (record.get("category_cpu_ns_per_message") or {}).get("SESSION_SETUP", 0.0)
    )
    if setup_total > 0.0 and combined > 0.0:
        # Infer message count from amortized setup when possible.
        if setup_per_message > 0.0:
            return max(0.0, combined - setup_per_message)
        return max(0.0, combined - setup_total)
    return max(0.0, combined - setup_per_message)


def cell_steady_cpu_ns_per_message(cell: Mapping[str, Any]) -> float:
    """Median steady CPU/message from an aggregated cell row."""
    steady = cell.get("steady_combined_cpu_ns_per_message")
    if isinstance(steady, Mapping):
        return float(steady.get("median", 0.0))
    if steady is not None:
        return float(steady)
    combined = cell.get("combined_cpu_ns_per_message") or {}
    setup = (cell.get("category_cpu_ns_per_message") or {}).get("SESSION_SETUP") or {}
    combined_v = float(combined.get("median", 0.0) if isinstance(combined, Mapping) else combined)
    setup_v = float(setup.get("median", 0.0) if isinstance(setup, Mapping) else setup)
    return max(0.0, combined_v - setup_v)


def cell_session_setup_cpu_ns(cell: Mapping[str, Any]) -> float:
    setup = cell.get("session_setup_cpu_ns") or {}
    if isinstance(setup, Mapping):
        return float(setup.get("median", 0.0))
    return float(setup or 0.0)


def reduce_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Stable, order-independent reduction to the aggregate JSON contract."""
    ordered = sorted(
        (dict(record) for record in records),
        key=lambda item: (item["transport"], item["cell_id"], int(item["seed"])),
    )
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in ordered:
        groups[record["cell_id"]].append(record)

    cells: list[dict[str, Any]] = []
    for cell_id, retained in sorted(groups.items()):
        coordinates = dict(retained[0]["coordinates"])
        cell: dict[str, Any] = {
            "cell_id": cell_id,
            "coordinates": coordinates,
            "n": len(retained),
            "seeds": [int(item["seed"]) for item in retained],
            "all_runs_retained": True,
            "audit_pass_count": sum(bool(item["audit"]["pass"]) for item in retained),
            "combined_cpu_ns_per_message": summarize(
                [float(item["combined_cpu_ns_per_message"]) for item in retained]
            ),
            "steady_combined_cpu_ns_per_message": summarize(
                [float(record_steady_cpu_ns_per_message(item)) for item in retained]
            ),
            "combined_wall_ns_per_message": summarize(
                [float(item["combined_wall_ns_per_message"]) for item in retained]
            ),
            "wait_ns_per_message": summarize(
                [float(item["wait_ns_per_message"]) for item in retained]
            ),
            "session_setup_cpu_ns": summarize(
                [
                    float(
                        item.get(
                            "session_setup_cpu_ns",
                            item["category_cpu_ns_per_message"].get("SESSION_SETUP", 0),
                        )
                    )
                    for item in retained
                ]
            ),
            "category_cpu_ns_per_message": {
                category: summarize(
                    [
                        float(item["category_cpu_ns_per_message"].get(category, 0))
                        for item in retained
                    ]
                )
                for category in CATEGORIES
            },
            "category_wall_ns_per_message": {
                category: summarize(
                    [
                        float(item["category_wall_ns_per_message"].get(category, 0))
                        for item in retained
                    ]
                )
                for category in CATEGORIES
            },
            "provenance_cpu_ns_per_message": _summarize_provenance(
                [item.get("provenance_cpu_ns_per_message") or {} for item in retained]
            ),
            "gap_decomposition_ns_per_message": _summarize_gap_decomposition(
                [item.get("gap_decomposition_ns_per_message") or {} for item in retained]
            ),
            "measured_messages": int(retained[0].get("measured_messages") or 0),
            "message_diagnostics": retained[0].get("message_diagnostics") or {},
            "retained_runs": [
                {
                    "seed": item["seed"],
                    "run_dir": item["run_dir"],
                    "audit": item["audit"],
                }
                for item in retained
            ],
        }
        cells.append(cell)

    aggregate_audit = audit_aggregate(
        [
            {
                "cell_id": record["cell_id"],
                "seed": record["seed"],
                "coordinates": record["coordinates"],
                "aggregate": {"combined_cpu_ns": record["combined_cpu_ns"]},
                "result_validity": record.get("result_validity"),
                "primary": record.get("primary", False),
            }
            for record in ordered
        ]
    )
    from .contracts import load_protocol
    from .gap_split import (
        classify_with_population_gate,
        observer_instrumentation_crosscheck,
    )

    protocol = load_protocol()
    seed_count = len({int(item["seed"]) for item in ordered})

    def _cell_decomp(cell: Mapping[str, Any]) -> dict[str, Any] | None:
        gap = cell.get("gap_decomposition_ns_per_message") or {}
        parent_raw = gap.get("parent_cpu_ns") or 0
        parent = (
            float(parent_raw.get("median", parent_raw.get("mean", 0)))
            if isinstance(parent_raw, Mapping)
            else float(parent_raw or 0)
        )
        mechs = {}
        for key in (
            "gap_event_loop",
            "gap_instrumentation",
            "gap_gc",
            "gap_syscall_return",
            "gap_unattributed",
        ):
            raw = gap.get(key) or 0
            mechs[key] = (
                float(raw.get("median", raw.get("mean", 0)))
                if isinstance(raw, Mapping)
                else float(raw or 0)
            )
        if parent <= 0 and not any(mechs.values()):
            return None
        return {
            "parent_cpu_ns": parent or sum(mechs.values()),
            "mechanisms": mechs,
            "boundaries": gap.get("boundaries") or ["inter_region"],
            "gap_syscall_return_subprovenance": gap.get(
                "gap_syscall_return_subprovenance"
            ),
        }

    def _arm_verdicts(implementation: str) -> dict[str, Any]:
        arm_cells = [
            cell
            for cell in cells
            if (cell.get("coordinates") or {}).get("implementation") == implementation
            and (cell.get("coordinates") or {}).get("mode") == "throttle"
        ]
        samples = []
        for cell in arm_cells:
            decomp = _cell_decomp(cell)
            if decomp is None:
                continue
            samples.append(
                {
                    "cell_id": cell.get("cell_id"),
                    "transport": (cell.get("coordinates") or {}).get("transport"),
                    **classify_with_population_gate(
                        decomp,
                        cfg=protocol["audit"],
                        measured_messages=int(cell.get("measured_messages") or 0),
                        seed_count=seed_count,
                    ),
                }
            )
        if not samples:
            return {
                "verdict": "deferred_insufficient_population",
                "binding": False,
                "advisory_only": None,
                "reason": f"no gap_decomposition samples for {implementation}",
                "implementation": implementation,
            }
        if any(
            item.get("verdict") == "deferred_insufficient_population"
            for item in samples
        ):
            return {
                "verdict": "deferred_insufficient_population",
                "binding": False,
                "implementation": implementation,
                "advisory_only": [
                    {
                        "cell_id": item.get("cell_id"),
                        "transport": item.get("transport"),
                        **(item.get("advisory_only") or {"verdict": item.get("verdict")}),
                    }
                    for item in samples
                ],
                "reason": samples[0].get("reason"),
                "population": samples[0].get("population"),
            }
        return {**samples[0], "implementation": implementation, "samples": samples}

    per_arm = {
        "raw_jsonrpc": _arm_verdicts("raw_jsonrpc"),
        "reference_sdk": _arm_verdicts("reference_sdk"),
    }
    aggregate_audit["diffuseness_verdict_by_arm"] = per_arm
    # Top-level field remains deferred when any arm is deferred; never pool arms.
    aggregate_audit["diffuseness_verdict"] = {
        "verdict": "deferred_insufficient_population"
        if any(
            not arm.get("binding")
            for arm in per_arm.values()
        )
        else "see_per_arm",
        "binding": False,
        "per_arm": True,
        "reason": (
            "verdicts are scoped per implementation arm "
            "(diffuseness_verdict_by_arm); do not pool raw and SDK"
        ),
        "arms": {
            name: {
                "verdict": arm.get("verdict"),
                "binding": arm.get("binding"),
            }
            for name, arm in per_arm.items()
        },
    }
    # Prefer raw-arm advisory list at top level for report compatibility.
    raw_arm = per_arm["raw_jsonrpc"]
    if raw_arm.get("verdict") == "deferred_insufficient_population":
        aggregate_audit["diffuseness_verdict"]["advisory_only"] = raw_arm.get(
            "advisory_only"
        )
        aggregate_audit["diffuseness_verdict"]["population"] = raw_arm.get("population")
        if raw_arm.get("reason"):
            aggregate_audit["diffuseness_verdict"]["reason"] = (
                f"{aggregate_audit['diffuseness_verdict']['reason']}; "
                f"raw arm: {raw_arm.get('reason')}"
            )

    observer_checks = []
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for cell in cells:
        coordinates = cell.get("coordinates") or {}
        key = (
            coordinates.get("transport"),
            coordinates.get("payload_bytes"),
            coordinates.get("schema_profile"),
            coordinates.get("tool_count"),
            coordinates.get("implementation"),
        )
        by_key.setdefault(key, {})[str(coordinates.get("mode"))] = cell
    for modes in by_key.values():
        if "throttle" in modes and "stripped" in modes:
            observer_checks.append(
                observer_instrumentation_crosscheck(
                    modes["throttle"], modes["stripped"], cfg=protocol["audit"]
                )
            )
    aggregate_audit["observer_instrumentation_crosscheck"] = observer_checks
    g7_live_cells = [
        cell.get("cell_id")
        for cell in cells
        if any(
            ((run.get("audit") or {}).get("gates") or {})
            .get("G7", {})
            .get("g7_live")
            for run in (cell.get("retained_runs") or [])
        )
        or bool(cell.get("gap_decomposition_ns_per_message"))
    ]
    aggregate_audit["g7_live_cells"] = g7_live_cells
    run_gates: dict[str, dict[str, Any]] = {}
    for gate_name in ("G1", "G2", "G3", "G6", "G7"):
        errors = [
            f"{record['cell_id']} seed={record['seed']}: {error}"
            for record in ordered
            for error in ((record.get("audit") or {}).get("gates", {}).get(gate_name, {}).get("errors") or [])
        ]
        run_gates[gate_name] = {
            "pass": not errors,
            "errors": errors,
            "run_count": len(ordered),
        }
    semantic_hashes: dict[tuple[Any, ...], tuple[str, ...]] = {}
    for record in ordered:
        coordinates = record["coordinates"]
        key = (
            coordinates.get("payload_bytes"),
            coordinates.get("schema_profile"),
            coordinates.get("tool_count"),
            int(record["seed"]),
        )
        observed = tuple(record.get("canonical_hashes") or ())
        reference = semantic_hashes.setdefault(key, observed)
        if observed != reference:
            run_gates["G2"]["errors"].append(
                f"cross-transport semantic hash mismatch for {key}"
            )
    run_gates["G2"]["pass"] = not run_gates["G2"]["errors"]
    aggregate_audit["gates"] = {
        **run_gates,
        **aggregate_audit.get("gates", {}),
    }
    repro_errors = [
        f"{record['cell_id']} seed={record['seed']}: {error}"
        for record in ordered
        for error in ((record.get("audit") or {}).get("manifest_errors") or [])
    ]
    aggregate_audit["repro"] = {
        "pass": not repro_errors,
        "errors": repro_errors,
    }
    aggregate_audit["violations"] = [
        error
        for gate in aggregate_audit["gates"].values()
        for error in gate.get("errors", [])
    ] + repro_errors
    aggregate_audit["pass"] = not aggregate_audit["violations"]
    diagnostics = audit_diagnostics(ordered)
    manifests = [dict(record["manifest"]) for record in ordered]
    first_manifest = manifests[0] if manifests else {}
    return {
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": protocol_sha256(),
        "experiment": "mcp_tax",
        "result_validity": _validity(ordered, aggregate_audit),
        "git": first_manifest.get("git"),
        "platform": first_manifest.get("platform"),
        "kernel_version": first_manifest.get("kernel_version"),
        "core_pins": first_manifest.get("core_pins"),
        "software": first_manifest.get("software"),
        "sdk_lock": first_manifest.get("sdk_lock"),
        "certificate": first_manifest.get("certificate"),
        "manifests": manifests,
        "run_count": len(ordered),
        "cell_count": len(cells),
        "deterministic_order": True,
        "cells": cells,
        "payload_exponents": _payload_exponents(cells),
        "setup_tool_count_curve": _tool_count_curve(cells),
        "sdk_raw_delta": _sdk_raw_delta(cells),
        "audit": aggregate_audit,
        "diagnostics": diagnostics,
    }


def write_aggregate(path: Path, aggregate: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summarize(values: Sequence[float]) -> dict[str, float | int]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"n": 0, "median": 0.0, "q1": 0.0, "q3": 0.0, "iqr": 0.0}
    q1 = quantile(ordered, 0.25)
    q3 = quantile(ordered, 0.75)
    return {
        "n": len(ordered),
        "median": quantile(ordered, 0.5),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
    }


def quantile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    return float(
        values[lower] * (upper - position) + values[upper] * (position - lower)
    )


def _analyze_one(run_dir: Path) -> dict[str, Any]:
    manifest = _load_json(run_dir / "manifest.json")
    plan = _load_json(run_dir / "plan.json")
    client = _load_endpoint(run_dir / "client")
    server = _load_endpoint(run_dir / "server")
    audit = audit_run(client, server, plan=plan, manifest=manifest)
    endpoints = {
        "client": endpoint_totals(client),
        "server": endpoint_totals(server),
    }
    measured_messages = int(
        plan.get("measured_messages")
        or manifest.get("measured_messages")
        or len(endpoints["client"]["canonical_hashes"])
        or 1
    )
    combined_cpu = sum(item["process_cpu_ns"] for item in endpoints.values())
    combined_wall = max(item["wall_ns"] for item in endpoints.values())
    session_setup_cpu_ns = sum(
        item["category_cpu_ns"]["SESSION_SETUP"] for item in endpoints.values()
    )
    category_cpu = {
        category: sum(item["category_cpu_ns"][category] for item in endpoints.values())
        / measured_messages
        for category in CATEGORIES
    }
    category_wall = {
        category: sum(item["category_wall_ns"][category] for item in endpoints.values())
        / measured_messages
        for category in CATEGORIES
    }
    provenance_cpu = _combined_provenance_cpu_ns_per_message(
        client, server, measured_messages=measured_messages
    )
    gap_decomp = _gap_decomposition_ns_per_message(
        client, measured_messages=measured_messages
    )
    coordinates = manifest.get("coordinates") or plan.get("coordinates") or {}
    combined_cpu_ns_per_message = combined_cpu / measured_messages
    steady_combined_cpu_ns_per_message = max(
        0.0, (combined_cpu - session_setup_cpu_ns) / measured_messages
    )
    return {
        "run_dir": run_dir.as_posix(),
        "cell_id": manifest.get("cell_id") or coordinates.get("cell_id") or run_dir.parent.name,
        "seed": int(manifest.get("seed", run_dir.name)),
        "transport": coordinates.get("transport") or run_dir.parents[2].name,
        "coordinates": coordinates,
        "manifest": manifest,
        "result_validity": manifest.get("result_validity"),
        "primary": manifest.get("primary", False),
        "combined_cpu_ns": combined_cpu,
        "combined_cpu_ns_per_message": combined_cpu_ns_per_message,
        "steady_combined_cpu_ns_per_message": steady_combined_cpu_ns_per_message,
        "combined_wall_ns_per_message": combined_wall / measured_messages,
        "wait_ns_per_message": (
            sum(item["wait_ns"] for item in endpoints.values()) / measured_messages
        ),
        "category_cpu_ns_per_message": category_cpu,
        "category_wall_ns_per_message": category_wall,
        "provenance_cpu_ns_per_message": provenance_cpu,
        "gap_decomposition_ns_per_message": gap_decomp,
        "measured_messages": measured_messages,
        "message_diagnostics": client.get("message_diagnostics") or {},
        "session_setup_cpu_ns": session_setup_cpu_ns,
        "canonical_hashes": endpoints["client"]["canonical_hashes"],
        "audit": audit,
        "client": client,
        "server": server,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_endpoint(directory: Path) -> dict[str, Any]:
    for filename in ("result.json", "metrics.json", "endpoint.json"):
        path = directory / filename
        if path.is_file():
            return _load_json(path)
    raise FileNotFoundError(f"missing endpoint JSON in {directory}")


def _endpoint_provenance_cpu_ns(endpoint: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """Sum provenance CPU by category from a client/server result ledger."""
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for entry in endpoint.get("categories") or []:
        if not isinstance(entry, Mapping):
            continue
        category = str(entry.get("category") or "")
        if not category:
            continue
        provenance = (entry.get("totals") or {}).get("provenance") or {}
        if not isinstance(provenance, Mapping):
            continue
        for name, value in provenance.items():
            totals[category][str(name)] += float(value)
    return {category: dict(values) for category, values in totals.items()}


def _combined_provenance_cpu_ns_per_message(
    client: Mapping[str, Any],
    server: Mapping[str, Any],
    *,
    measured_messages: int,
) -> dict[str, dict[str, float]]:
    divisor = max(1, int(measured_messages))
    combined: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for endpoint in (client, server):
        for category, provenances in _endpoint_provenance_cpu_ns(endpoint).items():
            for name, value in provenances.items():
                combined[category][name] += value / divisor
    return {category: dict(values) for category, values in combined.items()}


def _gap_decomposition_ns_per_message(
    client: Mapping[str, Any],
    *,
    measured_messages: int,
) -> dict[str, Any]:
    from .gap_split import GAP_DECOMPOSITION_KEY, normalize_mechanisms

    divisor = max(1, int(measured_messages))
    totals: dict[str, float] = defaultdict(float)
    parent_total = 0.0
    boundaries: set[str] = set()
    count = 0
    d_meas_total = 0.0
    d_adj_total = 0.0
    for mid, diagnostics in (client.get("message_diagnostics") or {}).items():
        if not isinstance(diagnostics, Mapping):
            continue
        decomp = diagnostics.get(GAP_DECOMPOSITION_KEY)
        if not isinstance(decomp, Mapping):
            continue
        count += 1
        parent_total += float(decomp.get("parent_cpu_ns") or 0)
        for key, value in normalize_mechanisms(decomp.get("mechanisms") or {}).items():
            totals[key] += float(value)
        for boundary in decomp.get("boundaries") or []:
            boundaries.add(str(boundary))
        sub = decomp.get("gap_syscall_return_subprovenance") or {}
        if isinstance(sub, Mapping):
            d_meas_total += float(sub.get("measured_ns") or 0)
            d_adj_total += float(sub.get("adjacent_segments_ns") or 0)
    if count == 0:
        return {}
    # Prefer averaging over observed decomposed messages (usually == measured).
    denom = max(1, count)
    out: dict[str, Any] = {
        "parent_cpu_ns": parent_total / denom,
        "boundaries": sorted(boundaries),
        "decomposed_message_count": count,
        "measured_messages": measured_messages,
        "gap_syscall_return_subprovenance": {
            "measured_ns": d_meas_total / denom,
            "adjacent_segments_ns": d_adj_total / denom,
        },
    }
    for key, value in totals.items():
        out[key] = value / denom
    return out


def _summarize_gap_decomposition(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not records:
        return {}
    keys = sorted(
        {
            key
            for record in records
            for key in record.keys()
            if key
            not in {
                "boundaries",
                "decomposed_message_count",
                "measured_messages",
                "parent_cpu_ns",
                "gap_syscall_return_subprovenance",
            }
        }
    )
    out: dict[str, Any] = {
        "parent_cpu_ns": summarize(
            [float(record.get("parent_cpu_ns") or 0) for record in records]
        ),
    }
    for key in keys:
        out[key] = summarize([float(record.get(key) or 0) for record in records])
    boundaries: set[str] = set()
    for record in records:
        for boundary in record.get("boundaries") or []:
            boundaries.add(str(boundary))
    out["boundaries"] = sorted(boundaries)
    d_meas = []
    d_adj = []
    for record in records:
        sub = record.get("gap_syscall_return_subprovenance") or {}
        if isinstance(sub, Mapping):
            d_meas.append(float(sub.get("measured_ns") or 0))
            d_adj.append(float(sub.get("adjacent_segments_ns") or 0))
    if d_meas or d_adj:
        out["gap_syscall_return_subprovenance"] = {
            "measured_ns": summarize(d_meas or [0.0]),
            "adjacent_segments_ns": summarize(d_adj or [0.0]),
        }
    return out


def _summarize_provenance(
    records: Sequence[Mapping[str, Mapping[str, float]]],
) -> dict[str, dict[str, dict[str, float | int]]]:
    keys: dict[str, set[str]] = defaultdict(set)
    for record in records:
        for category, provenances in record.items():
            keys[str(category)].update(str(name) for name in provenances)
    summarized: dict[str, dict[str, dict[str, float | int]]] = {}
    for category, names in sorted(keys.items()):
        summarized[category] = {
            name: summarize(
                [float((record.get(category) or {}).get(name, 0.0)) for record in records]
            )
            for name in sorted(names)
        }
    return summarized


def _payload_exponents(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[tuple[float, float]]] = defaultdict(list)
    for cell in cells:
        coordinates = cell["coordinates"]
        if int(coordinates.get("tool_count", 0)) != 1 or coordinates.get("mode") != "throttle":
            continue
        key = (
            str(coordinates.get("transport")),
            str(coordinates.get("schema_profile")),
            str(coordinates.get("implementation")),
            str(coordinates.get("mode")),
        )
        grouped[key].append(
            (
                float(coordinates.get("payload_bytes", 0)),
                float(cell["combined_cpu_ns_per_message"]["median"]),
            )
        )
    results = []
    for key, points in sorted(grouped.items()):
        positive = sorted((x, y) for x, y in points if x > 0 and y > 0)
        if len(positive) < 2:
            continue
        exponent = _linear_slope(
            [math.log(point[0]) for point in positive],
            [math.log(point[1]) for point in positive],
        )
        results.append(
            {
                "transport": key[0],
                "schema_profile": key[1],
                "implementation": key[2],
                "mode": key[3],
                "n_payloads": len(positive),
                "cpu_payload_exponent": exponent,
            }
        )
    return results


def _tool_count_curve(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    curve = []
    for cell in cells:
        coordinates = cell["coordinates"]
        count = int(coordinates.get("tool_count", 0))
        if count not in (10, 100, 1000):
            continue
        setup = cell.get("session_setup_cpu_ns", {})
        curve.append(
            {
                "transport": coordinates.get("transport"),
                "implementation": coordinates.get("implementation"),
                "tool_count": count,
                "session_setup_cpu_ns": setup.get("median", 0.0),
                "cell_id": cell["cell_id"],
            }
        )
    return sorted(
        curve,
        key=lambda item: (
            str(item["transport"]),
            str(item["implementation"]),
            int(item["tool_count"]),
        ),
    )


def _sdk_raw_delta(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pairs: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for cell in cells:
        coordinates = cell["coordinates"]
        key = tuple(
            coordinates.get(name)
            for name in (
                "transport",
                "payload_bytes",
                "schema_profile",
                "tool_count",
                "mode",
            )
        )
        pairs[key][str(coordinates.get("implementation"))] = cell
    deltas = []
    for key, pair in sorted(pairs.items(), key=lambda item: repr(item[0])):
        if set(pair) < {"reference_sdk", "raw_jsonrpc"}:
            continue
        sdk_steady = cell_steady_cpu_ns_per_message(pair["reference_sdk"])
        raw_steady = cell_steady_cpu_ns_per_message(pair["raw_jsonrpc"])
        sdk_setup = cell_session_setup_cpu_ns(pair["reference_sdk"])
        raw_setup = cell_session_setup_cpu_ns(pair["raw_jsonrpc"])
        deltas.append(
            {
                "transport": key[0],
                "payload_bytes": key[1],
                "schema_profile": key[2],
                "tool_count": key[3],
                "mode": key[4],
                "sdk_minus_raw_steady_cpu_ns_per_message": sdk_steady - raw_steady,
                "sdk_over_raw_steady_ratio": (
                    sdk_steady / raw_steady if raw_steady else None
                ),
                "sdk_minus_raw_setup_cpu_ns": sdk_setup - raw_setup,
                "sdk_setup_cpu_ns": sdk_setup,
                "raw_setup_cpu_ns": raw_setup,
            }
        )
    return deltas


def _linear_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator


def _validity(records: Sequence[Mapping[str, Any]], aggregate_audit: Mapping[str, Any]) -> str:
    if not records:
        return "debug_only"
    requested = {record.get("result_validity") for record in records}
    if requested == {"protocol_microbenchmark"} and aggregate_audit.get("pass"):
        return "protocol_microbenchmark"
    return "debug_only"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_root",
        nargs="?",
        type=Path,
        default=Path("apu_characterization/out/mcp_tax/runs"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apu_characterization/out/mcp_tax/mcp_tax.matrix.json"),
    )
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    aggregate = analyze_root(args.run_root, workers=args.workers)
    write_aggregate(args.output, aggregate)
    print(
        f"{args.output}: {aggregate['run_count']} runs, "
        f"audit={'PASS' if aggregate['audit']['pass'] else 'FAIL'}"
    )


if __name__ == "__main__":
    main()
