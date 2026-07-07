"""Environment capture and METHODOLOGY.md generation."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .instr import NO_INSTR, measure_timer_overhead_ns
from .harness.runner import run_batch

METHODOLOGY_PATH = Path("apu_characterization/METHODOLOGY.md")


def _git_commit(allow_dirty: bool) -> str:
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if dirty and not allow_dirty:
            raise RuntimeError("git tree is dirty; commit or pass --allow-dirty")
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        suffix = "-dirty" if dirty else ""
        return rev + suffix
    except FileNotFoundError:
        return "unknown"


def _pip_subset() -> dict[str, str]:
    keys = ("numpy", "matplotlib", "psutil", "tiktoken", "sympy")
    out: dict[str, str] = {}
    try:
        freeze = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        for line in freeze:
            name = line.split("==")[0].lower()
            if name in keys:
                out[name] = line.strip()
    except Exception:
        pass
    return out


def _cpu_info() -> dict[str, Any]:
    info: dict[str, Any] = {"platform": platform.platform(), "python": sys.version.split()[0]}
    try:
        import psutil

        info["cpu_model"] = platform.processor() or "unknown"
        info["cores_logical"] = psutil.cpu_count(logical=True)
        info["cores_physical"] = psutil.cpu_count(logical=False)
        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
    except Exception:
        info["cores_logical"] = None
    if hasattr(platform, "win32_ver") and sys.platform == "win32":
        info["os"] = f"Windows {platform.win32_ver()[0]}"
    else:
        info["os"] = platform.system()
        info["kernel"] = platform.release()
    return info


def _load_avg() -> float | None:
    try:
        return float(__import__("os").getloadavg()[0])
    except (AttributeError, OSError):
        return None


def measure_instrumentation_overhead() -> dict[str, float]:
    ns_per_pair = measure_timer_overhead_ns(200_000)
    on = run_batch(concurrency=10, profile="mixed", seed=999, mode="asyncio", llm_median_scale=0.01)
    import os

    os.environ["APU_NOINSTR"] = "1"
    try:
        from importlib import reload
        import apu_characterization.instr as instr_mod

        reload(instr_mod)
        off = run_batch(
            concurrency=10, profile="mixed", seed=999, mode="asyncio", llm_median_scale=0.01
        )
    finally:
        os.environ.pop("APU_NOINSTR", None)
        from importlib import reload
        import apu_characterization.instr as instr_mod2

        reload(instr_mod2)

    on_cpu = on["totals"]["thread_cpu_ns"]
    off_cpu = off["totals"]["thread_cpu_ns"]
    delta = max(0, on_cpu - off_cpu)
    frac = delta / on_cpu if on_cpu else 0.0
    return {
        "timer_ns_per_pair": ns_per_pair,
        "on_cpu_ns": float(on_cpu),
        "off_cpu_ns": float(off_cpu),
        "delta_cpu_ns": float(delta),
        "delta_fraction": frac,
    }


def run_pyspy_crosscheck(out_dir: Path, seed: int = 0) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    speedscope = out_dir / "pyspy_c100_mixed.speedscope.json"
    try:
        proc = subprocess.run(
            [
                "py-spy",
                "record",
                "--format",
                "speedscope",
                "--output",
                str(speedscope),
                "--",
                sys.executable,
                "-m",
                "apu_characterization.run_sweep",
                "--concurrency",
                "100",
                "--profiles",
                "mixed",
                "--seeds",
                "1",
                "--mode",
                "asyncio",
                "--out",
                str(out_dir / "pyspy_tmp"),
                "--skip-methodology",
                "--skip-live",
                "--skip-warmup",
                "--force",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        ok = proc.returncode == 0 and speedscope.is_file()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"status": "skipped", "reason": str(exc)}

    timer_run = out_dir / "runs" / "c100_mixed_seed0.json"
    timer_shares: dict[str, float] = {}
    if timer_run.is_file():
        data = json.loads(timer_run.read_text(encoding="utf-8"))
        total = data["totals"]["thread_cpu_ns"]
        for cat, vals in data.get("per_category", {}).items():
            timer_shares[cat] = vals["cpu_ns"] / total if total else 0.0

    pyspy_shares = _parse_speedscope_shares(speedscope) if ok else {}
    comparison: dict[str, Any] = {}
    for cat in set(timer_shares) | set(pyspy_shares):
        t = timer_shares.get(cat, 0.0) * 100
        p = pyspy_shares.get(cat, 0.0) * 100
        comparison[cat] = {"timer_pp": t, "pyspy_pp": p, "delta_pp": abs(t - p)}

    major = [c for c in comparison if comparison[c]["timer_pp"] >= 5.0]
    pass_ok = all(comparison[c]["delta_pp"] <= 10.0 for c in major) if major else True
    return {
        "status": "ok" if ok else "failed",
        "speedscope": str(speedscope),
        "comparison": comparison,
        "pass": pass_ok,
    }


def _parse_speedscope_shares(path: Path) -> dict[str, float]:
    """Map speedscope stacks to taxonomy categories by module name heuristics."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    frames = {f["name"]: f.get("file", "") for f in data.get("shared", {}).get("frames", [])}
    profiles = data.get("profiles", [])
    if not profiles:
        return {}

    samples = profiles[0].get("samples", [])
    weights = profiles[0].get("weights", [])
    total = sum(weights) or 1

    mapping = {
        "ORCH_SETUP": ("orch_engine", "setup"),
        "ORCH_DISPATCH": ("orch_engine", "dispatch"),
        "SERIALIZATION": ("json", "dumps", "loads"),
        "TOKENIZATION": ("tiktoken", "token"),
        "PROMPT_ASSEMBLY": ("mock_llm", "prompt", "react_loop"),
        "CONTEXT_MGMT": ("copy", "deepcopy", "context"),
        "TOOL_COMPUTE": ("tools", "impl", "search", "retrieve"),
        "LOGGING": ("logging",),
        "GC": ("gc",),
    }

    cat_weight: dict[str, float] = {k: 0.0 for k in mapping}
    cat_weight["INTERPRETER"] = 0.0

    for stack, w in zip(samples, weights):
        names = [frames.get(str(i), str(i)) for i in stack]
        joined = " ".join(names).lower()
        matched = False
        for cat, keys in mapping.items():
            if any(k in joined for k in keys):
                cat_weight[cat] += w
                matched = True
                break
        if not matched and any(k in joined for k in ("ceval", "python", "dict", "alloc")):
            cat_weight["INTERPRETER"] += w

    return {k: v / total for k, v in cat_weight.items() if v > 0}


