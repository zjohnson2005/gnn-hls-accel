"""Capture the complete experiment setup BEFORE any measurement runs.

Probes hardware, OS, Python stack, git state, fixture hashes, and records
the agent architecture and full task suite. Writes:

  apu_characterization/out/setup.json      machine-readable record
  apu_characterization/EXPERIMENT_SETUP.md rendered pre-registration doc

Every value in the .md is read from the probe results or the code itself.
Run this first, commit the artifacts, then run experiments. Each run
artifact embeds the setup digest so results are traceable to this record.

Run: python -m apu_characterization.capture_setup
"""

from __future__ import annotations

from . import env_pin as _env_pin  # noqa: F401 — pin BLAS before numpy in probes

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .profiles import PROFILES
from .tasks import SUBTASKS, TASKS, suite_digest
from .taxonomy import Category

OUT_DIR = Path("apu_characterization/out")
SETUP_JSON = OUT_DIR / "setup.json"
SETUP_MD = Path("apu_characterization/EXPERIMENT_SETUP.md")

PACKAGES = ("numpy", "psutil", "matplotlib", "tiktoken", "sympy", "py-spy")

# Refreshed by run_linux_replication_v3.sh before OpenAI sessions; not user edits.
GIT_IGNORE_RUNTIME_REFRESH = (
    "apu_characterization/out/setup.json",
    "apu_characterization/EXPERIMENT_SETUP.md",
    "apu_characterization/out/step_infer_calibration.json",
)


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def probe_hardware() -> dict[str, Any]:
    hw: dict[str, Any] = {
        "cpu_model": platform.processor() or "unknown",
        "machine": platform.machine(),
    }
    try:
        import psutil

        hw["cores_physical"] = psutil.cpu_count(logical=False)
        hw["cores_logical"] = psutil.cpu_count(logical=True)
        freq = psutil.cpu_freq()
        if freq:
            hw["cpu_freq_mhz_max"] = freq.max
            hw["cpu_freq_mhz_current"] = freq.current
        vm = psutil.virtual_memory()
        hw["ram_total_gb"] = round(vm.total / (1024**3), 2)
        hw["ram_available_gb"] = round(vm.available / (1024**3), 2)
    except ImportError:
        import os

        hw["cores_logical"] = os.cpu_count()
        hw["psutil"] = "missing: install for full hardware capture"

    if sys.platform == "win32":
        name = _run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor).Name"]
        )
        if name:
            hw["cpu_model"] = name
        plan = _run(["powercfg", "/getactivescheme"])
        if plan:
            hw["power_plan"] = plan
    else:
        proc = Path("/proc/cpuinfo")
        if proc.is_file():
            for line in proc.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith("model name"):
                    hw["cpu_model"] = line.split(":", 1)[1].strip()
                    break
        governor = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        if governor.is_file():
            hw["cpu_governor"] = governor.read_text().strip()
        else:
            # WSL2 and many VMs omit cpufreq sysfs; record explicitly so strict
            # validation can distinguish "not probed" from "not available".
            kernel = platform.release().lower()
            if "microsoft-standard-wsl" in kernel or "wsl" in kernel:
                hw["cpu_governor"] = "n/a (WSL2: no cpufreq sysfs)"
            else:
                hw["cpu_governor"] = "n/a (no cpufreq sysfs)"

    return hw


def probe_software() -> dict[str, Any]:
    sw: dict[str, Any] = {
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "python_build": " ".join(platform.python_build()),
        "os": platform.platform(),
    }
    freeze = _run([sys.executable, "-m", "pip", "freeze"])
    versions: dict[str, str] = {}
    for line in freeze.splitlines():
        pkg = line.split("==")[0].strip().lower()
        if pkg in PACKAGES:
            versions[pkg] = line.strip()
    # uv venvs may omit pip; fall back to importlib.metadata.
    try:
        from importlib.metadata import PackageNotFoundError, version as pkg_version
    except ImportError:
        from importlib_metadata import PackageNotFoundError, version as pkg_version  # type: ignore
    for pkg in PACKAGES:
        if pkg in versions:
            continue
        try:
            versions[pkg] = f"{pkg}=={pkg_version(pkg)}"
        except PackageNotFoundError:
            versions[pkg] = "not installed"
    sw["packages"] = versions
    return sw


