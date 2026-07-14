"""Figures generated exclusively from MCP-01 aggregate JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .audit import CATEGORIES


def render_transport_cpu_figure(
    aggregate: Mapping[str, Any],
    output_path: Path,
) -> Path:
    """Plot stacked category CPU with matched stripped/throttle floor band."""
    if aggregate.get("experiment") != "mcp_tax" or "cells" not in aggregate:
        raise ValueError("figure input must be an MCP-tax aggregate JSON object")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cells = list(aggregate["cells"])
    transports = sorted(
        {
            str((cell.get("coordinates") or {}).get("transport"))
            for cell in cells
            if _is_primary(cell)
        }
    )
    if not transports:
        raise ValueError("aggregate has no throttle tool_count=1 cells")

    category_values: dict[str, list[float]] = {category: [] for category in CATEGORIES}
    totals: list[float] = []
    for transport in transports:
        selected = [
            cell
            for cell in cells
            if _is_primary(cell)
            and (cell.get("coordinates") or {}).get("transport") == transport
        ]
        for category in CATEGORIES:
            category_values[category].append(
                _median(
                    [
                        float(
                            (cell.get("category_cpu_ns_per_message") or {})
                            .get(category, {})
                            .get("median", 0)
                        )
                        / 1000
                        for cell in selected
                    ]
                )
            )
        totals.append(
            _median(
                [
                    float(cell["combined_cpu_ns_per_message"]["median"]) / 1000
                    for cell in selected
                ]
            )
        )

    fig, axis = plt.subplots(figsize=(9, 5.2), constrained_layout=True)
    bottoms = [0.0] * len(transports)
    colors = plt.get_cmap("tab20").colors
    for index, category in enumerate(CATEGORIES):
        values = category_values[category]
        axis.bar(
            transports,
            values,
            bottom=bottoms,
            label=category,
            color=colors[index],
            width=0.68,
        )
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    floor, reference = _observer_band(cells)
    if floor is not None and reference is not None:
        axis.axhspan(
            floor / 1000,
            reference / 1000,
            color="black",
            alpha=0.08,
            label="observer strict floor → throttle reference",
        )
        axis.axhline(reference / 1000, color="black", linewidth=1.2, linestyle="--")
    for index, total in enumerate(totals):
        axis.text(index, bottoms[index], f" {total:.1f}", va="bottom", ha="center", fontsize=8)

    axis.set_ylabel("CPU (µs / measured message)")
    axis.set_xlabel("Transport")
    debug_only = aggregate.get("result_validity") == "debug_only"
    axis.set_title(
        "MCP-01 debug smoke category CPU by transport"
        if debug_only
        else "MCP-01 category CPU by transport"
    )
    axis.legend(fontsize=7, ncol=2, frameon=False)
    axis.grid(axis="y", alpha=0.2)
    fig.text(
        0.5,
        0.005,
        (
            "DEBUG SMOKE / INELIGIBLE / DO NOT CITE"
            if debug_only
            else "Controlled protocol microbenchmark; not production agent CPU share."
        ),
        ha="center",
        fontsize=8,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def figure_from_aggregate_json(aggregate_path: Path, output_path: Path) -> Path:
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    return render_transport_cpu_figure(aggregate, output_path)


def _is_primary(cell: Mapping[str, Any]) -> bool:
    coordinates = cell.get("coordinates") or {}
    return coordinates.get("mode") == "throttle" and int(
        coordinates.get("tool_count", 0)
    ) == 1


def _observer_band(cells: Sequence[Mapping[str, Any]]) -> tuple[float | None, float | None]:
    from .analyze import cell_steady_cpu_ns_per_message

    grouped: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = {}
    for cell in cells:
        coordinates = cell.get("coordinates") or {}
        key = tuple(
            coordinates.get(field)
            for field in (
                "transport",
                "payload_bytes",
                "schema_profile",
                "tool_count",
                "implementation",
            )
        )
        grouped.setdefault(key, {})[str(coordinates.get("mode"))] = cell
    pairs = [
        (modes["stripped"], modes["throttle"])
        for modes in grouped.values()
        if "stripped" in modes and "throttle" in modes
    ]
    if not pairs:
        return None, None
    floor = _median([cell_steady_cpu_ns_per_message(pair[0]) for pair in pairs])
    reference = _median([cell_steady_cpu_ns_per_message(pair[1]) for pair in pairs])
    return min(floor, reference), max(floor, reference)


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aggregate", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    figure_from_aggregate_json(args.aggregate, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
