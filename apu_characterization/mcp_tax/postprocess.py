"""Postprocess retained MCP-01 runs without launching measurements."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analyze import analyze_root, write_aggregate
from .figures import render_transport_cpu_figure
from .report import write_report
from .runner import HostLock
from .validate import validate_mcp_tax

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = Path(__file__).with_name("died_ledger.json")


def postprocess(
    run_root: Path,
    *,
    output_root: Path | None = None,
    workers: int | None = None,
) -> dict[str, Path]:
    """Analyze immutable completed runs in parallel and validate the bundle."""

    run_root = Path(run_root).resolve()
    if not run_root.is_dir():
        raise FileNotFoundError(f"retained run root does not exist: {run_root}")
    output_root = (
        Path(output_root).resolve() if output_root is not None else run_root.parent
    )
    paths = {
        "aggregate": output_root / "mcp_tax.matrix.json",
        "report": output_root / "mcp_tax.report.md",
        "figure": output_root / "mcp_tax.figure.png",
    }

    # The runner holds this same lock across every serial measurement. Analysis
    # can fan out only while no measurement process owns the retained run root.
    with HostLock(run_root.parent / ".measurement.lock"):
        aggregate = analyze_root(run_root, workers=workers)
        write_aggregate(paths["aggregate"], aggregate)
        write_report(
            paths["report"],
            aggregate,
            died_ledger_path=DEFAULT_LEDGER,
            aggregate_name=paths["aggregate"].name,
        )
        render_transport_cpu_figure(aggregate, paths["figure"])

    errors = validate_mcp_tax(aggregate)
    if errors:
        rendered = "\n".join(f"  - {error}" for error in errors)
        raise RuntimeError(f"MCP-01 publication validation failed:\n{rendered}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path, help="retained runs/ directory")
    parser.add_argument(
        "--output-root",
        type=Path,
        help="artifact directory (default: parent of run_root)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="parallel completed-run audit workers (default: up to 8)",
    )
    args = parser.parse_args()
    paths = postprocess(
        args.run_root,
        output_root=args.output_root,
        workers=args.workers,
    )
    for name, path in paths.items():
        print(f"{name}={path}")
    print("validate_mcp_tax=PASS")


if __name__ == "__main__":
    main()
