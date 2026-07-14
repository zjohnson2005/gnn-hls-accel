"""Frozen G1--G5 accounting gates for MCP-01."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .contracts import CellPlan, load_protocol
from .manifest import validate_manifest
from .taxonomy import MCP_INSTRUMENTED, McpCategory

CATEGORIES = tuple(category.value for category in MCP_INSTRUMENTED)


def _number(data: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return default


def _category_value(endpoint: Mapping[str, Any], category: str, metric: str) -> float:
    for source in _endpoint_sources(endpoint):
        direct = source.get(f"category_{metric}_ns")
        if isinstance(direct, Mapping):
            value = _number(direct, category)
            if value:
                return value
        categories = source.get("categories") or source.get("per_category") or {}
        if isinstance(categories, Mapping):
            record = categories.get(category, {})
        elif isinstance(categories, Sequence) and not isinstance(categories, (str, bytes)):
            return sum(
                _number(
                    item.get("totals") or item,
                    f"{metric}_ns",
                    metric,
                    f"total_{metric}_ns",
                )
                for item in categories
                if isinstance(item, Mapping)
                and item.get("category", item.get("name")) == category
            )
        else:
            record = {}
        if isinstance(record, Mapping):
            value = _number(record, f"{metric}_ns", metric, f"total_{metric}_ns")
            if value:
                return value
        if metric == "cpu" and isinstance(record, (int, float)):
            return float(record)
    return 0.0


def _setup_category_totals(endpoint: Mapping[str, Any], metric: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    setup = endpoint.get("setup")
    if not isinstance(setup, Sequence) or isinstance(setup, (str, bytes)):
        return totals
    for item in setup:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("category", ""))
        if not name:
            continue
        record = item.get("totals") or item
        totals[name] = totals.get(name, 0.0) + _number(
            record, f"{metric}_ns", metric, f"total_{metric}_ns"
        )
    return totals


def endpoint_totals(endpoint: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a client/server result without imposing Workstream B classes."""
    nested = endpoint.get("result")
    if isinstance(nested, Mapping):
        endpoint = {**endpoint, **nested}
    sources = _endpoint_sources(endpoint)
    category_cpu = {name: _category_value(endpoint, name, "cpu") for name in CATEGORIES}
    category_wall = {name: _category_value(endpoint, name, "wall") for name in CATEGORIES}
    for name, value in _setup_category_totals(endpoint, "cpu").items():
        if name in category_cpu:
            category_cpu[name] = category_cpu.get(name, 0.0) + value
    for name, value in _setup_category_totals(endpoint, "wall").items():
        if name in category_wall:
            category_wall[name] = category_wall.get(name, 0.0) + value
    residual_cpu = _category_value(endpoint, McpCategory.RESIDUAL.value, "cpu")
    residual_wall = _category_value(endpoint, McpCategory.RESIDUAL.value, "wall")
    process_cpu = _first_number(
        sources, "process_cpu_ns", "total_cpu_ns", "endpoint_cpu_ns", "cpu_ns"
    )
    wall = _first_number(sources, "wall_ns", "elapsed_wall_ns", "total_wall_ns")
    accounted_cpu = _first_number(
        sources, "accounted_cpu_ns", "instrumented_cpu_ns"
    ) or sum(category_cpu.values())
    accounted_wall = _first_number(
        sources, "accounted_wall_ns", "instrumented_wall_ns"
    ) or sum(category_wall.values())
    explicit_wait = _first_number(sources, "wait_ns", "io_wait_ns")
    waits = endpoint.get("waits")
    if isinstance(waits, Sequence) and not isinstance(waits, (str, bytes)):
        explicit_wait = sum(
            _number(item.get("totals") or item, "wall_ns", "wait_ns")
            for item in waits
            if isinstance(item, Mapping)
        )
    wait = explicit_wait
    hashes = None
    for source in sources:
        hashes = source.get("canonical_hashes")
        if hashes is None:
            hashes = source.get(
                "canonical_hash_sequence",
                source.get("request_hashes", source.get("message_hashes")),
            )
        if hashes is not None:
            break
    if hashes is None:
        messages = endpoint.get("messages") or endpoint.get("requests") or []
        hashes = [
            item.get("canonical_sha256", item.get("sha256"))
            for item in messages
            if isinstance(item, Mapping)
        ]
    return {
        "process_cpu_ns": process_cpu,
        "wall_ns": wall,
        "category_cpu_ns": category_cpu,
        "category_wall_ns": category_wall,
        "accounted_cpu_ns": accounted_cpu,
        "accounted_wall_ns": accounted_wall,
        "residual_cpu_ns": residual_cpu,
        "residual_wall_ns": residual_wall,
        "wait_ns": wait,
        "explicit_wait_ns": explicit_wait,
        "canonical_hashes": list(hashes or []),
        "mode": endpoint.get("mode"),
    }