def _git_cmd() -> list[str]:
    """Resolve git executable (Windows often lacks git on PATH)."""
    import shutil

    exe = shutil.which("git")
    if exe:
        return [exe]
    if sys.platform == "win32":
        for candidate in (
            Path(r"C:\Program Files\Git\cmd\git.exe"),
            Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
            Path.home() / "AppData" / "Local" / "Programs" / "Git" / "cmd" / "git.exe",
        ):
            if candidate.is_file():
                return [str(candidate)]
    return ["git"]


def _porcelain_path(line: str) -> str:
    line = line.rstrip("\r\n")
    parts = line.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    raw = parts[1].split(" -> ")[-1].strip()
    return raw.replace("\\", "/")


def probe_git(*, ignore_paths: tuple[str, ...] = ()) -> dict[str, str]:
    git = _git_cmd()[0]
    rev = _run(_git_cmd() + ["rev-parse", "HEAD"]) or "unknown"
    porcelain = _run(_git_cmd() + ["status", "--porcelain"])
    ignore = {p.replace("\\", "/") for p in ignore_paths}
    dirty_lines: list[str] = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        if not path or path in ignore:
            continue
        dirty_lines.append(line)
    out: dict[str, str] = {
        "commit": rev,
        "dirty": "yes" if dirty_lines else "no",
    }
    if dirty_lines:
        out["dirty_paths"] = [_porcelain_path(ln) for ln in dirty_lines]
    if rev == "unknown":
        out["git_path"] = git if Path(git).is_file() else "not found on PATH"
    elif Path(git).is_file():
        out["git_path"] = git
    return out


def probe_openai_config() -> dict[str, Any]:
    import os

    return {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": os.getenv("OPENAI_TEMPERATURE", "0 (default)"),
        "timeout_s": os.getenv("OE_OPENAI_TIMEOUT_S", "120"),
        "api_key_set": bool(os.getenv("OPENAI_API_KEY")),
    }


def probe_blas_pin() -> dict[str, str]:
    from .env_pin import blas_pin_snapshot

    return blas_pin_snapshot()


def probe_kernel() -> str:
    if sys.platform == "win32":
        return platform.platform()
    uname = _run(["uname", "-sr"])
    return uname or platform.platform()


def probe_fixtures() -> dict[str, Any]:
    meta_path = Path("apu_characterization/fixtures/fixtures_meta.json")
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"status": "not generated yet: run generate_fixtures or any experiment once"}


AGENT_DESCRIPTION = {
    "type": "plain-Python ReAct loop (no LangGraph in the measured path)",
    "decision_source": "scripted TaskSpec turn sequence, deterministic per (task, seed)",
    "llm": "in-process mock: asyncio.sleep drawn from seeded lognormal "
    "(zero thread CPU, models remote inference wait), synthetic response "
    "of profile-drawn size",
    "orchestration": "OrchEngine: task-graph build (ORCH_SETUP), readiness "
    "scan + scatter-on-completion dispatch (ORCH_DISPATCH), mirroring "
    "orchestration_engine/software/engine_sim.cpp semantics",
    "tools": {
        "search": "regex scan (phrase then word-alternation) over 50 MB corpus, top-5 snippets",
        "code_exec": "exec of the task-supplied Python snippet, bounded builtins",
        "retrieve": "full cosine top-5 over 100k x 384 float32 matrix, "
        "query embedded deterministically from query text hash",
        "calculator": "sympy (or plain eval fallback) on the task-supplied expression",
        "api": "mock remote API: HTTP_CLIENT-timed request build and response "
        "envelope parse around a seeded lognormal asyncio sleep (pure I/O wait)",
    },
    "turn_mechanics": "single call, fan-out burst (several calls per turn, "
    "completions land back-to-back on an ALL_OF join), chained handoff "
    "(pipe_result: parse previous result, rebuild next args), sub-agent "
    "spawning (child sessions with their own task graphs), structured "
    "emission (re-emit and validate the full accumulated JSON per turn)",
    "execution_model": "asyncio, all sessions share one event-loop thread; "
    "optional --threads mode for the comparison point",
    "clocks": "wall = perf_counter_ns; CPU = thread_time_ns per region; "
    "process user/system = os.times or psutil at run start/end",
    "nesting_rule": "exclusive self-time: inner region pauses its parent",
}


