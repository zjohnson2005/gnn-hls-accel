"""Enumerate MCP-01's frozen matrix; execution requires an explicit callback."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from apu_characterization.mcp_tax.contracts import (
    PROTOCOL_VERSION,
    CellCoordinates,
    CellPlan,
    enumerate_matrix,
    load_protocol,
)
from apu_characterization.mcp_tax.plan import build_cell_plan as _build_cell_plan
from apu_characterization.mcp_tax.runner import DEFAULT_RUN_ROOT, McpTaxRunner


def build_cell_plan(cell: CellCoordinates, seed: int) -> CellPlan:
    """Compatibility wrapper around the sole canonical plan builder."""

    return _build_cell_plan(cell, seed=int(seed))


def enumerate_plans(
    *,
    include_http_stream: bool = False,
    seeds: list[int] | None = None,
) -> list[CellPlan]:
    protocol = load_protocol()
    selected_seeds = (
        [int(seed) for seed in seeds]
        if seeds is not None
        else [int(seed) for seed in protocol["primary"]["seeds"]]
    )
    return [
        build_cell_plan(cell, seed)
        for cell in enumerate_matrix(include_http_stream=include_http_stream)
        for seed in selected_seeds
    ]


def load_callback(specification: str) -> Callable[..., Any]:
    if ":" not in specification:
        raise ValueError("callback must be MODULE:CALLABLE")
    module_name, attribute = specification.split(":", 1)
    callback = getattr(importlib.import_module(module_name), attribute)
    if not callable(callback):
        raise TypeError(f"{specification} is not callable")
    return callback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-http-stream", action="store_true")
    parser.add_argument("--seeds", default="0,1,2,3,4")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform serial measurements (default is dry-run)",
    )
    parser.add_argument(
        "--callback",
        default="apu_characterization.mcp_tax.execute:execute_cell",
        help="execution adapter as MODULE:CALLABLE",
    )
    parser.add_argument("--publication", action="store_true")
    parser.add_argument("--client-cores")
    parser.add_argument("--server-cores")
    parser.add_argument("--os-cores", dest="os_analysis_cores")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit matrix coordinates as JSON")
    args = parser.parse_args()

    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    cells = enumerate_matrix(include_http_stream=args.include_http_stream)
    plans = enumerate_plans(
        include_http_stream=args.include_http_stream,
        seeds=seeds,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "dry_run": not args.execute,
                    "cell_count": len(cells),
                    "run_count": len(plans),
                    "cells": [
                        {"cell_id": cell.cell_id, **cell.__dict__} for cell in cells
                    ],
                    "seeds": seeds,
                },
                indent=2,
            )
        )
    else:
        print(
            f"MCP-01 matrix: {len(cells)} cells, {len(plans)} seed runs; "
            f"{'EXECUTE' if args.execute else 'DRY RUN'}"
        )
    if not args.execute:
        return
    if args.publication:
        missing = [
            option
            for option, value in (
                ("--client-cores", args.client_cores),
                ("--server-cores", args.server_cores),
                ("--os-cores", args.os_analysis_cores),
            )
            if not value
        ]
        if missing:
            parser.error("--publication requires " + ", ".join(missing))
        os.environ["MCP_TAX_PUBLICATION"] = "1"
        os.environ["MCP_CLIENT_CORES"] = args.client_cores
        os.environ["MCP_SERVER_CORES"] = args.server_cores
        os.environ["MCP_OS_ANALYSIS_CORES"] = args.os_analysis_cores
    outcomes = McpTaxRunner(
        run_root=args.run_root,
        execute=load_callback(args.callback),
    ).run(plans, resume=not args.no_resume)
    completed = sum(outcome.status == "completed" for outcome in outcomes)
    skipped = sum(outcome.status == "skipped_complete" for outcome in outcomes)
    print(f"completed={completed} skipped_complete={skipped}")


if __name__ == "__main__":
    main()