def write_methodology(
    path: Path,
    *,
    cli_args: list[str],
    config: dict[str, Any],
    overhead: dict[str, float],
    max_residual: float,
    pyspy: dict[str, Any],
    deviations: list[str],
    live_validation: dict[str, Any] | None,
    threads_compare: dict[str, Any] | None,
    allow_dirty: bool,
) -> None:
    commit = _git_commit(allow_dirty)
    env = _cpu_info()
    load = _load_avg()
    lines = [
        "# APU Characterization Methodology",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Environment",
        "",
        f"- git commit: `{commit}`",
        f"- python: {env.get('python')}",
        f"- platform: {env.get('platform')}",
        f"- cpu: {env.get('cpu_model', 'unknown')}",
        f"- logical cores: {env.get('cores_logical')}",
        f"- ram_gb: {env.get('ram_gb')}",
        f"- loadavg_1m: {load}",
        "",
        "## Protocol",
        "",
        f"- CLI: `{' '.join(cli_args)}`",
        f"- resolved config: `{json.dumps(config)}`",
        "",
        "## Instrumentation overhead",
        "",
        f"- timer ns/pair: {overhead['timer_ns_per_pair']:.2f}",
        f"- on_cpu_ns: {int(overhead['on_cpu_ns'])}",
        f"- off_cpu_ns: {int(overhead['off_cpu_ns'])}",
        f"- delta_fraction: {overhead['delta_fraction']:.4f}",
        "",
        "## Accounting invariant",
        "",
        f"- max_residual_fraction observed: {max_residual:.4f}",
        "",
        "## py-spy cross-check",
        "",
        f"- status: {pyspy.get('status')}",
        f"- pass: {pyspy.get('pass')}",
    ]
    if pyspy.get("comparison"):
        lines.append("- category deltas (pp):")
        for cat, vals in sorted(pyspy["comparison"].items()):
            lines.append(
                f"  - {cat}: timer={vals['timer_pp']:.1f} pyspy={vals['pyspy_pp']:.1f} "
                f"delta={vals['delta_pp']:.1f}"
            )

    if threads_compare:
        lines.extend(
            [
                "",
                "## asyncio vs threads (c=100, mixed)",
                "",
                f"- asyncio_cpu_ns: {threads_compare.get('asyncio_cpu_ns')}",
                f"- threads_cpu_ns: {threads_compare.get('threads_cpu_ns')}",
                f"- delta_fraction: {threads_compare.get('delta_fraction')}",
            ]
        )

    if live_validation:
        lines.extend(
            [
                "",
                "## Live mode validation",
                "",
                f"- status: {live_validation.get('status')}",
            ]
        )
        for row in live_validation.get("rows", []):
            lines.append(f"  - {row}")

    if deviations:
        lines.extend(["", "## Deviations", ""])
        lines.extend(f"- {d}" for d in deviations)

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Category timers use thread_time_ns (excludes I/O wait and sleep).",
            "- GC hooks cover collector cycles only; refcount deallocation is a lower bound.",
            "- Per-category kernel time attribution is approximate; os_times reports aggregate user/system.",
            "- INTERPRETER fraction in py-spy is a sampling estimate, not a timer bucket.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