def _endpoint_sources(endpoint: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources = [endpoint]
    for key in ("endpoint_observation", "totals", "metrics", "summary"):
        nested = endpoint.get(key)
        if isinstance(nested, Mapping):
            sources.append(nested)
            metadata = nested.get("metadata")
            if isinstance(metadata, Mapping):
                sources.append(metadata)
    return sources


def _first_number(sources: Sequence[Mapping[str, Any]], *keys: str) -> float:
    for source in sources:
        value = _number(source, *keys)
        if value:
            return value
    return 0.0


def _limit(total: float, *, floor: float, fraction: float) -> float:
    return max(float(floor), float(fraction) * max(0.0, total))


def audit_run(
    client: Mapping[str, Any],
    server: Mapping[str, Any],
    *,
    plan: CellPlan | Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply G1--G3 to one retained seed run."""
    protocol = load_protocol()
    cfg = protocol["audit"]
    normalized = {
        "client": endpoint_totals(client),
        "server": endpoint_totals(server),
    }
    gates: dict[str, dict[str, Any]] = {}

    g1_errors: list[str] = []
    for role, endpoint in normalized.items():
        threshold = cfg["residual_limit"] * endpoint["process_cpu_ns"] + _limit(
            endpoint["process_cpu_ns"],
            floor=cfg["residual_slack_floor_ns"],
            fraction=cfg["residual_slack_fraction"],
        )
        if endpoint["residual_cpu_ns"] < 0:
            g1_errors.append(
                f"{role} residual CPU is negative "
                f"({endpoint['residual_cpu_ns']:.0f} ns)"
            )
        elif (
            endpoint.get("mode") != "stripped"
            and endpoint["residual_cpu_ns"] > threshold
        ):
            g1_errors.append(
                f"{role} residual CPU {endpoint['residual_cpu_ns']:.0f} ns "
                f"exceeds 15%+slack limit {threshold:.0f} ns"
            )
    combined_cpu = sum(item["process_cpu_ns"] for item in normalized.values())
    combined_residual = sum(
        max(0.0, item["residual_cpu_ns"]) for item in normalized.values()
    )
    combined_limit = cfg["residual_limit"] * combined_cpu + _limit(
        combined_cpu,
        floor=cfg["residual_slack_floor_ns"],
        fraction=cfg["residual_slack_fraction"],
    )
    if (
        not any(item.get("mode") == "stripped" for item in normalized.values())
        and combined_residual > combined_limit
    ):
        g1_errors.append(
            f"combined residual CPU {combined_residual:.0f} ns exceeds "
            f"15%+slack limit {combined_limit:.0f} ns"
        )
    gates["G1"] = _gate(g1_errors, residual_combined_ns=combined_residual)

    g2_errors: list[str] = []
    client_hashes = normalized["client"]["canonical_hashes"]
    server_hashes = normalized["server"]["canonical_hashes"]
    if client_hashes != server_hashes:
        g2_errors.append("client/server canonical hash sequences differ")
    expected_hashes = _expected_hashes(plan)
    if expected_hashes is not None and client_hashes != expected_hashes:
        g2_errors.append("observed canonical hash sequence differs from cell plan")
    if not client_hashes:
        g2_errors.append("canonical hash sequence is empty")
    gates["G2"] = _gate(g2_errors, message_count=len(client_hashes))

    g3_errors: list[str] = []
    conservation: dict[str, Any] = {}
    for role, endpoint in normalized.items():
        cpu_error = abs(
            endpoint["process_cpu_ns"]
            - endpoint["accounted_cpu_ns"]
            - endpoint["residual_cpu_ns"]
        )
        cpu_limit = _limit(
            endpoint["process_cpu_ns"],
            floor=cfg["conservation_floor_ns"],
            fraction=cfg["conservation_fraction"],
        )
        if cpu_error > cpu_limit:
            g3_errors.append(
                f"{role} CPU conservation error {cpu_error:.0f} ns exceeds "
                f"{cpu_limit:.0f} ns"
            )
        wall_terms = (
            endpoint["accounted_wall_ns"]
            + endpoint["explicit_wait_ns"]
            + endpoint["residual_wall_ns"]
        )
        wall_error = (
            abs(endpoint["wall_ns"] - wall_terms)
            if endpoint["wall_ns"] > 0 and wall_terms > 0
            else math.inf
        )
        wall_limit = _limit(
            endpoint["wall_ns"],
            floor=cfg["conservation_floor_ns"],
            fraction=cfg["conservation_fraction"],
        )
        if wall_error > wall_limit:
            detail = "missing wall components" if math.isinf(wall_error) else (
                f"wall conservation error {wall_error:.0f} ns exceeds {wall_limit:.0f} ns"
            )
            g3_errors.append(f"{role} {detail}")
        conservation[role] = {
            "cpu_error_ns": cpu_error,
            "cpu_limit_ns": cpu_limit,
            "wall_error_ns": None if math.isinf(wall_error) else wall_error,
            "wall_limit_ns": wall_limit,
            "wait_ns": endpoint["explicit_wait_ns"],
        }
    gates["G3"] = _gate(g3_errors, conservation=conservation)

    g6_errors, g6_details = _audit_g6(client, server, plan=plan, cfg=cfg)
    gates["G6"] = _gate(g6_errors, **g6_details)

    from .gap_split import audit_gap_split_conservation

    g7_errors, g7_details = audit_gap_split_conservation(client, cfg=cfg, role="client")
    gates["G7"] = _gate(g7_errors, **g7_details)

    manifest_errors = validate_manifest(manifest, plan=plan) if manifest else []
    errors = [error for gate in gates.values() for error in gate["errors"]] + manifest_errors
    return {
        "pass": not errors,
        "gates": gates,
        "manifest_errors": manifest_errors,
        "violations": errors,
        "endpoints": normalized,
    }


def audit_aggregate(
    runs: Sequence[Mapping[str, Any]],
    *,
    expected_seeds: Iterable[int] = range(5),
) -> dict[str, Any]:
    """Apply G4--G5 and retain every seed, including failures."""
    protocol = load_protocol()
    expected = set(int(seed) for seed in expected_seeds)
    by_base: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    by_cell: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        coordinates = _coordinates(run)
        cell_id = str(run.get("cell_id") or coordinates.get("cell_id") or "")
        by_cell[cell_id].append(run)
        by_base[_base_key(coordinates)][str(coordinates.get("mode", ""))].append(run)

    primary_bases = [
        (key, modes)
        for key, modes in by_base.items()
        if "throttle" in modes
        and any(_tool_count(item) == 1 for item in modes["throttle"])
    ]
    observer_n = math.ceil(
        len(primary_bases) * protocol["observer_subsample"]["fraction"]
    )
    eligible = sorted(
        primary_bases,
        key=lambda pair: _sha(
            str(pair[1]["throttle"][0].get("cell_id") or pair[0])
        ),
    )[:observer_n]
    g4_errors: list[str] = []
    for key, modes in eligible:
        missing = {"full", "throttle", "stripped"} - set(modes)
        if missing:
            g4_errors.append(f"observer cell {key} missing modes {sorted(missing)}")
    promoted_full = [
        str(run.get("cell_id", ""))
        for run in runs
        if _coordinates(run).get("mode") == "full"
        and (
            run.get("primary")
            or run.get("promoted")
            or run.get("claim_eligible")
        )
    ]
    if promoted_full:
        g4_errors.append("full observer runs must never be promoted to primary")

    g5_errors: list[str] = [] if runs else ["no retained runs"]
    spread_flags: list[dict[str, Any]] = []
    spread_summary: list[dict[str, Any]] = []
    for cell_id, retained in sorted(by_cell.items()):
        seeds = [int(run.get("seed", -1)) for run in retained]
        if set(seeds) != expected or len(seeds) != len(expected):
            g5_errors.append(
                f"{cell_id or '<missing-cell-id>'} retained seeds {sorted(seeds)}; "
                f"expected exactly {sorted(expected)}"
            )
        values = [
            _run_cpu(item)
            for item in retained
            if _run_cpu(item) > 0
        ]
        spread = _spread(values)
        if spread:
            pathological = (
                spread["iqr_over_median"]
                > protocol["audit"]["pathological_iqr_over_median"]
                or spread["max_over_median"]
                > protocol["audit"]["pathological_max_over_median"]
            )
            summary = {"cell_id": cell_id, **spread, "pathological": pathological}
            spread_summary.append(summary)
            if pathological:
                spread_flags.append(summary)

    gates = {
        "G4": _gate(g4_errors, observer_cells=len(eligible), full_promotions=promoted_full),
        "G5": _gate(
            g5_errors,
            spread=spread_summary,
            spread_flags=spread_flags,
            retained_runs=len(runs),
        ),
    }
    errors = [error for gate in gates.values() for error in gate["errors"]]
    return {
        "pass": not errors,
        "gates": gates,
        "violations": errors,
        "spread_flags": spread_flags,
        "spread": spread_summary,
        "retained_runs": len(runs),
    }


def audit_completed_run(run_dir: Path, *, plan: CellPlan | None = None) -> dict[str, Any]:
    client = _read_endpoint(run_dir / "client")
    server = _read_endpoint(run_dir / "server")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    return audit_run(client, server, plan=plan, manifest=manifest)


def _read_endpoint(path: Path) -> dict[str, Any]:
    for name in ("result.json", "metrics.json", "endpoint.json"):
        candidate = path / name
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no endpoint result JSON under {path}")


def _expected_hashes(plan: CellPlan | Mapping[str, Any] | None) -> list[str] | None:
    if plan is None:
        return None
    if isinstance(plan, CellPlan):
        return plan.request_hashes()[plan.warmup_messages :]
    hashes = plan.get("request_hashes") or plan.get("canonical_hashes")
    if hashes is not None:
        return list(hashes)[int(plan.get("warmup_messages") or 0) :]
    steps = plan.get("steps")
    if isinstance(steps, Sequence):
        import hashlib

        from .contracts import canonical_json_bytes

        reconstructed: list[str] = []
        for position, step in enumerate(steps):
            if not isinstance(step, Mapping):
                return None
            index = int(step.get("index", position))
            payload = {
                "jsonrpc": "2.0",
                "id": index + 1,
                "method": step.get("method"),
                "params": {
                    "name": step.get("tool_name"),
                    "arguments": {
                        "schema_id": step.get("schema_id"),
                        "payload": "x" * int(step.get("payload_bytes", 0)),
                    },
                },
            }
            reconstructed.append(
                hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
            )
        return reconstructed[int(plan.get("warmup_messages") or 0) :]
    return None


def _gate(errors: list[str], **details: Any) -> dict[str, Any]:
    return {"pass": not errors, "errors": errors, **details}


def _coordinates(run: Mapping[str, Any]) -> Mapping[str, Any]:
    manifest = run.get("manifest") or {}
    return run.get("coordinates") or manifest.get("coordinates") or {}


def _base_key(coordinates: Mapping[str, Any]) -> str:
    return "|".join(
        str(coordinates.get(key, ""))
        for key in (
            "transport",
            "payload_bytes",
            "schema_profile",
            "tool_count",
            "implementation",
        )
    )


def _tool_count(run: Mapping[str, Any]) -> int:
    return int(_coordinates(run).get("tool_count") or 0)


def _run_cpu(run: Mapping[str, Any]) -> float:
    aggregate = run.get("aggregate") or run.get("metrics") or run
    return _number(aggregate, "combined_cpu_ns", "total_cpu_ns", "cpu_ns")


def _spread(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    median = _quantile(ordered, 0.5)
    q1 = _quantile(ordered, 0.25)
    q3 = _quantile(ordered, 0.75)
    denominator = median if median else 1.0
    return {
        "median": median,
        "iqr_over_median": (q3 - q1) / denominator,
        "max_over_median": max(ordered) / denominator,
    }


def _audit_g6(
    client: Mapping[str, Any],
    server: Mapping[str, Any],
    *,
    plan: CellPlan | Mapping[str, Any] | None,
    cfg: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    coordinates = {}
    if isinstance(plan, CellPlan):
        coordinates = plan.coordinates.as_dict()
    elif isinstance(plan, Mapping):
        coordinates = dict(plan.get("coordinates") or {})
    implementation = str(coordinates.get("implementation") or "")
    transport = str(coordinates.get("transport") or "")
    mode = str(coordinates.get("mode") or "")
    errors: list[str] = []
    details: dict[str, Any] = {"implementation": implementation, "messages": []}

    client_norm = endpoint_totals(client)
    messages = client.get("messages") or {}
    if not isinstance(messages, Mapping):
        messages = {}
    message_ids = sorted(str(key) for key in messages.keys())

    cpu_limit = _limit(
        1.0,
        floor=cfg["conservation_floor_ns"],
        fraction=cfg["conservation_fraction"],
    )

    for message_id in message_ids:
        per_message: dict[str, Any] = {"message_id": message_id}
        categories = _message_categories(client, message_id)
        booked_cpu = {
            name: value
            for name, value in categories.items()
            if name not in {McpCategory.RESIDUAL.value} and value > 0
        }
        total_cpu = sum(booked_cpu.values()) or 1.0
        per_message["categories"] = booked_cpu
        diagnostics = (client.get("message_diagnostics") or {}).get(message_id) or {}
        boundary_ns = float(diagnostics.get("client_call_boundary_ns") or 0)
        nested_ns = float(diagnostics.get("client_nested_cpu_ns") or sum(booked_cpu.values()))
        per_message["client_call_boundary_ns"] = boundary_ns
        per_message["client_nested_cpu_ns"] = nested_ns

        if boundary_ns > 0 and nested_ns > boundary_ns + cpu_limit:
            errors.append(
                f"client message {message_id} nested CPU {nested_ns:.0f} ns exceeds "
                f"boundary {boundary_ns:.0f} ns by more than {cpu_limit:.0f} ns"
            )

        if implementation == "raw_jsonrpc" and mode != "stripped":
            if len(booked_cpu) < 3:
                errors.append(
                    f"client raw message {message_id} books {len(booked_cpu)} "
                    "non-zero categories; need >= 3"
                )
            frame_cpu = booked_cpu.get(McpCategory.MSG_FRAME.value, 0.0)
            if transport in {"stdio", "http_sse_tls_off", "http_sse_tls_on"} and frame_cpu <= 0:
                errors.append(
                    f"client raw message {message_id} has zero MSG_FRAME on {transport}"
                )
            single_share = float(cfg.get("g6_single_category_share", 0.95))
            dominant = max(booked_cpu.values()) if booked_cpu else 0.0
            if booked_cpu and dominant / total_cpu > single_share:
                errors.append(
                    f"client raw message {message_id} has one category at "
                    f"{100 * dominant / total_cpu:.1f}% of booked CPU"
                )
            provenance_by_cat = _message_provenance(client, message_id)
            per_message["provenance"] = provenance_by_cat
            dominant_share = float(cfg.get("g6_dominant_category_share", 0.50))
            named_share = float(cfg.get("g6_named_provenance_share", 0.80))
            generic = {
                str(name)
                for name in (cfg.get("g6_generic_provenance") or ["measured", "test", ""])
            }
            for category, cpu in booked_cpu.items():
                if cpu / total_cpu <= dominant_share:
                    continue
                prov = provenance_by_cat.get(category) or {}
                named_ns = sum(
                    float(amount)
                    for name, amount in prov.items()
                    if str(name) not in generic
                )
                denom = sum(float(amount) for amount in prov.values()) or float(cpu)
                named_frac = named_ns / denom if denom else 0.0
                per_message.setdefault("dominant_provenance", {})[category] = {
                    "category_share": cpu / total_cpu,
                    "named_provenance_share": named_frac,
                    "provenance": dict(prov),
                }
                if named_frac < named_share:
                    errors.append(
                        f"client raw message {message_id} category {category} is "
                        f"{100 * cpu / total_cpu:.1f}% of booked CPU but named "
                        f"provenance covers only {100 * named_frac:.1f}% "
                        f"(need >= {100 * named_share:.0f}%); presumptive gap-fill "
                        "or opaque lump"
                    )
        details["messages"].append(per_message)

    return errors, details


def _message_categories(endpoint: Mapping[str, Any], message_id: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    categories = endpoint.get("categories") or []
    if isinstance(categories, Sequence) and not isinstance(categories, (str, bytes)):
        for item in categories:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("message_id")) != str(message_id):
                continue
            name = str(item.get("category"))
            record = item.get("totals") or item
            totals[name] = totals.get(name, 0.0) + _number(record, "cpu_ns")
    return totals


def _message_provenance(
    endpoint: Mapping[str, Any], message_id: str
) -> dict[str, dict[str, float]]:
    """Per-message category → provenance-label → cpu_ns."""
    out: dict[str, dict[str, float]] = {}
    categories = endpoint.get("categories") or []
    if not isinstance(categories, Sequence) or isinstance(categories, (str, bytes)):
        return out
    for item in categories:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("message_id")) != str(message_id):
            continue
        name = str(item.get("category"))
        record = item.get("totals") or item
        prov = record.get("provenance") if isinstance(record, Mapping) else None
        if not isinstance(prov, Mapping):
            continue
        bucket = out.setdefault(name, {})
        for label, amount in prov.items():
            bucket[str(label)] = bucket.get(str(label), 0.0) + float(amount or 0)
    return out


def audit_diagnostics(
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Non-gating diagnostics: TLS CA unity, zero-byte flags, wait outliers."""
    tls_hashes: set[str] = set()
    zero_byte_messages: list[str] = []
    wait_outliers: list[dict[str, Any]] = []
    for run in runs:
        manifest = run.get("manifest") or {}
        software = manifest.get("software") or {}
        tls = software.get("tls") or manifest.get("certificate")
        if isinstance(tls, Mapping):
            ca = tls.get("ca_sha256") or tls.get("sha256")
            if ca:
                tls_hashes.add(str(ca))
        for role in ("client", "server"):
            endpoint = run.get(role) or {}
            captures = endpoint.get("wire_captures") or []
            if isinstance(captures, Sequence):
                for item in captures:
                    if isinstance(item, Mapping) and int(item.get("bytes") or 0) == 0:
                        zero_byte_messages.append(
                            f"{run.get('cell_id')}:{role}:{item.get('message_id')}"
                        )
            waits_by_message: dict[str, list[float]] = defaultdict(list)
            waits = endpoint.get("waits") or []
            if isinstance(waits, Sequence) and not isinstance(waits, (str, bytes)):
                for item in waits:
                    if not isinstance(item, Mapping):
                        continue
                    message_id = str(item.get("message_id", ""))
                    totals = item.get("totals") or item
                    waits_by_message[message_id].append(_number(totals, "wall_ns"))
            for message_id, values in waits_by_message.items():
                if not values:
                    continue
                ordered = sorted(values)
                median = _quantile(ordered, 0.5) or 1.0
                for value in values:
                    if value > 10 * median:
                        wait_outliers.append(
                            {
                                "cell_id": run.get("cell_id"),
                                "role": role,
                                "message_id": message_id,
                                "wait_ns": value,
                                "median_wait_ns": median,
                            }
                        )
    return {
        "tls_ca_fingerprints": sorted(tls_hashes),
        "tls_ca_unique": len(tls_hashes) <= 1,
        "zero_byte_messages": sorted(set(zero_byte_messages)),
        "wait_outliers": wait_outliers,
    }


def _quantile(values: Sequence[float], q: float) -> float:
    if len(values) == 1:
        return float(values[0])
    index = (len(values) - 1) * q
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return float(values[low])
    return float(values[low] * (high - index) + values[high] * (index - low))


def _sha(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
