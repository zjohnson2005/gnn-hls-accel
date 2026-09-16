"""CAP-01 measured figures with an explicitly labeled design projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

PROJECTION_CAPTION = (
    "Projection uncertainty: only three measured floor x points are available. "
    "The dashed extension is descriptive extrapolation, not inferential evidence."
)


def generate_figures(
    aggregate: Mapping[str, Any],
    *,
    solve_rate_path: Path,
    capability_floor_path: Path,
) -> tuple[Path, Path]:
    """Write separate measured-latency and capability-floor panels."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "CAP-01 figures require optional dependency matplotlib; "
            "analysis and reporting remain available without it."
        ) from exc

    figure_data = aggregate.get("figure_data") or {}
    curves = list(figure_data.get("solve_rate_curves") or [])
    if not curves:
        raise ValueError("aggregate has no measured solve-rate curve data")

    solve_rate_path.parent.mkdir(parents=True, exist_ok=True)
    capability_floor_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axis = plt.subplots(figsize=(7.2, 4.5))
    styles = {
        "langgraph": ("o", "#3b6fb6"),
        "rust": ("s", "#d47a1f"),
        "raw_python": ("^", "#2d9d63"),
    }
    for harness in ("langgraph", "rust", "raw_python"):
        points = sorted(
            (item for item in curves if item.get("harness") == harness),
            key=lambda item: float(item["latency_scale_ms"]),
        )
        if not points:
            continue
        marker, color = styles[harness]
        axis.plot(
            [float(item["latency_scale_ms"]) for item in points],
            [float(item["solve_rate_pct"]) for item in points],
            marker=marker,
            color=color,
            label=harness,
        )
    axis.set_xscale("log")
    axis.set_xlabel("Measured model latency scale (ms)")
    axis.set_ylabel("Solve rate (%)")
    axis.set_title("CAP-01 solve rate versus measured model latency")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(solve_rate_path, dpi=180)
    plt.close(fig)

    floor_points = list(figure_data.get("capability_floor_points") or [])
    if len(floor_points) != 3:
        raise ValueError(
            "capability-versus-floor figure requires exactly three measured "
            "harness points"
        )
    fit = (aggregate.get("capability_floor_fit") or {}).get("fit")
    if not fit:
        raise ValueError("aggregate has no descriptive three-point floor fit")
    projection_label = str(figure_data.get("projection_label") or "")
    target_us = [float(value) for value in figure_data.get("projection_target_floor_us") or []]
    if len(target_us) != 2:
        raise ValueError("aggregate must contain the two frozen Tier D target floors")

    fig, axis = plt.subplots(figsize=(7.6, 5.2))
    for point in floor_points:
        harness = str(point["harness"])
        marker, color = styles[harness]
        axis.scatter(
            [float(point["floor_ms"])],
            [float(point["solve_rate_pct"])],
            marker=marker,
            color=color,
            s=65,
            label=f"{harness} measured",
            zorder=3,
        )
    ordered = sorted(floor_points, key=lambda item: float(item["floor_ms"]))
    axis.plot(
        [float(item["floor_ms"]) for item in ordered],
        [float(item["solve_rate_pct"]) for item in ordered],
        color="#555555",
        linewidth=1.2,
        label="descriptive relationship across measured points",
    )

    raw = next(item for item in floor_points if item["harness"] == "raw_python")
    target_ms = sorted(value / 1000.0 for value in target_us)
    projection_x = [target_ms[0], target_ms[1], float(raw["floor_ms"])]
    intercept = float(fit["intercept_pp"])
    slope = float(fit["slope_pp_per_ms"])
    projection_y = [intercept + slope * value for value in projection_x]
    axis.plot(
        projection_x,
        projection_y,
        linestyle="--",
        color="#7f3c8d",
        linewidth=1.5,
        label=projection_label,
    )
    axis.set_xscale("log")
    axis.set_xlabel("Host-measured harness floor (ms)")
    axis.set_ylabel("Solve rate (%)")
    axis.set_title("CAP-01 capability versus host-measured floor")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend(fontsize=7)
    fig.text(0.01, 0.01, PROJECTION_CAPTION, fontsize=7, wrap=True)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(capability_floor_path, dpi=180)
    plt.close(fig)
    return solve_rate_path, capability_floor_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aggregate", type=Path)
    parser.add_argument("--solve-rate-output", required=True, type=Path)
    parser.add_argument("--capability-floor-output", required=True, type=Path)
    args = parser.parse_args()
    aggregate = json.loads(args.aggregate.read_text(encoding="utf-8"))
    paths = generate_figures(
        aggregate,
        solve_rate_path=args.solve_rate_output,
        capability_floor_path=args.capability_floor_output,
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