def build_setup() -> dict[str, Any]:
    setup = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "hardware": probe_hardware(),
        "software": probe_software(),
        "git": probe_git(),
        "kernel": probe_kernel(),
        "openai": probe_openai_config(),
        "blas_pin": probe_blas_pin(),
        "fixtures": probe_fixtures(),
        "agent": AGENT_DESCRIPTION,
        "taxonomy": [c.value for c in Category],
        "profiles": {
            name: {
                "turns": f"{p.turns_min} to {p.turns_max}",
                "tool_weights": p.tool_weights,
                "llm_median_s": p.llm_median_s,
                "llm_sigma": p.llm_sigma,
                "llm_response_kb": f"{p.llm_response_kb_min} to {p.llm_response_kb_max}",
                "tool_result_kb": f"{p.tool_result_kb_min} to {p.tool_result_kb_max}",
                "tool_rate": p.tool_rate,
            }
            for name, p in PROFILES.items()
        },
        "task_suite": {
            "digest": suite_digest(),
            "count": len(TASKS),
            "tasks": [t.describe() for t in TASKS],
            "subagent_tasks": [t.describe() for t in SUBTASKS.values()],
        },
    }
    blob = json.dumps(setup, sort_keys=True, default=str)
    setup["setup_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return setup


def render_md(setup: dict[str, Any]) -> str:
    hw = setup["hardware"]
    sw = setup["software"]
    git = setup["git"]
    agent = setup["agent"]

    lines = [
        "# APU characterization: experiment setup (pre-registration)",
        "",
        f"Captured: {setup['captured_utc']}",
        f"Setup digest: `{setup['setup_digest']}` (embedded in every run artifact)",
        "This file is generated by `python -m apu_characterization.capture_setup`.",
        "Do not hand-edit; re-run the capture instead.",
        "",
        "## Hardware",
        "",
        f"- CPU: {hw.get('cpu_model')}",
        f"- physical cores: {hw.get('cores_physical')}, logical: {hw.get('cores_logical')}",
        f"- max freq MHz: {hw.get('cpu_freq_mhz_max', 'n/a')},"
        f" current: {hw.get('cpu_freq_mhz_current', 'n/a')}",
        f"- RAM: {hw.get('ram_total_gb')} GB total,"
        f" {hw.get('ram_available_gb')} GB available at capture",
        f"- power plan: {hw.get('power_plan', hw.get('cpu_governor', 'not readable'))}",
        "",
        "## Software",
        "",
        f"- OS: {sw['os']}",
        f"- Python: {sw['python']} ({sw['python_implementation']})",
        f"- git commit: `{git['commit']}` (dirty: {git['dirty']})",
        "- packages:",
    ]
    for pkg, ver in sw["packages"].items():
        lines.append(f"  - {ver}" if "==" in ver else f"  - {pkg}: {ver}")

    bp = setup.get("blas_pin", {})
    lines.extend(
        [
            "",
            "## BLAS thread pin (v3.1+)",
            "",
            "NumPy/OpenBLAS matmul must run single-threaded so retrieve CPU books to",
            "TOOL_COMPUTE instead of invisible OpenBLAS workers (THREADPOOL).",
            f"- OPENBLAS_NUM_THREADS: {bp.get('OPENBLAS_NUM_THREADS', 'unset')}",
            f"- MKL_NUM_THREADS: {bp.get('MKL_NUM_THREADS', 'unset')}",
            f"- OMP_NUM_THREADS: {bp.get('OMP_NUM_THREADS', 'unset')}",
        ]
    )

    lines.extend(
        [
            "",
            "## Agent under test",
            "",
            f"- type: {agent['type']}",
            f"- decisions: {agent['decision_source']}",
            f"- LLM: {agent['llm']}",
            f"- orchestration: {agent['orchestration']}",
            f"- turn mechanics: {agent['turn_mechanics']}",
            f"- execution: {agent['execution_model']}",
            f"- clocks: {agent['clocks']}",
            f"- nesting: {agent['nesting_rule']}",
            "- tools:",
        ]
    )
    for name, desc in agent["tools"].items():
        lines.append(f"  - `{name}`: {desc}")

    lines.extend(
        [
            "",
            "## Fixtures",
            "",
            f"- {json.dumps(setup['fixtures'], indent=2)}",
            "",
            "## Category taxonomy",
            "",
            "- " + ", ".join(setup["taxonomy"]),
            "",
            "## Task profiles",
            "",
        ]
    )
    for name, p in setup["profiles"].items():
        lines.append(
            f"- `{name}`: turns {p['turns']}, tool_rate {p['tool_rate']},"
            f" llm median {p['llm_median_s']} s sigma {p['llm_sigma']},"
            f" response {p['llm_response_kb']} KB, tool result {p['tool_result_kb']} KB,"
            f" weights {p['tool_weights']}"
        )

    ts = setup["task_suite"]
    lines.extend(
        [
            "",
            f"## Task suite ({ts['count']} tasks, digest `{ts['digest']}`)",
            "",
            "Session i with seed s runs task[(s + i) mod n] from its profile pool;"
            " the mixed profile draws from all tasks.",
            "",
        ]
    )
    for t in ts["tasks"] + ts.get("subagent_tasks", []):
        lines.append(f"### {t['task_id']} ({t['profile']})")
        lines.append("")
        lines.append(f"Goal: {t['goal']}")
        lines.append("")
        for i, turn in enumerate(t["turns"]):
            lines.append(f"- turn {i}: {turn}")
        lines.append("")

    lines.extend(
        [
            "## Measurement protocol",
            "",
            "1. Timer correctness tests must pass first"
            " (python -m apu_characterization.tests.test_instr).",
            "2. Warm state (tokenizer, corpus, vector matrix) loads before the"
            " measured window.",
            "3. Per region: thread_time_ns (CPU, excludes I/O wait) and"
            " perf_counter_ns (wall), exclusive nesting.",
            "4. Invariant per run: sum(category CPU) + residual = total thread"
            " CPU; residual must stay below 15%.",
            "5. Instrumentation overhead: timer microbenchmark plus"
            " APU_NOINSTR=1 comparison run; must stay below 3% or be mitigated.",
            "6. py-spy sampling cross-check at c=100 mixed; agreement within"
            " 10 percentage points per major category.",
            "7. Medians and IQR over 5 seeds minimum; no single-run numbers in"
            " figures or tables.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if git dirty, psutil missing, or required fields unknown",
    )
    args = parser.parse_args()

    setup = build_setup()
    if args.strict:
        from .setup_validate import validate_setup

        errors = validate_setup(setup, strict=True)
        if errors:
            raise SystemExit(
                "Strict capture failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SETUP_JSON.write_text(json.dumps(setup, indent=2, default=str), encoding="utf-8")
    SETUP_MD.write_text(render_md(setup), encoding="utf-8")
    print(f"setup json: {SETUP_JSON}")
    print(f"setup md:   {SETUP_MD}")
    print(f"digest:     {setup['setup_digest']}")


if __name__ == "__main__":
    main()
